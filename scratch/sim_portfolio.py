import sqlite3
import pandas as pd
import numpy as np

# Connect to database
import os
db_path = os.path.expanduser("~/.tradingagents/tradingagents.db")
print("Connecting to DB:", db_path)
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
date_to_idx = {date: idx for idx, date in enumerate(unique_dates)}

print(f"Total unique dates: {len(unique_dates)}")
print(f"Date range: {unique_dates[0]} to {unique_dates[-1]}")

# Simulation parameters
holding_days = 5
num_slots = 5

# Let's simulate Benchmark (Hold NVDA) using overlapping slots
# Benchmark portfolio value: start with 100
bench_portfolio = 100
# Active benchmark trades list: each trade is [start_idx, end_idx, return, allocated_value]
bench_trades = []
bench_cash = 100

# Strategy portfolio value: start with 100
strat_portfolio = 100
# Active strategy trades list: each trade is [start_idx, end_idx, return, allocated_value]
strat_trades = []
strat_cash = 100

bench_history = []
strat_history = []

for idx, date in enumerate(unique_dates):
    # 1. Settle completed trades for Benchmark
    settled_bench_cash = 0
    remaining_bench_trades = []
    for trade in bench_trades:
        start_idx, end_idx, ret, alloc = trade
        if idx >= end_idx:
            # Settle at end_idx
            settled_bench_cash += alloc * (1 + ret)
        else:
            remaining_bench_trades.append(trade)
    bench_cash += settled_bench_cash
    bench_trades = remaining_bench_trades

    # 1b. Settle completed trades for Strategy
    settled_strat_cash = 0
    remaining_strat_trades = []
    for trade in strat_trades:
        start_idx, end_idx, ret, alloc = trade
        if idx >= end_idx:
            settled_strat_cash += alloc * (1 + ret)
        else:
            remaining_strat_trades.append(trade)
    strat_cash += settled_strat_cash
    strat_trades = remaining_strat_trades

    # Get data entries for this day
    day_entries = df[df['trade_date'] == date]
    
    # 2. Enter new trades
    if not day_entries.empty:
        entry = day_entries.iloc[0]
        raw_ret = entry['raw_return']
        
        # Benchmark always enters a trade
        # Benchmark uses 1/5 of the total portfolio value at entry
        bench_entry_alloc = (bench_cash + sum(t[3] for t in bench_trades)) / num_slots
        if bench_cash >= bench_entry_alloc:
            bench_cash -= bench_entry_alloc
            bench_trades.append([idx, idx + holding_days, raw_ret, bench_entry_alloc])

        # Strategy enters trade if Buy/Overweight
        rating = str(entry['rating']).lower() if pd.notna(entry['rating']) else ''
        action = str(entry['action']).lower() if pd.notna(entry['action']) else ''
        signal = rating if rating else action
        is_long = 'buy' in signal or 'overweight' in signal
        
        if is_long:
            strat_entry_alloc = (strat_cash + sum(t[3] for t in strat_trades)) / num_slots
            if strat_cash >= strat_entry_alloc:
                strat_cash -= strat_entry_alloc
                strat_trades.append([idx, idx + holding_days, raw_ret, strat_entry_alloc])

    # 3. Calculate current total value (with interpolation for active trades)
    current_bench_val = bench_cash
    for trade in bench_trades:
        start_idx, end_idx, ret, alloc = trade
        # Interpolate return linearly
        progress = min(1.0, (idx - start_idx) / holding_days)
        current_bench_val += alloc * (1 + ret * progress)

    current_strat_val = strat_cash
    for trade in strat_trades:
        start_idx, end_idx, ret, alloc = trade
        progress = min(1.0, (idx - start_idx) / holding_days)
        current_strat_val += alloc * (1 + ret * progress)

    bench_history.append((date, current_bench_val))
    strat_history.append((date, current_strat_val))

print(f"Final Benchmark Value: {bench_history[-1][1]:.2f} (ROI: {bench_history[-1][1]-100:.1f}%)")
print(f"Final Strategy Value: {strat_history[-1][1]:.2f} (ROI: {strat_history[-1][1]-100:.1f}%)")
