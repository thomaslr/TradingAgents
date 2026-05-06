import os
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import logging

from api.routes import runs, reports, market, analysis
from tradingagents.default_config import DEFAULT_CONFIG

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

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

@app.get("/api/health")
def health_check():
    """Simple health check endpoint."""
    return {"status": "ok", "db_path": app.state.db_path}

if __name__ == "__main__":
    # Standard entry point for running directly
    uvicorn.run("api.main:app", host="127.0.0.1", port=6767, reload=True)
