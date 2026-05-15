import sqlite3
import json
import os
from pathlib import Path

db_path = r'c:\Users\rober\dev_win\TradingAgents\tradingagents.db'

print(f"Using DB: {db_path}")

if not os.path.exists(db_path):
    print("DB file not found!")
    exit(1)

conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

print("--- Research Queue ---")
try:
    cursor.execute("SELECT * FROM research_queue ORDER BY created_at DESC LIMIT 10")
    for row in cursor.fetchall():
        d = dict(row)
        print(d)
except Exception as e:
    print(f"Error reading research_queue: {e}")

print("\n--- Runs ---")
try:
    cursor.execute("SELECT * FROM runs ORDER BY id DESC LIMIT 10")
    for row in cursor.fetchall():
        print(dict(row))
except Exception as e:
    print(f"Error reading runs: {e}")

conn.close()
