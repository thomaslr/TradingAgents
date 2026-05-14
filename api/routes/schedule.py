from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Any, Optional

from api.dependencies import get_schedule_manager
from tradingagents.db.schedule_manager import ScheduleManager

router = APIRouter(prefix="/schedule", tags=["Schedule"])

class ScheduleRequest(BaseModel):
    tickers: List[str]
    config: Dict[str, Any]
    interval_minutes: int
    scheduled_time: Optional[str] = None

@router.get("", response_model=List[Dict[str, Any]])
def list_schedules(manager: ScheduleManager = Depends(get_schedule_manager)):
    """List all scheduled analysis jobs."""
    return manager.list_jobs()

@router.post("")
def add_schedule(request: ScheduleRequest, manager: ScheduleManager = Depends(get_schedule_manager)):
    """Add a new scheduled analysis job."""
    try:
        job = manager.add_job(
            tickers=request.tickers,
            config=request.config,
            interval_minutes=request.interval_minutes,
            scheduled_time=request.scheduled_time
        )
        return {"status": "success", "job": job}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    return {"status": "success", "message": f"Job {job_id} deleted"}

@router.delete("/{job_id}")
def delete_schedule(job_id: str, manager: ScheduleManager = Depends(get_schedule_manager)):
    """Delete a scheduled analysis job."""
    deleted = manager.delete_job(job_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Job not found")
    return {"status": "success", "message": f"Job {job_id} deleted"}

@router.post("/{job_id}/toggle")
def toggle_schedule(job_id: str, manager: ScheduleManager = Depends(get_schedule_manager)):
    """Toggle the paused state of a job."""
    success = manager.toggle_job(job_id)
    if not success:
        raise HTTPException(status_code=404, detail="Job not found")
    return {"status": "success"}

@router.patch("/{job_id}")
def update_schedule(job_id: str, request: Dict[str, Any], manager: ScheduleManager = Depends(get_schedule_manager)):
    """Update a scheduled job."""
    success = manager.update_job(job_id, **request)
    if not success:
        raise HTTPException(status_code=404, detail="Job not found")
    return {"status": "success"}
