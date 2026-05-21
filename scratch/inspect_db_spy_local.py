import sqlite3
db_path = 'tradingagents_container.db'
conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row
configs = conn.execute('SELECT * FROM simulation_configs').fetchall()
for c in configs:
    config_id = c['config_id']
    label = c['label']
    total = conn.execute('SELECT COUNT(*) FROM runs WHERE ticker = \'SPY\' AND config_id = ?', (config_id,)).fetchone()[0]
    completed = conn.execute('SELECT COUNT(*) FROM runs WHERE ticker = \'SPY\' AND config_id = ? AND status = \'completed\' AND outcome_status = \'resolved\'', (config_id,)).fetchone()[0]
    print(f'ID: {config_id} | Label: {label} | Total: {total} | Completed/Resolved: {completed}')
conn.close()
