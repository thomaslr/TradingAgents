import sqlite3
import pandas as pd
import os

db_path = os.path.expanduser("~/.tradingagents/tradingagents.db")
conn = sqlite3.connect(db_path)
query = """
    SELECT trade_date, ticker, raw_return, alpha_return, rating, action, config_id
    FROM runs
    WHERE ticker = 'NVDA' AND status = 'completed' AND config_id = '3199b8420baa'
    ORDER BY trade_date ASC
"""
df = pd.read_sql_query(query, conn)
conn.close()

print("NVDA runs for config 3:")
print(df)

if df.empty:
    print("No data found")
    exit()

# Run TS-equivalent non-extended simulation
unique_dates = sorted(df['trade_date'].unique())
date_groups = {}
for _, row in df.iterrows():
    date = row['trade_date']
    if date not in date_groups:
        date_groups[date] = []
    date_groups[date].append(row)

total_slots = 5
bench_value = 100.0
strat_value = 100.0
bench_trades = []
strat_trades = []

for idx, date in enumerate(unique_dates):
    bench_trades = [t for t in bench_trades if idx < t['endIdx']]
    strat_trades = [t for t in strat_trades if idx < t['endIdx']]
    day_entries = date_groups.get(date, [])
    for entry in day_entries:
        raw_ret = entry['raw_return'] if entry['raw_return'] is not None else 0.0
        base_bench = max(0.0001, 1.0 + raw_ret)
        daily_bench_ret = (base_bench ** (1.0 / 5.0)) - 1.0
        bench_trades.append({'startIdx': idx, 'endIdx': idx + 5, 'dailyReturn': daily_bench_ret})
        rating = str(entry['rating']).lower() if entry['rating'] else ''
        if 'buy' in rating or 'overweight' in rating:
            strat_trades.append({'startIdx': idx, 'endIdx': idx + 5, 'dailyReturn': daily_bench_ret})
    bench_daily_ret = sum(t['dailyReturn'] for t in bench_trades) / total_slots
    strat_daily_ret = sum(t['dailyReturn'] for t in strat_trades) / total_slots
    bench_value *= (1.0 + bench_daily_ret)
    strat_value *= (1.0 + strat_daily_ret)

print(f"\nNon-extended Benchmark ROI: {bench_value-100.0:.2f}%")
print(f"Non-extended Strategy ROI: {strat_value-100.0:.2f}%")

# Run extended simulation
bench_value_ext = 100.0
strat_value_ext = 100.0
bench_trades_ext = []
strat_trades_ext = []
extended_dates = list(unique_dates) + [f"virtual-{i}" for i in range(1, 6)]

for idx, date in enumerate(extended_dates):
    bench_trades_ext = [t for t in bench_trades_ext if idx < t['endIdx']]
    strat_trades_ext = [t for t in strat_trades_ext if idx < t['endIdx']]
    if not date.startswith("virtual-"):
        day_entries = date_groups.get(date, [])
        for entry in day_entries:
            raw_ret = entry['raw_return'] if entry['raw_return'] is not None else 0.0
            base_bench = max(0.0001, 1.0 + raw_ret)
            daily_bench_ret = (base_bench ** (1.0 / 5.0)) - 1.0
            bench_trades_ext.append({'startIdx': idx, 'endIdx': idx + 5, 'dailyReturn': daily_bench_ret})
            rating = str(entry['rating']).lower() if entry['rating'] else ''
            if 'buy' in rating or 'overweight' in rating:
                strat_trades_ext.append({'startIdx': idx, 'endIdx': idx + 5, 'dailyReturn': daily_bench_ret})
    bench_daily_ret_ext = sum(t['dailyReturn'] for t in bench_trades_ext) / total_slots
    strat_daily_ret_ext = sum(t['dailyReturn'] for t in strat_trades_ext) / total_slots
    bench_value_ext *= (1.0 + bench_daily_ret_ext)
    strat_value_ext *= (1.0 + strat_daily_ret_ext)

print(f"Extended Benchmark ROI: {bench_value_ext-100.0:.2f}%")
print(f"Extended Strategy ROI: {strat_value_ext-100.0:.2f}%")
