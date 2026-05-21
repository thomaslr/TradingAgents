import sqlite3
db_path = 'tradingagents_container.db'
conn = sqlite3.connect(db_path)
ratings = conn.execute('SELECT DISTINCT rating FROM runs WHERE ticker = \'SPY\'').fetchall()
print([r[0] for r in ratings])
conn.close()
