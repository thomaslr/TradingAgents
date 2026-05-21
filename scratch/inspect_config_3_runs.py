import sqlite3
import pandas as pd
import os

db_path = os.path.expanduser("~/.tradingagents/tradingagents.db")
conn = sqlite3.connect(db_path)
query = """
    SELECT id, ticker, trade_date, rating, action, status, outcome_status
    FROM runs
    WHERE config_id = '3199b8420baa'
    ORDER BY ticker, trade_date ASC
"""
df = pd.read_sql_query(query, conn)
print("Runs for config 3199b8420baa:")
print(df.to_string())
conn.close()
