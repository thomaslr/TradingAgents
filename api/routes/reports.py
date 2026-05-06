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
    """List all report files available for a given ticker and date."""
    base_dir = Path(config.get("results_dir", "reports")).expanduser()
    # Handle safe ticker format used by engine (just simple string usually)
    json_path = base_dir / ticker / "TradingAgentsStrategy_logs" / f"full_states_log_{date}.json"
    
    if not json_path.exists():
        raise HTTPException(status_code=404, detail=f"No reports found for {ticker} on {date}")
        
    # We return the available reports based on our static mapping
    return {"ticker": ticker, "date": date, "files": list(REPORT_MAPPINGS.keys())}

@router.get("/{ticker}/{date}/{filename}")
def get_report_content(ticker: str, date: str, filename: str, config: dict = Depends(get_config)):
    """Get the markdown content of a specific report file from the JSON state."""
    if filename not in REPORT_MAPPINGS:
        raise HTTPException(status_code=404, detail=f"Unknown report type: {filename}")
        
    base_dir = Path(config.get("results_dir", "reports")).expanduser()
    json_path = base_dir / ticker / "TradingAgentsStrategy_logs" / f"full_states_log_{date}.json"
    
    if not json_path.exists():
        raise HTTPException(status_code=404, detail=f"No reports found for {ticker} on {date}")
        
    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            
        key = REPORT_MAPPINGS[filename]
        content = data.get(key)
        
        if not content:
             content = f"No content available for {filename}."
             
        return {"filename": filename, "content": content}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error reading report: {str(e)}")
