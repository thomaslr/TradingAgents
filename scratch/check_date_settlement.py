import sqlite3
db_path = 'tradingagents_container.db'
conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row
configs = ['9eab7031ab05', 'e6f82770959c', '3199b8420baa']
for cid in configs:
    print('CONFIG:', cid)
    rows = conn.execute('SELECT trade_date, raw_return, holding_days FROM runs WHERE ticker = \'SPY\' AND config_id = ? AND trade_date IN (\'2026-05-13\', \'2026-05-14\', \'2026-05-15\')', (cid,)).fetchall()
    for row in rows:
        print(f"  {row['trade_date']}: raw={row['raw_return']} holding_days={row['holding_days']}")
conn.close()
