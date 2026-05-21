import sqlite3
db_path = 'tradingagents_container.db'
conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row
config_id = '2de2f4219526'
rows = conn.execute('SELECT trade_date, rating, action FROM runs WHERE ticker = \'SPY\' AND status = \'completed\' AND outcome_status = \'resolved\' AND config_id = ?', (config_id,)).fetchall()
for r in rows:
    rat = r['rating']
    if rat != 'Hold':
        print(f"Date: {r['trade_date']} | Rating: {r['rating']} | Action: {r['action']}")
conn.close()
