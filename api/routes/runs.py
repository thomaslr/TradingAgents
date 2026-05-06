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

@lru_cache(max_size=100)
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

@router.delete("/{run_id}")
def delete_run(run_id: int, registry: RunRegistry = Depends(get_registry)):
    """Delete a specific run from history."""
    try:
        registry.delete_run(run_id)
        return {"status": "success", "message": f"Run {run_id} deleted."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
