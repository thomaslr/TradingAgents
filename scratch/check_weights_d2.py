import sqlite3
db_path = 'tradingagents_container.db'
conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row
config_id = '2de2f4219526'
runs = conn.execute('SELECT trade_date, rating, action, raw_return FROM runs WHERE ticker = \'SPY\' AND status = \'completed\' AND outcome_status = \'resolved\' AND config_id = ? ORDER BY trade_date ASC', (config_id,)).fetchall()
run_by_date = {r['trade_date']: r for r in runs}
run_dates = sorted(list(run_by_date.keys()))
from datetime import datetime, timedelta
def get_next_weekday(date_str):
    d = datetime.strptime(date_str, '%Y-%m-%d')
    while True:
        d += timedelta(days=1)
        if d.weekday() < 5:
            return d.strftime('%Y-%m-%d')
def get_weekdays_between(start_str, end_str):
    curr = datetime.strptime(start_str, '%Y-%m-%d')
    end = datetime.strptime(end_str, '%Y-%m-%d')
    res = []
    while curr <= end:
        if curr.weekday() < 5:
            res.append(curr.strftime('%Y-%m-%d'))
        curr += timedelta(days=1)
    return res

curr_end = run_dates[-1]
for _ in range(5):
    curr_end = get_next_weekday(curr_end)
dataset_dates = get_weekdays_between(run_dates[0], curr_end)

state_a = 'CASH'
weight_b = 0.0

diffs = []
for idx, date in enumerate(dataset_dates):
    run = run_by_date.get(date)
    if run:
        rating = run['rating'].lower() if run['rating'] else ''
        if 'buy' in rating or 'overweight' in rating:
            state_a = 'LONG'
            weight_b = 1.5 if 'overweight' in rating else 1.0
        elif 'sell' in rating or 'underweight' in rating:
            state_a = 'CASH'
            weight_b = 0.5 if 'underweight' in rating else 0.0
    weight_a = 1.0 if state_a == 'LONG' else 0.0
    if weight_a != weight_b:
        diffs.append((date, run['rating'] if run else None, weight_a, weight_b))

print('Total differences in weights:', len(diffs))
for d in diffs[:10]:
    print(f'Date: {d[0]} | Rating: {d[1]} | Weight A: {d[2]} | Weight B: {d[3]}')
conn.close()
