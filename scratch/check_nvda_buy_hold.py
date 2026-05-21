import sqlite3
import pandas as pd
import os

db_path = os.path.expanduser("~/.tradingagents/tradingagents.db")
conn = sqlite3.connect(db_path)
query = """
    SELECT trade_date, ticker, raw_return
    FROM runs
    WHERE ticker = 'NVDA' AND status = 'completed' AND config_id = '76fe8ce626d8'
    ORDER BY trade_date ASC
"""
df = pd.read_sql_query(query, conn)
conn.close()

if df.empty:
    print("No data found")
    exit()

unique_dates = sorted(df['trade_date'].unique())
print(f"Total unique dates: {len(unique_dates)}")
print(f"Date range: {unique_dates[0]} to {unique_dates[-1]}")

# Cumulative return of daily raw_returns
# Wait! raw_return is the 5-day return of the stock starting on that date.
# Let's see how much NVDA went up in reality. We can get its close prices if they are in the DB or calculate from raw_returns.
# Wait, let's print the actual raw_returns for a few dates to see:
print("\nFirst 10 runs:")
print(df.head(10))

# Wait, let's see what the actual cumulative return would be if we entered a new trade every day.
# If we enter a new trade every day, we are always 100% invested (5 slots active).
# So the return should be the actual buy and hold return of the stock over the period!
# Let's calculate the compounded return of the daily returns (which is close_price(t+5) / close_price(t))?
# No, daily return of the stock is close_price(t+1) / close_price(t) - 1.
# Let's fetch close prices using yfinance!
import yfinance as yf
nvda = yf.Ticker("NVDA")
hist = nvda.history(start="2026-03-01", end="2026-05-15")
print("\nNVDA Actual Stock Price History:")
print(hist[['Close']].head(5))
print(hist[['Close']].tail(5))
start_price = hist['Close'].iloc[0]
end_price = hist['Close'].iloc[-1]
actual_bh_roi = (end_price / start_price - 1.0) * 100.0
print(f"\nActual NVDA Buy and Hold ROI (2026-03-02 to 2026-05-14): {actual_bh_roi:.2f}%")
