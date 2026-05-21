import sqlite3
import pandas as pd
import os

db_path = os.path.expanduser("~/.tradingagents/tradingagents.db")
conn = sqlite3.connect(db_path)
query = """
    SELECT trade_date, ticker, raw_return, alpha_return, rating, action, config_id
    FROM runs
    WHERE ticker = 'NVDA' AND status = 'completed' AND config_id = '76fe8ce626d8'
    ORDER BY trade_date ASC
"""
df = pd.read_sql_query(query, conn)
conn.close()

if df.empty:
    print("No data found")
    exit()

unique_dates = sorted(df['trade_date'].unique())
print(f"Total unique dates: {len(unique_dates)}")

# Group entries by date
date_groups = {}
for _, row in df.iterrows():
    date = row['trade_date']
    if date not in date_groups:
        date_groups[date] = []
    date_groups[date].append(row)

# TypeScript parameters
total_slots = 5
bench_value = 100.0
strat_value = 100.0

bench_trades = []
strat_trades = []

# Extend the simulation dates by adding 5 virtual dates at the end
extended_dates = list(unique_dates)
for i in range(1, 6):
    extended_dates.append(f"virtual-{i}")

for idx, date in enumerate(extended_dates):
    # 1. Clear completed trades
    bench_trades = [t for t in bench_trades if idx < t['endIdx']]
    strat_trades = [t for t in strat_trades if idx < t['endIdx']]

    # 2. Add new trades starting today (only if it is a real date, not a virtual date)
    if not date.startswith("virtual-"):
        day_entries = date_groups.get(date, [])
        for entry in day_entries:
            raw_ret = entry['raw_return'] if entry['raw_return'] is not None else 0.0
            
            base_bench = max(0.0001, 1.0 + raw_ret)
            daily_bench_ret = (base_bench ** (1.0 / 5.0)) - 1.0
            
            bench_trades.append({
                'startIdx': idx,
                'endIdx': idx + 5,
                'dailyReturn': daily_bench_ret
            })
            
            rating = str(entry['rating']).lower() if entry['rating'] else ''
            is_long = 'buy' in rating or 'overweight' in rating
            
            if is_long:
                strat_trades.append({
                    'startIdx': idx,
                    'endIdx': idx + 5,
                    'dailyReturn': daily_bench_ret
                })

    # 3. Compute daily returns across all slots
    bench_daily_ret = sum(t['dailyReturn'] for t in bench_trades) / total_slots
    strat_daily_ret = sum(t['dailyReturn'] for t in strat_trades) / total_slots

    # 4. Compound
    bench_value = bench_value * (1.0 + bench_daily_ret)
    strat_value = strat_value * (1.0 + strat_daily_ret)

print(f"Final Benchmark ROI (Extended): {bench_value-100.0:.2f}%")
print(f"Final Strategy ROI (Extended): {strat_value-100.0:.2f}%")
