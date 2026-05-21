import sqlite3
import os

db_path = os.path.expanduser("~/.tradingagents/tradingagents.db")
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = [row[0] for row in cursor.fetchall()]
print("Tables in DB:", tables)

if "runs" in tables:
    cursor.execute("SELECT DISTINCT deep_model FROM runs")
    deep_models = [row[0] for row in cursor.fetchall()]
    print("Distinct deep models in runs:", deep_models)
    
    cursor.execute("SELECT DISTINCT quick_model FROM runs")
    quick_models = [row[0] for row in cursor.fetchall()]
    print("Distinct quick models in runs:", quick_models)

if "simulation_configs" in tables:
    cursor.execute("SELECT DISTINCT deep_model, quick_model FROM simulation_configs")
    configs = cursor.fetchall()
    print("Configs in simulation_configs:", configs)

conn.close()
