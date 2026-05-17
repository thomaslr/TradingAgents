import os
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException
import json

from api.dependencies import get_config

router = APIRouter(prefix="/reports", tags=["Reports"])

REPORT_MAPPINGS = {
    "market_report.md": "market_report",
    "sentiment_report.md": "sentiment_report",
    "news_report.md": "news_report",
    "fundamentals_report.md": "fundamentals_report",
    "trader_plan.md": "trader_investment_decision",
    "investment_plan.md": "investment_plan",
    "final_decision.md": "final_trade_decision"
}

@router.get("/{ticker}/{date}")
def list_reports(ticker: str, date: str, config: dict = Depends(get_config)):
    """List all simulation IDs available for a given ticker and date."""
    base_dir = Path(config.get("results_dir", "reports")).expanduser()
    day_dir = base_dir / ticker / date
    
    legacy_path = base_dir / ticker / "TradingAgentsStrategy_logs" / f"full_states_log_{date}.json"

    if not day_dir.exists():
        if legacy_path.exists():
            return {
                "ticker": ticker, 
                "date": date, 
                "files": list(REPORT_MAPPINGS.keys()),
                "simulations": ["legacy"]
            }
        raise HTTPException(status_code=404, detail=f"No reports found for {ticker} on {date}")
        
    # List all .json files in the day directory
    sims = [p.stem for p in day_dir.glob("*.json")]
    return {
        "ticker": ticker, 
        "date": date, 
        "files": list(REPORT_MAPPINGS.keys()) if (sims or legacy_path.exists()) else [],
        "simulations": sorted(sims, reverse=True)
    }

@router.get("/{ticker}/{date}/{filename}")
def get_report_content(ticker: str, date: str, filename: str, sim_id: str = "legacy", config: dict = Depends(get_config)):
    """Get the markdown content of a specific report file from a simulation JSON."""
    if filename not in REPORT_MAPPINGS:
        raise HTTPException(status_code=404, detail=f"Unknown report type: {filename}")
        
    base_dir = Path(config.get("results_dir", "reports")).expanduser()
    
    if sim_id == "legacy":
        json_path = base_dir / ticker / "TradingAgentsStrategy_logs" / f"full_states_log_{date}.json"
        
        # If legacy path doesn't exist, try to find the newest simulation JSON in the ticker/date dir
        if not json_path.exists():
            day_dir = base_dir / ticker / date
            if day_dir.exists():
                sims = sorted([p for p in day_dir.glob("*.json")], key=os.path.getmtime, reverse=True)
                if sims:
                    json_path = sims[0]
                    sim_id = json_path.stem
    else:
        json_path = base_dir / ticker / date / f"{sim_id}.json"
    
    if not json_path.exists():
        raise HTTPException(status_code=404, detail=f"Simulation data not found for {ticker} on {date}")
        
    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            
        key = REPORT_MAPPINGS[filename]
        content = data.get(key)
        
        # Transparently resolve logical cache pointers if found
        if isinstance(content, dict) and content.get("cached") and content.get("shared_path"):
            shared_path = Path(content["shared_path"])
            if shared_path.exists():
                try:
                    with open(shared_path, 'r', encoding='utf-8') as sf:
                        shared_data = json.load(sf)
                        content = shared_data.get("report", f"Error: report key missing in cached file {shared_path}")
                except Exception as sf_err:
                    content = f"Error reading cached report: {str(sf_err)}"
            else:
                content = f"Cached report file not found at {shared_path}."
        
        if not content:
             content = f"No content available for {filename} in simulation {sim_id}."
             
        return {"filename": filename, "content": content, "sim_id": sim_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error reading report: {str(e)}")

