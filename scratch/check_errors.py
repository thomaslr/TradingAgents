import sqlite3
import os
from pathlib import Path

db_path = Path.home() / ".tradingagents" / "tradingagents.db"

if not db_path.exists():
    print(f"Database not found at {db_path}")
    exit(1)

conn = sqlite3.connect(str(db_path))
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

print(f"\nChecking LATEST failures (newest first)...\n")
# Get the last 5 failed runs
cursor.execute("SELECT id, ticker, trade_date, status, started_at, error_message FROM runs WHERE status = 'failed' ORDER BY id DESC LIMIT 5")
rows = cursor.fetchall()

if not rows:
    print("No failed runs found in the database.")
else:
    for row in rows:
        print(f"ID: {row['id']} | {row['ticker']} {row['trade_date']} | Started: {row['started_at']}")
        print(f"Error: {row['error_message']}\n")

conn.close()
