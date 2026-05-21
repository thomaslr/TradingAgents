import os

memory_path = os.path.expanduser("~/.tradingagents/memory/trading_memory.md")
print("Memory log path:", memory_path)
if os.path.exists(memory_path):
    print("File size:", os.path.getsize(memory_path), "bytes")
    with open(memory_path, "r", encoding="utf-8") as f:
        content = f.read()
    # Print the first 1000 chars and the last 1000 chars of the file to see what it contains
    print("\n--- First 1000 chars ---")
    print(content[:1000])
    print("\n--- Last 1000 chars ---")
    print(content[-1000:])
else:
    print("Memory log file does not exist!")
