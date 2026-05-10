from fastapi import APIRouter, HTTPException, Query
import yfinance as yf
import pandas as pd
from typing import List, Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/market", tags=["Market Data"])

@router.get("/ohlc/{ticker}")
def get_ohlc_data(
    ticker: str,
    period: Optional[str] = Query(None, description="Time period (e.g., 1mo, 6mo, 1y, 5y)"),
    start: Optional[str] = Query(None, description="Start date (YYYY-MM-DD)"),
    end: Optional[str] = Query(None, description="End date (YYYY-MM-DD)"),
    interval: str = Query("1d", description="Time interval (e.g., 1d, 1wk)")
):
    """Fetch OHLC data for lightweight charts."""
    try:
        # Normalize inputs
        start_str = start.strip() if start and start.strip() else None
        end_str = end.strip() if end and end.strip() else None
        period_val = period if period else "1y"

        logger.info(f"OHLC Request: {ticker} | Start: {start_str} | End: {end_str} | Period: {period_val}")

        if start_str and end_str:
            data = yf.download(ticker, start=start_str, end=end_str, interval=interval, progress=False)
        else:
            data = yf.download(ticker, period=period_val, interval=interval, progress=False)

        if data.empty:
            logger.warning(f"No OHLC data found for {ticker} with current params")
            raise HTTPException(status_code=404, detail=f"No data found for {ticker}")
            
        # Format data for Lightweight Charts
        if isinstance(data.columns, pd.MultiIndex):
            ticker_data = data.xs(ticker, level=1, axis=1) if ticker in data.columns.levels[1] else data
        else:
            ticker_data = data
            
        df = ticker_data.reset_index()
        date_col = 'Date' if 'Date' in df.columns else 'Datetime' if 'Datetime' in df.columns else df.columns[0]
        
        candles = []
        volumes = []
        
        for _, row in df.iterrows():
            time_val = row[date_col].strftime('%Y-%m-%d') if interval.endswith('d') or interval.endswith('wk') or interval.endswith('mo') else int(row[date_col].timestamp())
            
            candles.append({
                "time": time_val,
                "open": float(row['Open']),
                "high": float(row['High']),
                "low": float(row['Low']),
                "close": float(row['Close'])
            })
            
            volumes.append({
                "time": time_val,
                "value": float(row['Volume'])
            })
            
        return {
            "ticker": ticker,
            "period": period_val,
            "interval": interval,
            "candles": candles,
            "volumes": volumes
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Unexpected error fetching OHLC for {ticker}")
        raise HTTPException(status_code=500, detail=str(e))
