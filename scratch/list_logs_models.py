import os
from pathlib import Path

logs_dir = os.path.expanduser("~/.tradingagents/logs")
print("Scanning logs dir:", logs_dir)

if not os.path.exists(logs_dir):
    print("Logs dir does not exist!")
    exit()

json_files = list(Path(logs_dir).rglob("*.json"))
print(f"Total JSON files: {len(json_files)}")

model_combinations = set()
for jf in json_files:
    # stem name format is usually: quick_deep_depth_timestamp or similar
    # Let's extract model combination from the parent dirs and filename
    # e.g., logs/NVDA/2026-05-05/llama3.2-3b_llama3.1-8b_d3_1714930200.json
    parts = jf.stem.split('_')
    if len(parts) >= 3:
        quick = parts[0]
        deep = parts[1]
        depth = parts[2]
        model_combinations.add((quick, deep, depth))

print("\nModel combinations found in JSON filenames:")
for qc, dp, dt in sorted(model_combinations):
    print(f"  Quick: {qc} | Deep: {dp} | Depth: {dt}")
