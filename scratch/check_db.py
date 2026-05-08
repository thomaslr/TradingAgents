import sqlite3
import os

db_path = os.path.expanduser("~/.tradingagents/tradingagents.db")
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

try:
    cursor.execute("SELECT id, ticker, trade_date, status, created_at FROM runs ORDER BY id DESC LIMIT 10;")
    rows = cursor.fetchall()
    print("ID | Ticker | Date | Status | Created At")
    print("-" * 60)
    for row in rows:
        print(f"{row[0]} | {row[1]} | {row[2]} | {row[3]} | {row[4]}")
except Exception as e:
    print(f"Error: {e}")
finally:
    conn.close()
