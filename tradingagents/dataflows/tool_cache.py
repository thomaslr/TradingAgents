import os
import json
import hashlib
import logging
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)

class ToolCache:
    """A persistent cache for tool outputs to ensure reproducibility."""
    
    def __init__(self, cache_dir: str):
        self.cache_dir = Path(cache_dir) / "tools"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
    def _get_key(self, method: str, *args, **kwargs) -> str:
        """Generate a stable hash key for a method call."""
        # Normalize kwargs by sorting keys
        sorted_kwargs = dict(sorted(kwargs.items()))
        data = json.dumps({
            "method": method,
            "args": args,
            "kwargs": sorted_kwargs
        }, sort_keys=True)
        
        return hashlib.sha256(data.encode("utf-8")).hexdigest()
    
    def get(self, method: str, *args, **kwargs) -> Optional[Any]:
        """Retrieve a cached result if it exists."""
        key = self._get_key(method, *args, **kwargs)
        cache_file = self.cache_dir / f"{key}.json"
        
        if cache_file.exists():
            try:
                logger.info(f"Cache hit for tool: {method}")
                with open(cache_file, "r", encoding="utf-8") as f:
                    return json.load(f)["result"]
            except Exception as e:
                logger.warning(f"Failed to read cache file {cache_file}: {e}")
        
        return None
    
    def set(self, method: str, result: Any, *args, **kwargs) -> None:
        """Store a result in the cache."""
        key = self._get_key(method, *args, **kwargs)
        cache_file = self.cache_dir / f"{key}.json"
        
        try:
            data = {
                "method": method,
                "args": args,
                "kwargs": kwargs,
                "timestamp": json.dumps(json.dumps(None)), # Placeholder for future timestamp if needed
                "result": result
            }
            with open(cache_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            logger.info(f"Cached output for tool: {method}")
        except Exception as e:
            logger.warning(f"Failed to write cache file {cache_file}: {e}")
