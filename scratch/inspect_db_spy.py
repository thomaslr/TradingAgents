import sqlite3
import os

db_path = '/app/data/tradingagents.db'
conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row

configs = conn.execute("SELECT * FROM simulation_configs").fetchall()
for c in configs:
    print(dict(c))

count = conn.execute("SELECT COUNT(*) FROM runs WHERE ticker = 'SPY'").fetchone()[0]
print(f"Total SPY runs: {count}")

spy_configs = conn.execute("SELECT DISTINCT config_id FROM runs WHERE ticker = 'SPY'").fetchall()
print(f"SPY configs: {[row['config_id'] for row in spy_configs]}")

conn.close()