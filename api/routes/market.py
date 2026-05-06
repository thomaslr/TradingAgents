from fastapi import APIRouter, HTTPException, Query
import yfinance as yf
from typing import List, Dict, Any

router = APIRouter(prefix="/market", tags=["Market Data"])

@router.get("/ohlc/{ticker}")
def get_ohlc_data(
    ticker: str,
    period: str = Query("1y", description="Time period (e.g., 1mo, 6mo, 1y, 5y)"),
    interval: str = Query("1d", description="Time interval (e.g., 1d, 1wk)")
):
    """Fetch OHLC data for lightweight charts."""
    try:
        data = yf.download(ticker, period=period, interval=interval, progress=False)
        if data.empty:
            raise HTTPException(status_code=404, detail=f"No data found for {ticker}")
            
        # Format data for Lightweight Charts: 
        # Expected format: [{ time: '2019-04-11', open: 141.77, high: 142.15, low: 138.81, close: 140.41 }]
        # Also include volume: [{ time: '2019-04-11', value: 123456 }]
        
        # If single ticker, columns are 'Open', 'High', 'Low', 'Close', 'Volume'
        # If multi-ticker (shouldn't happen here, but handle just in case), columns are MultiIndex
        if isinstance(data.columns, pd.MultiIndex):
            # Just take the first ticker if it returned a multi-index unexpectedly
            ticker_data = data.xs(ticker, level=1, axis=1) if ticker in data.columns.levels[1] else data
        else:
            ticker_data = data
            
        # Reset index to get Date as a column
        df = ticker_data.reset_index()
        
        # Determine date column name (usually 'Date' or 'Datetime')
        date_col = 'Date' if 'Date' in df.columns else 'Datetime' if 'Datetime' in df.columns else df.columns[0]
        
        candles = []
        volumes = []
        
        for _, row in df.iterrows():
            # Format time as YYYY-MM-DD for daily data, or unix timestamp for intraday
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
            "period": period,
            "interval": interval,
            "candles": candles,
            "volumes": volumes
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

import pandas as pd # Needed for isinstance check
