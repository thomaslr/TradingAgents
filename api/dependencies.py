import os
from typing import Generator
from fastapi import Request

from tradingagents.default_config import DEFAULT_CONFIG
from tradingagents.db.registry import RunRegistry

def get_registry(request: Request) -> Generator[RunRegistry, None, None]:
    """Dependency to get a database registry instance."""
    # Read the db path from the app state or default config
    db_path = getattr(request.app.state, "db_path", DEFAULT_CONFIG["db_path"])
    registry = RunRegistry(db_path)
    try:
        yield registry
    finally:
        registry.close()

def get_config() -> dict:
    """Dependency to get the current configuration."""
    return DEFAULT_CONFIG.copy()

from tradingagents.db.schedule_manager import ScheduleManager
from pathlib import Path

def get_schedule_manager(request: Request) -> ScheduleManager:
    db_path = Path(getattr(request.app.state, "db_path", DEFAULT_CONFIG["db_path"]))
    schedule_path = db_path.parent / "schedule.json"
    return ScheduleManager(schedule_path)
