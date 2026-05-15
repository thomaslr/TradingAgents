import sqlite3
import os

db_path = os.path.join(os.path.expanduser("~"), ".tradingagents", "tradingagents.db")

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

print("Checking for concatenated dates in 'runs' table...")
cursor.execute("SELECT id, ticker, trade_date FROM runs WHERE LENGTH(trade_date) > 10")
rows = cursor.fetchall()
if not rows:
    print("No runs with trade_date length > 10 found.")
else:
    for row in rows:
        print(row)

print("\nChecking for concatenated dates in 'research_queue' table...")
# Note: research_queue.dates is a JSON list, so we search for long strings inside it
cursor.execute("SELECT id, dates FROM research_queue")
rows = cursor.fetchall()
found_q = False
for row in rows:
    if len(row[1]) > 30: # Typical JSON list ["YYYY-MM-DD", "YYYY-MM-DD"] is ~28 chars
        print(f"Suspiciously long dates field in queue job {row[0]}: {row[1]}")
        found_q = True
if not found_q:
    print("No suspiciously long dates found in research_queue.")

conn.close()
