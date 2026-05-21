import sqlite3
import os

db_path = os.path.expanduser("~/.tradingagents/tradingagents.db")
print("Connecting to DB:", db_path)
conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row

print("\n--- All Simulation Configs ---")
configs = conn.execute("SELECT * FROM simulation_configs").fetchall()
for c in configs:
    count = conn.execute("SELECT COUNT(*) FROM runs WHERE config_id = ?", (c["config_id"],)).fetchone()[0]
    completed = conn.execute("SELECT COUNT(*) FROM runs WHERE config_id = ? AND status = 'completed'", (c["config_id"],)).fetchone()[0]
    resolved = conn.execute("SELECT COUNT(*) FROM runs WHERE config_id = ? AND outcome_status = 'resolved'", (c["config_id"],)).fetchone()[0]
    print(f"ID: {c['config_id']} | Label: {c['label']} | Color: {c['color']}")
    print(f"  Provider: {c['provider']} | Quick: {c['quick_model']} | Deep: {c['deep_model']} | Depth: {c['depth']}")
    print(f"  Total Runs: {count} | Completed: {completed} | Resolved: {resolved}")

print("\n--- NVDA Runs ---")
runs = conn.execute("SELECT * FROM runs WHERE ticker = 'NVDA'").fetchall()
for r in runs:
    print(f"ID: {r['id']} | Date: {r['trade_date']} | Config: {r['config_id']} | Status: {r['status']} | Outcome: {r['outcome_status']}")
    print(f"  Rating: {r['rating']} | Action: {r['action']} | TimeHorizon: {r['time_horizon']}")
    print(f"  Raw Return: {r['raw_return']} | Alpha Return: {r['alpha_return']} | Holding Days: {r['holding_days']}")

conn.close()
