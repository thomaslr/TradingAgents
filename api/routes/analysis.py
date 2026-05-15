from fastapi import APIRouter, Depends, BackgroundTasks, HTTPException
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import logging
import sys
import os
from datetime import datetime
from pathlib import Path
import multiprocessing

from api.dependencies import get_registry, get_config
from tradingagents.db.registry import RunRegistry
from cli.batch_runner import run_batch_analysis

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/analysis", tags=["Analysis"])

# ── Global Task Management ──────────────────────────────────────────

class AnalysisTaskState:
    """Manages the lifecycle and cancellation of background analysis jobs using multiprocessing."""
    def __init__(self):
        self.manager = multiprocessing.Manager()
        self._shared_data = self.manager.dict({
            "active_job": None,
            "active_job_id": None,
            "last_error": None,
            "is_paused": False,
            "yield_requested": False
        })
        self.abort_event = multiprocessing.Event()
        self.lock = multiprocessing.Lock()
        self.worker_process: Optional[multiprocessing.Process] = None
        self.worker_thread: Optional[multiprocessing.Process] = None # For compatibility with old variable names if any

    @property
    def active_job(self): return self._shared_data["active_job"]
    @active_job.setter
    def active_job(self, val): self._shared_data["active_job"] = val

    @property
    def active_job_id(self): return self._shared_data["active_job_id"]
    @active_job_id.setter
    def active_job_id(self, val): self._shared_data["active_job_id"] = val

    @property
    def last_error(self): return self._shared_data["last_error"]
    @last_error.setter
    def last_error(self, val): self._shared_data["last_error"] = val

    @property
    def is_paused(self): return self._shared_data["is_paused"]
    @is_paused.setter
    def is_paused(self, val): self._shared_data["is_paused"] = val

    @property
    def yield_requested(self): return self._shared_data["yield_requested"]
    @yield_requested.setter
    def yield_requested(self, val): self._shared_data["yield_requested"] = val

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
                    job = task_state.active_job
                    if job:
                        job["status_message"] = msg
                        task_state.active_job = job
            
            from api.utils.network import ensure_ollama_ready
            import asyncio
            
            ready = asyncio.run(ensure_ollama_ready(ollama_url, mac_address, wake_timeout, set_status))
            if not ready:
                raise Exception(f"Ollama server at {ollama_url} is unreachable.")
            
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
                job = task_state.active_job
                if job:
                    job["current_ticker"] = ticker
                    job["current_date"] = date
                    task_state.active_job = job

        def token_cb(in_tokens: int, out_tokens: int):
            with task_state.lock:
                job = task_state.active_job
                if job:
                    job["input_tokens"] = in_tokens
                    job["output_tokens"] = out_tokens
                    task_state.active_job = job

        def status_cb(msg: str):
            with task_state.lock:
                job = task_state.active_job
                if job:
                    job["sub_status"] = msg
                    task_state.active_job = job

        summary = run_batch_analysis(
            tickers=request.tickers,
            dates=expanded_dates,
            config=config,
            registry=registry,
            skip_completed=request.skip_completed,
            force=request.force,
            abort_event=task_state.abort_event,
            progress_callback=progress_cb,
            token_callback=token_cb,
            status_callback=status_cb
        )
        logger.info(f"Background analysis complete: {summary}")
    except Exception as e:
        import traceback
        err_msg = f"Analysis Failed: {str(e)}\n{traceback.format_exc()}"
        logger.error(err_msg)
        task_state.set_error(str(e))
    finally:
        was_yielded = task_state.yield_requested
        if request.id:
            status = "completed" if not task_state.last_error else "failed"
            if was_yielded:
                status = "pending"
            
            registry.update_queue_status(request.id, status, error=task_state.last_error)
            

        registry.close()
        task_state.clear_job()

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

            if task_state.is_running():
                time.sleep(3)
                continue

            registry = RunRegistry(db_path)
            try:
                next_job = registry.get_next_queued_job()
                if next_job:
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
                    registry.update_queue_status(next_job["id"], "running")
                    execute_analysis_task(req, base_config.copy(), db_path)
                else:
                    time.sleep(10)
            finally:
                registry.close()
                
        except Exception as e:
            logger.error(f"Queue Worker Error: {e}")
            time.sleep(10)

def start_worker_if_needed(background_tasks: BackgroundTasks, db_path: str, config: dict):
    """Ensures the background worker is running."""
    with task_state.lock:
        if task_state.worker_process is None or not task_state.worker_process.is_alive():
            task_state.worker_process = multiprocessing.Process(
                target=run_queue_worker, 
                args=(db_path, config),
                daemon=True
            )
            task_state.worker_process.start()

# ── Endpoints ────────────────────────────────────────────────────────

@router.get("/queue")
def get_research_queue(registry: RunRegistry = Depends(get_registry)):
    return registry.get_queue()

@router.post("/queue")
def add_to_research_queue(
    item: Dict[str, Any], 
    background_tasks: BackgroundTasks,
    registry: RunRegistry = Depends(get_registry),
    config: dict = Depends(get_config)
):
    date_from = str(item.get("dateFrom", "")).strip()
    date_to = str(item.get("dateTo", "")).strip()
    
    # Enforce max length to prevent concatenation bugs (e.g. "2026-01-042026-02-05")
    if len(date_from) > 10: date_from = date_from[:10]
    if len(date_to) > 10: date_to = date_to[:10]

    dates_list = []
    if date_from:
        dates_list.append(date_from)
        if date_to and date_to != date_from:
            dates_list.append(date_to)

    job_data = {
        "id": item.get("id", datetime.now().strftime("%Y%m%d%H%M%S")),
        "tickers": item.get("tickers", []),
        "dates": dates_list,
        "provider": item.get("provider", "openai"),
        "quick_model": item.get("quickModel", ""),
        "deep_model": item.get("deepModel", ""),
        "depth": item.get("depth", 1),
        "force": item.get("force", False)
    }
    registry.add_to_queue(job_data, priority=item.get("priority", False))
    start_worker_if_needed(background_tasks, registry.db_path, config)
    return {"status": "success", "id": job_data["id"]}

@router.delete("/queue/{job_id}")
def remove_from_research_queue(job_id: str, registry: RunRegistry = Depends(get_registry)):
    registry.remove_from_queue(job_id)
    return {"status": "success"}

@router.post("/queue/reorder")
def reorder_research_queue(job_ids: List[str], registry: RunRegistry = Depends(get_registry)):
    registry.reorder_queue(job_ids)
    return {"status": "success"}

@router.post("/queue/start")
def start_research_queue(background_tasks: BackgroundTasks, registry: RunRegistry = Depends(get_registry), config: dict = Depends(get_config)):
    task_state.is_paused = False
    start_worker_if_needed(background_tasks, registry.db_path, config)
    return {"status": "success"}

@router.post("/queue/pause")
def pause_research_queue():
    task_state.is_paused = True
    if task_state.is_running():
        task_state.stop_job()
    return {"status": "success"}

@router.post("/queue/resume")
def resume_research_queue(background_tasks: BackgroundTasks, registry: RunRegistry = Depends(get_registry), config: dict = Depends(get_config)):
    task_state.is_paused = False
    start_worker_if_needed(background_tasks, registry.db_path, config)
    return {"status": "success"}

@router.post("/batch")
def start_batch_analysis(request: AnalysisRequest, background_tasks: BackgroundTasks, config: dict = Depends(get_config), registry: RunRegistry = Depends(get_registry)):
    if task_state.is_running():
        raise HTTPException(status_code=400, detail="Job already running.")
    
    import uuid
    job_id = request.id or str(uuid.uuid4())
    job_data = {
        "id": job_id,
        "tickers": request.tickers,
        "dates": request.dates,
        "provider": request.llm_provider or config.get("llm_provider", "openai"),
        "quick_model": request.quick_think_llm or config.get("quick_think_llm", ""),
        "deep_model": request.deep_think_llm or config.get("deep_think_llm", ""),
        "depth": request.max_debate_rounds or config.get("max_debate_rounds", 1),
        "force": request.force
    }
    
    registry.add_to_queue(job_data, priority=True)
    task_state.is_paused = False
    start_worker_if_needed(background_tasks, registry.db_path, config)
    return {"status": "accepted", "id": job_id}

@router.get("/status")
def get_analysis_status(background_tasks: BackgroundTasks, registry: RunRegistry = Depends(get_registry), config: dict = Depends(get_config)):
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
    task_state.stop_job(yield_after=False)
    return {"status": "success"}

@router.post("/yield")
def yield_analysis():
    task_state.stop_job(yield_after=True)
    return {"status": "success"}

@router.post("/purge")
async def purge_analysis(registry: RunRegistry = Depends(get_registry)):
    task_state.abort_event.set()
    with task_state.lock:
        if task_state.worker_process and task_state.worker_process.is_alive():
            task_state.worker_process.kill()  # Forcefully kill with SIGKILL
            task_state.worker_process.join(timeout=2)
        
        registry.clear_queue()
        cache_dir = os.environ.get("TRADINGAGENTS_CACHE_DIR", "data/cache")
        if os.path.exists(cache_dir):
            try:
                import shutil
                shutil.rmtree(cache_dir, ignore_errors=True)
                os.makedirs(cache_dir, exist_ok=True)
            except Exception as e:
                logger.error(f"Purge error: {e}")
        task_state.active_job = None
    return {"status": "success"}
