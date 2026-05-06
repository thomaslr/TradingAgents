from fastapi import APIRouter, Depends, BackgroundTasks, HTTPException
from pydantic import BaseModel
from typing import List, Optional
import logging

from api.dependencies import get_registry, get_config
from tradingagents.db.registry import RunRegistry
from cli.batch_runner import run_batch_analysis

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/analysis", tags=["Analysis"])

class AnalysisRequest(BaseModel):
    tickers: List[str]
    dates: List[str]
    force: bool = False
    skip_completed: bool = True

def execute_analysis_task(request: AnalysisRequest, config: dict, db_path: str):
    """Background task to run the analysis."""
    # We need a new registry instance for the background thread
    registry = RunRegistry(db_path)
    try:
        logger.info(f"Starting background analysis for {request.tickers} on {request.dates}")
        summary = run_batch_analysis(
            tickers=request.tickers,
            dates=request.dates,
            config=config,
            registry=registry,
            skip_completed=request.skip_completed,
            force=request.force
        )
        logger.info(f"Background analysis complete: {summary}")
    except Exception as e:
        logger.error(f"Background analysis failed: {e}")
    finally:
        registry.close()

@router.post("/batch")
def start_batch_analysis(
    request: AnalysisRequest, 
    background_tasks: BackgroundTasks,
    config: dict = Depends(get_config),
    registry: RunRegistry = Depends(get_registry)
):
    """Trigger a new batch analysis asynchronously."""
    
    # We pass the db_path to the background task so it can create its own DB connection
    # SQLite connections cannot be shared across threads easily
    background_tasks.add_task(execute_analysis_task, request, config, registry.db_path)
    
    return {
        "status": "accepted",
        "message": f"Analysis queued for {len(request.tickers)} tickers and {len(request.dates)} dates.",
        "tickers": request.tickers,
        "dates": request.dates
    }
