import os
import re

memory_path = os.path.expanduser("~/.tradingagents/memory/trading_memory.md")
print("Memory log path:", memory_path)

if not os.path.exists(memory_path):
    print("File does not exist")
    exit()

with open(memory_path, "r", encoding="utf-8") as f:
    content = f.read()

# Entries in trading_memory.md look like:
# [2026-05-08 | AAPL | Hold | pending] or similar header
# Let's find all headers:
headers = re.findall(r"\[(\d{4}-\d{2}-\d{2})\s*\|\s*([A-Za-z0-9]+)\s*\|\s*([^|\]]+)\s*\|\s*([^|\]]+)(?:\|\s*([^\]]+))?\]", content)

print(f"Total headers found: {len(headers)}")
nvda_entries = []
for h in headers:
    if h[1] == 'NVDA':
        nvda_entries.append(h)

print(f"\nFound {len(nvda_entries)} NVDA entries in memory log:")
for ne in nvda_entries:
    print(ne)

# Let's inspect the actual raw entries in the file
entry_blocks = content.split("<!-- ENTRY_END -->")
print(f"\nTotal entry blocks: {len(entry_blocks)}")

nvda_blocks = []
for block in entry_blocks:
    if "NVDA" in block[:200]:
        nvda_blocks.append(block)

print(f"\nNVDA blocks found: {len(nvda_blocks)}")
for i, block in enumerate(nvda_blocks):
    print(f"\n--- NVDA Block {i+1} ---")
    print(block[:500])
