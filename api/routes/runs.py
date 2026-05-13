from fastapi import APIRouter, Depends, HTTPException, Query
from typing import List, Optional, Dict, Any

from api.dependencies import get_registry
from tradingagents.db.registry import RunRegistry

router = APIRouter(prefix="/runs", tags=["Runs"])

@router.get("", response_model=List[Dict[str, Any]])
def list_runs(
    ticker: Optional[str] = Query(None, description="Filter by ticker"),
    status: Optional[str] = Query(None, description="Filter by status (e.g., completed, running)"),
    limit: int = Query(100, description="Max number of runs to return"),
    registry: RunRegistry = Depends(get_registry)
):
    """List historical analysis runs."""
    return registry.list_runs(ticker=ticker, status=status, limit=limit)

import yfinance as yf
from functools import lru_cache
from pathlib import Path
import shutil
from pydantic import BaseModel

@lru_cache(maxsize=100)
def _get_company_name(ticker: str) -> str:
    """Fetch company name from yfinance with simple caching."""
    try:
        t = yf.Ticker(ticker)
        return t.info.get("shortName") or t.info.get("longName") or ticker
    except Exception:
        return ticker

@router.get("/tickers", response_model=List[Dict[str, str]])
def list_unique_tickers(registry: RunRegistry = Depends(get_registry)):
    """Get a list of all unique tickers in the database with their company names."""
    runs = registry.list_runs(limit=1000)
    unique_tickers = sorted(list(set(run["ticker"] for run in runs)))
    
    return [
        {"ticker": t, "name": _get_company_name(t)}
        for t in unique_tickers
    ]

class BatchDeleteRequest(BaseModel):
    run_ids: List[int]

@router.post("/batch-delete")
def batch_delete_runs(request: BatchDeleteRequest, registry: RunRegistry = Depends(get_registry)):
    """Delete multiple runs from history and their report directories."""
    try:
        deleted_count = 0
        for run_id in request.run_ids:
            run = registry.get_run(run_id)
            if run and run.get("report_dir"):
                report_path = Path(run["report_dir"])
                if report_path.exists() and report_path.is_dir():
                    shutil.rmtree(report_path, ignore_errors=True)
            registry.delete_run(run_id)
            deleted_count += 1
        return {"status": "success", "message": f"{deleted_count} runs deleted."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/{run_id}")
def delete_run(run_id: int, registry: RunRegistry = Depends(get_registry)):
    """Delete a specific run from history and its report directory."""
    try:
        run = registry.get_run(run_id)
        if run and run.get("report_dir"):
            report_path = Path(run["report_dir"])
            if report_path.exists() and report_path.is_dir():
                shutil.rmtree(report_path, ignore_errors=True)
        registry.delete_run(run_id)
        return {"status": "success", "message": f"Run {run_id} deleted."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/configs", response_model=List[Dict[str, Any]])
def list_configs(registry: RunRegistry = Depends(get_registry)):
    """List all simulation configurations with their labels and colors."""
    return registry.list_configs()

@router.get("/performance", response_model=List[Dict[str, Any]])
def get_performance_data(
    ticker: Optional[str] = Query(None, description="Filter by ticker"),
    config_id: Optional[str] = Query(None, description="Filter by simulation config"),
    date_from: Optional[str] = Query(None, description="Start date (YYYY-MM-DD)"),
    date_to: Optional[str] = Query(None, description="End date (YYYY-MM-DD)"),
    limit: int = Query(5000, description="Max number of runs to return"),
    registry: RunRegistry = Depends(get_registry),
):
    """Get runs with resolved outcomes for the performance dashboard.
    
    Returns only runs where outcome_status = 'resolved', joined with 
    simulation config label and color for chart rendering.
    """
    return registry.list_runs_for_performance(
        ticker=ticker,
        config_id=config_id,
        date_from=date_from,
        date_to=date_to,
        limit=limit,
    )

