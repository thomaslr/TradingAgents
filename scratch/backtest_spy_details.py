import sqlite3
import json
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

db_path = 'tradingagents_container.db'
conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row

configs = conn.execute('SELECT * FROM simulation_configs').fetchall()
results = []

for config in configs:
    config_id = config['config_id']
    label = config['label']
    
    runs = conn.execute(
        'SELECT trade_date, rating, action, raw_return FROM runs WHERE ticker = \'SPY\' AND status = \'completed\' AND outcome_status = \'resolved\' AND config_id = ? ORDER BY trade_date ASC',
        (config_id,)
    ).fetchall()
    
    if not runs:
        continue
        
    rating_counts = {'buy': 0, 'overweight': 0, 'hold': 0, 'underweight': 0, 'sell': 0, 'other': 0}
    for r in runs:
        rat = r['rating'].lower() if r['rating'] else ''
        if 'buy' in rat:
            rating_counts['buy'] += 1
        elif 'overweight' in rat:
            rating_counts['overweight'] += 1
        elif 'hold' in rat:
            rating_counts['hold'] += 1
        elif 'underweight' in rat:
            rating_counts['underweight'] += 1
        elif 'sell' in rat:
            rating_counts['sell'] += 1
        else:
            rating_counts['other'] += 1

    run_by_date = {r['trade_date']: r for r in runs}
    run_dates = sorted(list(run_by_date.keys()))
    
    start_date = run_dates[0]
    last_run_date = run_dates[-1]
    
    curr_end = last_run_date
    for _ in range(5):
        curr_end = get_next_weekday(curr_end)
    end_date = curr_end
    
    dataset_dates = get_weekdays_between(start_date, end_date)
    
    bench_val = 100.0
    strat_val = 100.0
    strat_a_val = 100.0
    strat_b_val = 100.0
    strat_c_val = 100.0
    
    bench_trades = []
    strat_trades = []
    
    state_a = 'CASH'
    weight_b = 0.0
    
    for idx, date in enumerate(dataset_dates):
        bench_trades = [t for t in bench_trades if idx < t['end_idx']]
        strat_trades = [t for t in strat_trades if idx < t['end_idx']]
        
        run = run_by_date.get(date)
        if run:
            raw_ret = run['raw_return']
            base_bench = max(0.0001, 1.0 + raw_ret)
            daily_bench_ret = (base_bench ** 0.2) - 1.0
            
            bench_trades.append({'end_idx': idx + 5, 'daily_return': daily_bench_ret})
            
            rating = run['rating'].lower() if run['rating'] else ''
            is_long = 'buy' in rating or 'overweight' in rating
            if is_long:
                strat_trades.append({'end_idx': idx + 5, 'daily_return': daily_bench_ret})
                
            if 'buy' in rating or 'overweight' in rating:
                state_a = 'LONG'
                weight_b = 1.5 if 'overweight' in rating else 1.0
            elif 'sell' in rating or 'underweight' in rating:
                state_a = 'CASH'
                weight_b = 0.5 if 'underweight' in rating else 0.0
            elif 'hold' in rating:
                pass
                
        bench_daily_ret = sum(t['daily_return'] for t in bench_trades) / 5.0
        strat_daily_ret = sum(t['daily_return'] for t in strat_trades) / 5.0
        
        weight_a = 1.0 if state_a == 'LONG' else 0.0
        strat_a_daily_ret = weight_a * bench_daily_ret
        
        strat_b_daily_ret = weight_b * bench_daily_ret
        
        if run:
            rating = run['rating'].lower() if run['rating'] else ''
            if 'buy' in rating:
                weight_c = 1.0
            elif 'overweight' in rating:
                weight_c = 1.5
            elif 'underweight' in rating:
                weight_c = 0.5
            elif 'sell' in rating:
                weight_c = 0.0
            else:
                weight_c = 1.0
        else:
            weight_c = 1.0
        strat_c_daily_ret = weight_c * bench_daily_ret
        
        bench_val *= (1.0 + bench_daily_ret)
        strat_val *= (1.0 + strat_daily_ret)
        strat_a_val *= (1.0 + strat_a_daily_ret)
        strat_b_val *= (1.0 + strat_b_daily_ret)
        strat_c_val *= (1.0 + strat_c_daily_ret)
        
    results.append({
        'label': label,
        'config_id': config_id,
        'bench_roi': bench_val - 100.0,
        'strat_roi': strat_val - 100.0,
        'strat_a_roi': strat_a_val - 100.0,
        'strat_b_roi': strat_b_val - 100.0,
        'strat_c_roi': strat_c_val - 100.0,
        'total_runs': len(runs),
        'rating_counts': rating_counts
    })

print(json.dumps(results, indent=2))
conn.close()
