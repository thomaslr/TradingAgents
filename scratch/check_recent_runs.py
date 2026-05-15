import sqlite3
import os

db_path = os.path.join(os.path.expanduser("~"), ".tradingagents", "tradingagents.db")

conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

print("Recent Runs (ID, Ticker, Date, Price, Status):")
cursor.execute("SELECT id, ticker, trade_date, close_price, status, error_message FROM runs ORDER BY id DESC LIMIT 20")
for row in cursor.fetchall():
    print(f"ID: {row['id']} | {row['ticker']} | {row['trade_date']} | Price: {row['close_price']} | Status: {row['status']} | Error: {row['error_message']}")

conn.close()
