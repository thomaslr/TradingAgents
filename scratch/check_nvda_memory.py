import os
import re
from collections import Counter

memory_path = os.path.expanduser("~/.tradingagents/memory/trading_memory.md")
print("Reading memory log:", memory_path)

if not os.path.exists(memory_path):
    print("Memory log does not exist!")
    exit()

with open(memory_path, "r", encoding="utf-8") as f:
    content = f.read()

# Match entries
# Pattern can match both:
# [date | ticker | rating | pending | quick | deep | depth | runtime]
# and
# [date | ticker | rating | raw_ret | alpha_ret | holding | quick | deep | depth | runtime]
pattern = r"\[([^\]]+)\]"
headers = re.findall(pattern, content)

nvda_entries = []
for h in headers:
    parts = [p.strip() for p in h.split("|")]
    if len(parts) >= 4 and parts[1] == "NVDA":
        nvda_entries.append(parts)

print(f"Total NVDA entries in memory log: {len(nvda_entries)}")

# Group by config and status
configs = Counter()
status_counts = Counter()
by_date_and_config = {}

for entry in nvda_entries:
    # entry could be:
    # [date, ticker, rating, pending, quick, deep, depth, runtime] -> len 8
    # or [date, ticker, rating, raw_ret, alpha_ret, holding, quick, deep, depth, runtime] -> len 10
    date = entry[0]
    ticker = entry[1]
    rating = entry[2]
    
    if "pending" in entry[3]:
        status = "pending"
        quick = entry[4] if len(entry) > 4 else "unknown"
        deep = entry[5] if len(entry) > 5 else "unknown"
        depth = entry[6] if len(entry) > 6 else "1"
    else:
        status = "resolved"
        quick = entry[6] if len(entry) > 6 else "unknown"
        deep = entry[7] if len(entry) > 7 else "unknown"
        depth = entry[8] if len(entry) > 8 else "1"
        
    config_key = f"{quick} / {deep} d{depth}"
    configs[config_key] += 1
    status_counts[status] += 1
    
    key = (date, config_key)
    if key not in by_date_and_config:
        by_date_and_config[key] = []
    by_date_and_config[key].append((rating, status, entry))

print("\nCounts by Configuration:")
for config, count in configs.items():
    print(f"  {config}: {count} entries")

print("\nCounts by Status:")
for status, count in status_counts.items():
    print(f"  {status}: {count} entries")

print("\nRecent entries:")
for (date, config), entries in sorted(by_date_and_config.items(), key=lambda x: (x[0][0], x[0][1]))[-10:]:
    for rating, status, raw in entries:
        print(f"  {date} | {config} | Rating: {rating} | Status: {status} | Raw: {raw}")
