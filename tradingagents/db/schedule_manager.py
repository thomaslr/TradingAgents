import json
import uuid
import logging
from pathlib import Path
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)

class ScheduleManager:
    def __init__(self, config_path: str | Path):
        self.config_path = Path(config_path)
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_file()

    def _ensure_file(self):
        if not self.config_path.exists():
            self._write_jobs([])

    def _read_jobs(self) -> List[Dict[str, Any]]:
        try:
            content = self.config_path.read_text(encoding="utf-8")
            return json.loads(content)
        except Exception as e:
            logger.error(f"Failed to read schedule file {self.config_path}: {e}")
            return []

    def _write_jobs(self, jobs: List[Dict[str, Any]]):
        self.config_path.write_text(json.dumps(jobs, indent=2), encoding="utf-8")

    def list_jobs(self) -> List[Dict[str, Any]]:
        return self._read_jobs()

    def add_job(
        self,
        tickers: List[str],
        config: Dict[str, Any],
        interval_minutes: int,
        scheduled_time: Optional[str] = None, # HH:MM
    ) -> Dict[str, Any]:
        jobs = self._read_jobs()
        job_id = str(uuid.uuid4())
        
        # Calculate first run
        now = datetime.now(timezone.utc)
        if scheduled_time:
            # Anchor to today at HH:MM
            try:
                hh, mm = map(int, scheduled_time.split(":"))
                target = now.replace(hour=hh, minute=mm, second=0, microsecond=0)
                # If that time already passed today, move to tomorrow
                if target < now:
                    target += timedelta(days=1)
                next_run = target.isoformat()
            except:
                next_run = now.isoformat()
        else:
            next_run = now.isoformat()
        
        job = {
            "id": job_id,
            "tickers": tickers,
            "config": config,
            "interval_minutes": interval_minutes,
            "scheduled_time": scheduled_time,
            "last_run": None,
            "next_run": next_run,
            "paused": False,
            "created_at": datetime.now(timezone.utc).isoformat()
        }
        jobs.append(job)
        self._write_jobs(jobs)
        return job

    def delete_job(self, job_id: str) -> bool:
        jobs = self._read_jobs()
        new_jobs = [j for j in jobs if j["id"] != job_id]
        if len(new_jobs) == len(jobs):
            return False
        self._write_jobs(new_jobs)
        return True

    def get_due_jobs(self) -> List[Dict[str, Any]]:
        jobs = self._read_jobs()
        due_jobs = []
        now = datetime.now(timezone.utc)
        
        for job in jobs:
            if job.get("paused"):
                continue
            if not job.get("next_run"):
                continue
            next_run = datetime.fromisoformat(job["next_run"])
            if now >= next_run:
                due_jobs.append(job)
                
        return due_jobs

    def toggle_job(self, job_id: str) -> bool:
        """Toggle the paused state of a job."""
        jobs = self._read_jobs()
        for job in jobs:
            if job["id"] == job_id:
                job["paused"] = not job.get("paused", False)
                self._write_jobs(jobs)
                return True
        return False

    def update_job(self, job_id: str, **kwargs) -> bool:
        """Update job parameters."""
        jobs = self._read_jobs()
        for job in jobs:
            if job["id"] == job_id:
                for k, v in kwargs.items():
                    job[k] = v
                self._write_jobs(jobs)
                return True
        return False

    def mark_job_ran(self, job_id: str):
        jobs = self._read_jobs()
        now = datetime.now(timezone.utc)
        for job in jobs:
            if job["id"] == job_id:
                job["last_run"] = now.isoformat()
                interval = timedelta(minutes=job["interval_minutes"])
                
                if job.get("scheduled_time"):
                    # Use the anchor from next_run + interval
                    last_next_run = datetime.fromisoformat(job["next_run"])
                    job["next_run"] = (last_next_run + interval).isoformat()
                else:
                    job["next_run"] = (now + interval).isoformat()
                break
        self._write_jobs(jobs)
