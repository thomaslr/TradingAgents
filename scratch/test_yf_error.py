import yfinance as yf
import sys

symbol = "AAPL"
try:
    ticker = yf.Ticker(symbol)
    print(f"Fetching info for {symbol}...")
    info = ticker.info
    print("Success!")
except Exception as e:
    print(f"Caught exception: {type(e).__name__}: {e}")
    # Print the module where the exception is defined if possible
    print(f"Module: {getattr(e, '__module__', 'Unknown')}")
