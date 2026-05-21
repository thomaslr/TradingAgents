import sqlite3
db_path = 'tradingagents_container.db'
conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row
configs = conn.execute('SELECT * FROM simulation_configs').fetchall()
for c in configs:
    cid = c['config_id']
    label = c['label']
    hdays = conn.execute('SELECT DISTINCT holding_days FROM runs WHERE ticker = \'SPY\' AND config_id = ?', (cid,)).fetchall()
    hdays_list = [row[0] for row in hdays]
    print(f'ID: {cid} | Label: {label} | Holding Days: {hdays_list}')
conn.close()
