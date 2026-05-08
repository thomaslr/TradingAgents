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
    ) -> Dict[str, Any]:
        jobs = self._read_jobs()
        job_id = str(uuid.uuid4())
        
        # Start immediately (next_run = now)
        next_run = datetime.now(timezone.utc).isoformat()
        
        job = {
            "id": job_id,
            "tickers": tickers,
            "config": config,
            "interval_minutes": interval_minutes,
            "last_run": None,
            "next_run": next_run,
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
            if not job.get("next_run"):
                continue
            next_run = datetime.fromisoformat(job["next_run"])
            if now >= next_run:
                due_jobs.append(job)
                
        return due_jobs

    def mark_job_ran(self, job_id: str):
        jobs = self._read_jobs()
        now = datetime.now(timezone.utc)
        for job in jobs:
            if job["id"] == job_id:
                job["last_run"] = now.isoformat()
                interval = timedelta(minutes=job["interval_minutes"])
                # calculate next run based on now (to avoid immediate back-to-back runs if it fell behind)
                job["next_run"] = (now + interval).isoformat()
                break
        self._write_jobs(jobs)
