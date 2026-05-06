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

@router.delete("/{run_id}")
def delete_run(run_id: int, registry: RunRegistry = Depends(get_registry)):
    """Delete a specific run from history."""
    try:
        registry.delete_run(run_id)
        return {"status": "success", "message": f"Run {run_id} deleted."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
