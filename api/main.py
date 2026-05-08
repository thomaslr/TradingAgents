import os
import uvicorn
import asyncio
from datetime import datetime
from pathlib import Path
import httpx
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import logging

# Configure logging at the very top so all modules inherit the settings
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

from api.routes import runs, reports, market, analysis, schedule
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
                logging.info(f"Triggering scheduled job {job['id']} for {job['tickers']}")
                manager.mark_job_ran(job['id'])
                
                # Execute in the background using a thread (since it's blocking)
                # We use today's date for scheduled runs
                today = datetime.now().strftime("%Y-%m-%d")
                
                # We need a new registry per job
                registry = RunRegistry(db_path)
                try:
                    # To address duplicate runs for the same ticker/date, 
                    # we use force=True to ensure it overwrites.
                    await asyncio.to_thread(
                        run_batch_analysis,
                        tickers=job["tickers"],
                        dates=[today],
                        config=job["config"],
                        registry=registry,
                        skip_completed=False,
                        force=True
                    )
                except Exception as e:
                    logging.error(f"Scheduled job {job['id']} failed: {e}")
                finally:
                    registry.close()
        except Exception as e:
            logging.error(f"Error in scheduler loop: {e}")
            
        await asyncio.sleep(60)

@app.on_event("startup")
async def startup_event():
    asyncio.create_task(scheduler_loop())

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

if __name__ == "__main__":
    # Standard entry point for running directly
    uvicorn.run("api.main:app", host="127.0.0.1", port=6767, reload=True)
