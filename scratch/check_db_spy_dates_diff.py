import sqlite3
db_path = 'tradingagents_container.db'
conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row
c1 = '2de2f4219526'
c2 = '3199b8420baa'
r1 = conn.execute('SELECT trade_date FROM runs WHERE ticker = \'SPY\' AND status = \'completed\' AND outcome_status = \'resolved\' AND config_id = ?', (c1,)).fetchall()
r2 = conn.execute('SELECT trade_date FROM runs WHERE ticker = \'SPY\' AND status = \'completed\' AND outcome_status = \'resolved\' AND config_id = ?', (c2,)).fetchall()
d1 = set(r['trade_date'] for r in r1)
d2 = set(r['trade_date'] for r in r2)
print('In c1 but not c2:', sorted(list(d1 - d2)))
print('In c2 but not c1:', sorted(list(d2 - d1)))
conn.close()
