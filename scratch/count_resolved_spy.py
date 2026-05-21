import sqlite3
db_path = '/app/data/tradingagents.db'
conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row
rows = conn.execute("SELECT config_id, COUNT(*) as cnt FROM runs WHERE ticker = 'SPY' AND status = 'completed' AND outcome_status = 'resolved' GROUP BY config_id").fetchall()
for r in rows:
    print(dict(r))
conn.close()