import sqlite3
db_path = 'tradingagents_container.db'
conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row
configs = conn.execute('SELECT * FROM simulation_configs').fetchall()
for c in configs:
    config_id = c['config_id']
    label = c['label']
    dates = conn.execute('SELECT MIN(trade_date), MAX(trade_date), COUNT(DISTINCT trade_date) FROM runs WHERE ticker = \'SPY\' AND config_id = ? AND status = \'completed\' AND outcome_status = \'resolved\'', (config_id,)).fetchone()
    print(f'ID: {config_id} | Label: {label} | Min: {dates[0]} | Max: {dates[1]} | Unique Dates: {dates[2]}')
conn.close()
