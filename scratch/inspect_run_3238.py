import sqlite3
db_path = '/app/data/tradingagents.db'
conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row
r = conn.execute("SELECT * FROM runs WHERE id = 3238").fetchone()
print(dict(r))
conn.close()