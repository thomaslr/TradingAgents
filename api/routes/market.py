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
    period: Optional[str] = Query(None),
    start: Optional[str] = Query(None),
    end: Optional[str] = Query(None),
    interval: str = Query("1d")
):
    """Fetch OHLC data for lightweight charts."""
    try:
        t = yf.Ticker(ticker)
        
        # Priority: start/end strings
        if start and end:
            data = t.history(start=start, end=end, interval=interval)
            data = data.sort_index()
            # Ensure index is naive for precise slicing
            if data.index.tz is not None:
                data.index = data.index.tz_localize(None)
            data = data.loc[start:end]
        else:
            p = period if period else "1y"
            data = t.history(period=p, interval=interval)

        if data.empty:
            raise HTTPException(status_code=404, detail="No data")
            
        # Format data for Lightweight Charts
        df = data.reset_index()
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
            "period": period or "1y",
            "interval": interval,
            "candles": candles,
            "volumes": volumes
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error fetching OHLC for {ticker}")
        raise HTTPException(status_code=500, detail=str(e))
