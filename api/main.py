import os
import uvicorn
import asyncio
from datetime import datetime
from pathlib import Path
import httpx
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import logging
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

# Configure logging at the very top so all modules inherit the settings
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

from api.routes import runs, reports, market, analysis, schedule, memory
from tradingagents.default_config import DEFAULT_CONFIG

app = FastAPI(
    title="TradingAgents API",
    description="Backend API for the TradingAgents Web UI",
    version="1.0.0"
)

# Enable CORS for the Vue frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify the exact Vue app origin
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Store the db_path in app state so dependencies can access it
app.state.db_path = DEFAULT_CONFIG["db_path"]

# Include routers
app.include_router(runs.router, prefix="/api")
app.include_router(reports.router, prefix="/api")
app.include_router(market.router, prefix="/api")
app.include_router(analysis.router, prefix="/api")
app.include_router(schedule.router, prefix="/api")
app.include_router(memory.router, prefix="/api")



@app.on_event("startup")
async def startup_event():
    asyncio.create_task(scheduler_loop())
    # Start the Research Queue worker if jobs are pending
    from api.routes.analysis import start_worker_if_needed
    from tradingagents.db.registry import RunRegistry
    from tradingagents.default_config import DEFAULT_CONFIG
    
    # We use a dummy background tasks object for the startup call
    from fastapi import BackgroundTasks
    start_worker_if_needed(BackgroundTasks(), DEFAULT_CONFIG["db_path"], DEFAULT_CONFIG)

from api.utils.network import ensure_ollama_ready

async def scheduler_loop():
    """Background task to poll for scheduled jobs."""
    while True:
        try:
            # We need to construct a mock request to pass to get_schedule_manager
            # but since get_schedule_manager only needs request.app.state.db_path,
            # we can just instantiate it directly here.
            db_path = Path(DEFAULT_CONFIG["db_path"])
            schedule_path = db_path.parent / "schedule.json"
            from tradingagents.db.schedule_manager import ScheduleManager
            manager = ScheduleManager(schedule_path)
            
            due_jobs = manager.get_due_jobs()
            for job in due_jobs:
                logging.info(f"Adding scheduled job {job['id']} for {job['tickers']} to Research Queue")
                manager.mark_job_ran(job['id'])
                
                # We use today's date for scheduled runs
                today = datetime.now().strftime("%Y-%m-%d")
                
                # To address duplicate runs for the same ticker/date, 
                # we use force=True to ensure it overwrites.
                from tradingagents.db.registry import RunRegistry
                registry = RunRegistry(db_path)
                try:
                    job_data = {
                        "id": f"sch_{job['id']}_{today}",
                        "tickers": job["tickers"],
                        "dates": [today],
                        "provider": job["config"].get("llm_provider", "openai"),
                        "quick_model": job["config"].get("quick_think_llm", ""),
                        "deep_model": job["config"].get("deep_think_llm", ""),
                        "depth": job["config"].get("max_debate_rounds", 1),
                        "force": True
                    }
                    # Add to queue with priority=True to bump to top
                    registry.add_to_queue(job_data, priority=True)
                except Exception as e:
                    logging.error(f"Failed to queue scheduled job {job['id']}: {e}")
                finally:
                    registry.close()
        except Exception as e:
            logging.error(f"Error in scheduler loop: {e}")
            
        await asyncio.sleep(60)

@app.get("/api/health")
def health_check():
    """Simple health check endpoint."""
    return {"status": "ok", "db_path": app.state.db_path}

@app.get("/api/config")
def get_app_config():
    """Get the application configuration."""
    return {
        "llm_provider": DEFAULT_CONFIG.get("llm_provider"),
        "quick_think_llm": DEFAULT_CONFIG.get("quick_think_llm"),
        "deep_think_llm": DEFAULT_CONFIG.get("deep_think_llm")
    }

@app.get("/api/ollama/tags")
async def get_ollama_tags():
    """Fetch available models from local Ollama server."""
    # Try to resolve Ollama URL from .env, fallback to default
    ollama_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434/v1")
    mac_address = os.getenv("OLLAMA_MAC_ADDRESS")
    
    # SMART WAKE: Try to wake the server first (with a shorter "interactive" timeout)
    if mac_address:
        # We use a 15s timeout here so the UI doesn't hang too long
        # but gives the server a chance to wake.
        await ensure_ollama_ready(ollama_url, mac_address, timeout=15)
    
    # Convert /v1/chat or /v1 to base /api/tags for model listing
    base_url = ollama_url.split("/v1")[0]
    tags_url = f"{base_url}/api/tags"
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(tags_url, timeout=5.0)
            if response.status_code == 200:
                data = response.json()
                # Return just the model names for easier frontend usage
                return [m["name"] for m in data.get("models", [])]
            return []
    except Exception as e:
        logging.error(f"Failed to fetch Ollama tags: {e}")
        return []

# Serve static files from the frontend/dist directory
# This allows a single container to serve both the API and the UI
# Place this AFTER all API routes to avoid intercepting them
dist_path = Path("frontend/dist")
if dist_path.exists():
    app.mount("/", StaticFiles(directory=str(dist_path), html=True), name="frontend")
    
    @app.exception_handler(404)
    async def not_found_handler(request, exc):
        # For SPA (Single Page Application) routing support:
        # If a path isn't found in the API or StaticFiles, serve index.html
        return FileResponse(dist_path / "index.html")
else:
    logging.warning("Frontend dist directory not found. UI will not be served.")

if __name__ == "__main__":
    host = os.getenv("API_HOST", "127.0.0.1")
    port = int(os.getenv("API_PORT", 7101))
    reload = os.getenv("API_RELOAD", "true").lower() == "true"
    
    uvicorn.run("api.main:app", host=host, port=port, reload=reload)

