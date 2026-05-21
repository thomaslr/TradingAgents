import sqlite3
db_path = 'tradingagents_container.db'
conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row
configs = ['9eab7031ab05', 'e6f82770959c', '3199b8420baa']
for cid in configs:
    runs = conn.execute('SELECT trade_date, raw_return FROM runs WHERE ticker = \'SPY\' AND status = \'completed\' AND outcome_status = \'resolved\' AND config_id = ? ORDER BY trade_date ASC', (cid,)).fetchall()
    dates = [r['trade_date'] for r in runs]
    print('Config:', cid, 'Total:', len(runs), 'Min Date:', dates[0], 'Max Date:', dates[-1])
    samples = runs[:3] + runs[-3:]
    sample_str = ', '.join([r['trade_date'] + ': ' + str(r['raw_return']) for r in samples])
    print('  Samples:', sample_str)
conn.close()
