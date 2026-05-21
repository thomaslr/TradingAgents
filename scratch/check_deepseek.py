import os

memory_path = os.path.expanduser("~/.tradingagents/memory/trading_memory.md")
print("Reading memory log:", memory_path)

if not os.path.exists(memory_path):
    print("Memory log does not exist!")
    exit()

with open(memory_path, "r", encoding="utf-8") as f:
    content = f.read()

import re
matches = re.findall(r"\[([^\]]*deepseek[^\]]*)\]", content, re.IGNORECASE)
print(f"Found {len(matches)} matching headers:")
for m in matches[:10]:
    print(m)
