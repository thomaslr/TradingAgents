import sqlite3
import os

db_path = os.path.expanduser("~/.tradingagents/tradingagents.db")
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

try:
    cursor.execute("PRAGMA table_info(runs);")
    columns = cursor.fetchall()
    print("Columns in 'runs' table:")
    for col in columns:
        print(f" - {col[1]} ({col[2]})")
        
    cursor.execute("SELECT * FROM runs ORDER BY id DESC LIMIT 5;")
    rows = cursor.fetchall()
    print("\nLast 5 rows:")
    for row in rows:
        print(row)
except Exception as e:
    print(f"Error: {e}")
finally:
    conn.close()
