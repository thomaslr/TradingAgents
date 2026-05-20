import sqlite3
import pandas as pd
import os

db_path = os.path.expanduser("~/.tradingagents/tradingagents.db")
print("Connecting to DB:", db_path)
conn = sqlite3.connect(db_path)
query = """
    SELECT trade_date, ticker, raw_return, alpha_return, status, outcome_status, config_id
    FROM runs
    WHERE ticker = 'NVDA' AND status = 'completed'
    ORDER BY trade_date ASC
"""
df = pd.read_sql_query(query, conn)
print(df.to_string())
conn.close()
