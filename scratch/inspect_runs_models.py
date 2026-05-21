import sqlite3
import os

db_path = os.path.expanduser("~/.tradingagents/tradingagents.db")
print("Connecting to DB:", db_path)
conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row

print("\n--- Unique Model Combinations in Runs Table ---")
query = """
    SELECT provider, quick_model, deep_model, depth, COUNT(*) as run_count
    FROM runs
    GROUP BY provider, quick_model, deep_model, depth
"""
rows = conn.execute(query).fetchall()
for r in rows:
    print(f"Provider: {r['provider']} | Quick: {r['quick_model']} | Deep: {r['deep_model']} | Depth: {r['depth']} | Run Count: {r['run_count']}")

print("\n--- All Unique Tickers in Runs Table ---")
tickers = conn.execute("SELECT ticker, COUNT(*) as run_count FROM runs GROUP BY ticker").fetchall()
for t in tickers:
    print(f"Ticker: {t['ticker']} | Run Count: {t['run_count']}")

conn.close()
