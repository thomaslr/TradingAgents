from fastapi import APIRouter, Depends, BackgroundTasks, HTTPException
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import logging
import threading
import sys
import os
from datetime import datetime
from pathlib import Path

from api.dependencies import get_registry, get_config
from tradingagents.db.registry import RunRegistry
from cli.batch_runner import run_batch_analysis

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/analysis", tags=["Analysis"])

# ── Global Task Management ──────────────────────────────────────────

class AnalysisTaskState:
    """Manages the lifecycle and cancellation of background analysis jobs."""
    def __init__(self):
        self.active_job: Optional[Dict[str, Any]] = None
        self.active_job_id: Optional[str] = None
        self.last_error = None
        self.status_message: Optional[str] = None
        self.abort_event = threading.Event()
        self.lock = threading.Lock()
        self.worker_thread: Optional[threading.Thread] = None
        self.is_queue_processing = False
        self.is_paused = False
        self.yield_requested = False

    def start_job(self, tickers: List[str], dates: List[str], config: dict, job_id: Optional[str] = None):
        with self.lock:
            self.abort_event.clear()
            self.last_error = None
            self.active_job_id = job_id
            self.active_job = {
                "id": job_id,
                "tickers": tickers,
                "dates": dates,
                "started_at": datetime.now().isoformat(),
                "config": {
                    "provider": config.get("llm_provider"),
                    "quick_model": config.get("quick_think_llm"),
                    "deep_model": config.get("deep_think_llm"),
                    "debate_depth": config.get("max_debate_rounds")
                },
                "status_message": None
            }

    def set_error(self, error: str):
        with self.lock:
            self.last_error = error
            self.active_job = None
            self.active_job_id = None

    def stop_job(self, yield_after: bool = False):
        with self.lock:
            self.abort_event.set()
            self.yield_requested = yield_after

    def clear_job(self):
        with self.lock:
            self.active_job = None
            self.active_job_id = None
            self.abort_event.clear()
            self.yield_requested = False

    def is_running(self) -> bool:
        return self.active_job is not None

# Global instance
task_state = AnalysisTaskState()

# ── API Models ───────────────────────────────────────────────────────

class AnalysisRequest(BaseModel):
    id: Optional[str] = None
    tickers: List[str]
    dates: List[str]
    force: bool = False
    skip_completed: bool = True
    # Model configuration overrides
    llm_provider: Optional[str] = None
    quick_think_llm: Optional[str] = None
    deep_think_llm: Optional[str] = None
    max_debate_rounds: Optional[int] = None

# ── Task Execution ──────────────────────────────────────────────────

def execute_analysis_task(request: AnalysisRequest, config: dict, db_path: str):
    """Background task to run the analysis."""
    # Emergency logging to local file
    log_file = Path("analysis_startup.log")
    with open(log_file, "a") as f:
        f.write(f"\n[{datetime.now()}] Starting task for {request.tickers}\n")
    
    try:
        # Ensure root is in path
        root_dir = str(Path(__file__).parent.parent.parent)
        if root_dir not in sys.path:
            sys.path.append(root_dir)
            
        print(f"DEBUG: execute_analysis_task started for {request.tickers}")
        registry = RunRegistry(db_path)
        # Apply overrides from request to config
        if request.llm_provider: config["llm_provider"] = request.llm_provider
        if request.quick_think_llm: config["quick_think_llm"] = request.quick_think_llm
        if request.deep_think_llm: config["deep_think_llm"] = request.deep_think_llm
        if request.max_debate_rounds is not None: config["max_debate_rounds"] = request.max_debate_rounds
        
        # --- SMART WAKE LOGIC ---
        if config.get("llm_provider") == "ollama":
            ollama_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434/v1")
            mac_address = os.getenv("OLLAMA_MAC_ADDRESS")
            wake_timeout = int(os.getenv("OLLAMA_WAKE_TIMEOUT", "60"))
            
            def set_status(msg: str):
                with task_state.lock:
                    if task_state.active_job:
                        task_state.active_job["status_message"] = msg
            
            from api.utils.network import ensure_ollama_ready
            import asyncio
            
            # Since we are in a background thread, we need a way to run the async check
            # We can use a temporary event loop or just run it synchronously if needed.
            # But httpx.AsyncClient needs a loop.
            ready = asyncio.run(ensure_ollama_ready(ollama_url, mac_address, wake_timeout, set_status))
            
            if not ready:
                # If we can't reach it and wake failed, we should probably fail here
                # rather than letting the agents timeout individually.
                raise Exception(f"Ollama server at {ollama_url} is unreachable.")
            
            # Clear the waking status once ready
            set_status(None)
        # ------------------------

        from cli.batch_runner import _expand_dates
        expanded_dates = request.dates
        if len(expanded_dates) == 2:
            try:
                expanded_dates = _expand_dates(expanded_dates[0], expanded_dates[1])
            except Exception:
                pass
                
        logger.info(f"Starting background analysis for {request.tickers} on {expanded_dates}")
        
        task_state.start_job(request.tickers, expanded_dates, config, job_id=request.id)
        
        def progress_cb(ticker: str, date: str):
            with task_state.lock:
                if task_state.active_job:
                    task_state.active_job["current_ticker"] = ticker
                    task_state.active_job["current_date"] = date

        def token_cb(in_tokens: int, out_tokens: int):
            with task_state.lock:
                if task_state.active_job:
                    task_state.active_job["input_tokens"] = in_tokens
                    task_state.active_job["output_tokens"] = out_tokens

        summary = run_batch_analysis(
            tickers=request.tickers,
            dates=expanded_dates,
            config=config,
            registry=registry,
            skip_completed=request.skip_completed,
            force=request.force,
            abort_event=task_state.abort_event,
            progress_callback=progress_cb,
            token_callback=token_cb
        )
        logger.info(f"Background analysis complete: {summary}")
    except Exception as e:
        import traceback
        err_msg = f"Analysis Failed: {str(e)}\n{traceback.format_exc()}"
        logger.error(err_msg)
        with open(log_file, "a") as f:
            f.write(f"CRASH: {err_msg}\n")
        task_state.set_error(str(e))
    finally:
        # Check if we should yield this job back to the queue
        was_yielded = task_state.yield_requested
        
        if request.id:
            status = "completed" if not task_state.last_error else "failed"
            if was_yielded:
                status = "queued"
                logger.info(f"Job {request.id} yielded back to queue.")
            
            registry.update_queue_status(request.id, status, error=task_state.last_error)
            
            if was_yielded:
                # Re-add to top of queue to ensure it's next after the new job
                # Note: update_queue_status already set it to 'queued', but we want it at the TOP
                registry.reorder_queue([request.id] + [j["id"] for j in registry.get_queue() if j["id"] != request.id])

        registry.close()
        task_state.clear_job()

# ── Endpoints ────────────────────────────────────────────────────────

# ── Queue Worker ──────────────────────────────────────────────────

def run_queue_worker(db_path: str, base_config: dict):
    """Background worker that processes the research queue sequentially."""
    import time
    logger.info("Research Queue Worker started.")
    
    while True:
        try:
            if task_state.is_paused:
                time.sleep(5)
                continue

            if task_state.abort_event.is_set():
                # If we are stopping, don't start new jobs
                time.sleep(5)
                continue

            if task_state.is_running():
                time.sleep(3)
                continue

            registry = RunRegistry(db_path)
            try:
                next_job = registry.get_next_queued_job()
                if next_job:
                    logger.info(f"Worker picking up job: {next_job['id']} ({next_job['tickers']})")
                    
                    # Map queue job to AnalysisRequest
                    req = AnalysisRequest(
                        id=next_job["id"],
                        tickers=next_job["tickers"],
                        dates=next_job["dates"],
                        force=next_job["force"],
                        llm_provider=next_job["provider"],
                        quick_think_llm=next_job["quick_model"],
                        deep_think_llm=next_job["deep_model"],
                        max_debate_rounds=next_job["depth"]
                    )
                    
                    # Update status in DB immediately
                    registry.update_queue_status(next_job["id"], "running")
                    
                    # Run it (this will block this thread until job is done)
                    execute_analysis_task(req, base_config.copy(), db_path)
                else:
                    # Nothing to do, sleep a bit
                    time.sleep(10)
            finally:
                registry.close()
                
        except Exception as e:
            logger.error(f"Queue Worker Error: {e}")
            time.sleep(10)

def start_worker_if_needed(background_tasks: BackgroundTasks, db_path: str, config: dict):
    """Ensures the background worker is running."""
    with task_state.lock:
        if task_state.worker_thread is None or not task_state.worker_thread.is_alive():
            logger.info("Spawning Research Queue Worker thread...")
            task_state.worker_thread = threading.Thread(
                target=run_queue_worker, 
                args=(db_path, config),
                daemon=True
            )
            task_state.worker_thread.start()

# ── API Models ───────────────────────────────────────────────────────

class QueueItem(BaseModel):
    id: str
    tickers: List[str]
    dateFrom: Optional[str] = None
    dateTo: Optional[str] = None
    provider: str
    quickModel: str
    deepModel: str
    depth: int = 1
    force: bool = False

# ── Endpoints ────────────────────────────────────────────────────────

@router.get("/queue")
def get_research_queue(registry: RunRegistry = Depends(get_registry)):
    """Fetch the current persistent research queue."""
    return registry.get_queue()

@router.post("/queue")
def add_to_research_queue(
    item: Dict[str, Any], 
    background_tasks: BackgroundTasks,
    registry: RunRegistry = Depends(get_registry),
    config: dict = Depends(get_config)
):
    """Add a new job to the persistent research queue."""
    # Convert frontend keys to DB keys if needed
    job_data = {
        "id": item.get("id", datetime.now().strftime("%Y%m%d%H%M%S")),
        "tickers": item.get("tickers", []),
        "dates": [item.get("dateFrom"), item.get("dateTo")] if item.get("dateFrom") else [],
        "provider": item.get("provider", "openai"),
        "quick_model": item.get("quickModel", ""),
        "deep_model": item.get("deepModel", ""),
        "depth": item.get("depth", 1),
        "force": item.get("force", False)
    }
    
    registry.add_to_queue(job_data, priority=item.get("priority", False))
    
    # Ensure worker is running
    start_worker_if_needed(background_tasks, registry.db_path, config)
    
    return {"status": "success", "id": job_data["id"]}

@router.delete("/queue/{job_id}")
def remove_from_research_queue(job_id: str, registry: RunRegistry = Depends(get_registry)):
    """Remove a job from the queue."""
    registry.remove_from_queue(job_id)
    return {"status": "success"}

@router.post("/queue/reorder")
def reorder_research_queue(
    job_ids: List[str], 
    registry: RunRegistry = Depends(get_registry)
):
    """Update the sort order of the research queue."""
    registry.reorder_queue(job_ids)
    return {"status": "success"}

@router.post("/queue/start")
def start_research_queue(
    background_tasks: BackgroundTasks,
    registry: RunRegistry = Depends(get_registry),
    config: dict = Depends(get_config)
):
    """Manually signal the worker to start processing the queue."""
    task_state.is_paused = False # Auto-resume if signaled
    start_worker_if_needed(background_tasks, registry.db_path, config)
    return {"status": "success", "message": "Worker signaled and resumed."}

@router.post("/queue/pause")
def pause_research_queue():
    """Pause the research queue processing."""
    task_state.is_paused = True
    # Also stop current job if running so it can be resumed later
    if task_state.is_running():
        task_state.stop_job()
    return {"status": "success", "message": "Queue paused."}

@router.post("/queue/resume")
def resume_research_queue(
    background_tasks: BackgroundTasks,
    registry: RunRegistry = Depends(get_registry),
    config: dict = Depends(get_config)
):
    """Resume the research queue processing."""
    task_state.is_paused = False
    start_worker_if_needed(background_tasks, registry.db_path, config)
    return {"status": "success", "message": "Queue resumed."}

@router.post("/batch")
def start_batch_analysis(
    request: AnalysisRequest, 
    background_tasks: BackgroundTasks,
    config: dict = Depends(get_config),
    registry: RunRegistry = Depends(get_registry)
):
    """Trigger a new batch analysis asynchronously."""
    if task_state.is_running():
        raise HTTPException(status_code=400, detail="An analysis job is already running.")
    
    # Immediately mark as running to prevent frontend race conditions
    task_state.start_job(request.tickers, request.dates, config)
    
    background_tasks.add_task(execute_analysis_task, request, config, registry.db_path)
    
    return {
        "status": "accepted",
        "message": f"Analysis queued for {len(request.tickers)} tickers and {len(request.dates)} dates.",
        "tickers": request.tickers,
        "dates": request.dates
    }

@router.get("/status")
def get_analysis_status(
    background_tasks: BackgroundTasks,
    registry: RunRegistry = Depends(get_registry),
    config: dict = Depends(get_config)
):
    """Check if an analysis job is currently running."""
    # Ensure worker is alive if there's anything in the queue
    queue = registry.get_queue()
    if len(queue) > 0:
        start_worker_if_needed(background_tasks, registry.db_path, config)

    return {
        "running": task_state.is_running(),
        "job": task_state.active_job,
        "last_error": task_state.last_error,
        "queue_count": len(queue),
        "is_paused": task_state.is_paused
    }

@router.post("/stop")
def stop_analysis():
    """Request the current analysis job to stop gracefully."""
    if not task_state.is_running():
        return {"status": "error", "message": "No job is currently running."}
    
    task_state.stop_job(yield_after=False)
    return {"status": "success", "message": "Stop requested. The job will abort before the next ticker/date."}

@router.post("/yield")
def yield_analysis():
    """Request the current analysis job to yield to the queue gracefully."""
    if not task_state.is_running():
        return {"status": "error", "message": "No job is currently running."}
    
    task_state.stop_job(yield_after=True)
    return {"status": "success", "message": "Yield requested. The job will finish the current day and then move back to the queue."}
