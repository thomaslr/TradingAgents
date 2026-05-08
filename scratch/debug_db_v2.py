import sqlite3
import os

db_path = os.path.expanduser("~/.tradingagents/tradingagents.db")
conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

try:
    cursor.execute("SELECT COUNT(*) FROM runs;")
    count = cursor.fetchone()[0]
    print(f"Total runs in DB: {count}")
    
    cursor.execute("SELECT * FROM runs ORDER BY id DESC LIMIT 10;")
    rows = cursor.fetchall()
    print("\nLast 10 runs:")
    for row in rows:
        print(f"ID: {row['id']} | Ticker: {row['ticker']} | Date: {row['trade_date']} | Status: {row['status']} | Error: {row['error_message']}")
except Exception as e:
    print(f"Error: {e}")
finally:
    conn.close()
