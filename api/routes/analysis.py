from fastapi import APIRouter, Depends, BackgroundTasks, HTTPException
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import logging
import threading
from datetime import datetime

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
        self.abort_event = threading.Event()
        self.lock = threading.Lock()

    def start_job(self, tickers: List[str], dates: List[str]):
        with self.lock:
            self.abort_event.clear()
            self.active_job = {
                "tickers": tickers,
                "dates": dates,
                "started_at": datetime.now().isoformat()
            }

    def stop_job(self):
        with self.lock:
            self.abort_event.set()

    def clear_job(self):
        with self.lock:
            self.active_job = None
            self.abort_event.clear()

    def is_running(self) -> bool:
        return self.active_job is not None

# Global instance
task_state = AnalysisTaskState()

# ── API Models ───────────────────────────────────────────────────────

class AnalysisRequest(BaseModel):
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
    print(f"DEBUG: execute_analysis_task started for {request.tickers}")
    registry = RunRegistry(db_path)
    try:
        # Apply overrides from request to config
        if request.llm_provider: config["llm_provider"] = request.llm_provider
        if request.quick_think_llm: config["quick_think_llm"] = request.quick_think_llm
        if request.deep_think_llm: config["deep_think_llm"] = request.deep_think_llm
        if request.max_debate_rounds is not None: config["max_debate_rounds"] = request.max_debate_rounds

        from cli.batch_runner import _expand_dates
        expanded_dates = request.dates
        if len(expanded_dates) == 2:
            try:
                expanded_dates = _expand_dates(expanded_dates[0], expanded_dates[1])
            except Exception:
                pass
                
        logger.info(f"Starting background analysis for {request.tickers} on {expanded_dates}")
        print(f"DEBUG: Tickers: {request.tickers}, Dates: {expanded_dates}, Provider: {config.get('llm_provider')}")
        
        task_state.start_job(request.tickers, expanded_dates)
        
        def progress_cb(ticker: str, date: str):
            with task_state.lock:
                if task_state.active_job:
                    task_state.active_job["current_ticker"] = ticker
                    task_state.active_job["current_date"] = date

        summary = run_batch_analysis(
            tickers=request.tickers,
            dates=expanded_dates,
            config=config,
            registry=registry,
            skip_completed=request.skip_completed,
            force=request.force,
            abort_event=task_state.abort_event,
            progress_callback=progress_cb
        )
        logger.info(f"Background analysis complete: {summary}")
        print(f"DEBUG: Analysis complete: {summary}")
    except Exception as e:
        logger.error(f"Background analysis failed: {e}")
        print(f"DEBUG: Analysis failed: {e}")
        import traceback
        traceback.print_exc()
    finally:
        registry.close()
        task_state.clear_job()
        print("DEBUG: execute_analysis_task finished and job cleared.")

# ── Endpoints ────────────────────────────────────────────────────────

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
    
    background_tasks.add_task(execute_analysis_task, request, config, registry.db_path)
    
    return {
        "status": "accepted",
        "message": f"Analysis queued for {len(request.tickers)} tickers and {len(request.dates)} dates.",
        "tickers": request.tickers,
        "dates": request.dates
    }

@router.get("/status")
def get_analysis_status():
    """Check if an analysis job is currently running."""
    return {
        "running": task_state.is_running(),
        "job": task_state.active_job
    }

@router.post("/stop")
def stop_analysis():
    """Request the current analysis job to stop gracefully."""
    if not task_state.is_running():
        return {"status": "error", "message": "No job is currently running."}
    
    task_state.stop_job()
    return {"status": "success", "message": "Stop requested. The job will abort before the next ticker/date."}
