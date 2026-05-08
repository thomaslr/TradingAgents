from fastapi import APIRouter, Depends, HTTPException
from typing import List, Dict, Any
from api.dependencies import get_config
from tradingagents.agents.utils.memory import TradingMemoryLog

router = APIRouter(prefix="/memory", tags=["Memory"])

@router.get("", response_model=List[Dict[str, Any]])
def get_memory_entries(config: dict = Depends(get_config)):
    """Fetch all entries from the trading memory log."""
    try:
        memory_log = TradingMemoryLog(config)
        entries = memory_log.load_entries()
        return entries
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to load memory log: {str(e)}")

@router.delete("")
def clear_memory_log(config: dict = Depends(get_config)):
    """Clear all entries from the trading memory log."""
    try:
        memory_log = TradingMemoryLog(config)
        if memory_log._log_path and memory_log._log_path.exists():
            # Use atomic write to clear (truncate) the file
            memory_log._log_path.write_text("", encoding="utf-8")
        return {"status": "ok", "message": "Memory log cleared"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to clear memory log: {str(e)}")

