import sqlite3
db_path = '/app/data/tradingagents.db'
conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row
rows = conn.execute("SELECT id, ticker, trade_date, config_id, rating, action FROM runs WHERE ticker = 'SPY' AND rating is NULL LIMIT 10").fetchall()
for r in rows:
    print(dict(r))
conn.close()