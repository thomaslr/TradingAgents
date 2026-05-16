import sqlite3
import os
import json
import re
from pathlib import Path
from datetime import datetime

def recover():
    db_path = os.getenv("TRADINGAGENTS_DB_PATH", "/app/data/tradingagents.db")
    results_dir = os.getenv("TRADINGAGENTS_RESULTS_DIR", "/app/data/logs")
    
    if not os.path.exists(db_path):
        print(f"Error: Database not found at {db_path}")
        return

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    
    print(f"Starting recovery from {results_dir} into {db_path}")
    
    # We'll need to re-create configs too
    def get_or_create_config(provider, quick, deep, depth):
        config_id = f"{provider}_{quick}_{deep}_d{depth}".replace(":", "-").replace("/", "_")
        label = f"{quick} / {deep} d{depth}"
        
        # Pick a color
        colors = ["#10b981", "#6366f1", "#f59e0b", "#ef4444", "#8b5cf6"]
        
        conn.execute("""
            INSERT OR IGNORE INTO simulation_configs (config_id, provider, quick_model, deep_model, depth, label, color, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (config_id, provider, quick, deep, depth, label, colors[0], datetime.now().isoformat()))
        return config_id

    # Scan for tickers
    for ticker in os.listdir(results_dir):
        ticker_path = os.path.join(results_dir, ticker)
        if not os.path.isdir(ticker_path): continue
        
        print(f"Scanning {ticker}...")
        for date_str in os.listdir(ticker_path):
            date_path = os.path.join(ticker_path, date_str)
            if not os.path.isdir(date_path): continue
            
            # Find JSON files
            for filename in os.listdir(date_path):
                if not filename.endswith(".json"): continue
                
                file_path = os.path.join(date_path, filename)
                try:
                    with open(file_path, 'r') as f:
                        state = json.load(f)
                    
                    # Extract models from filename or state
                    # Filename pattern: quick_deep_depth_timestamp.json
                    # Example: llama3.2-3b_llama3.1-8b_d3_084354.json
                    parts = filename.replace(".json", "").split("_")
                    if len(parts) >= 3:
                        quick = parts[0].replace("-", ":")
                        deep = parts[1].replace("-", ":")
                        depth_str = parts[2].replace("d", "")
                        depth = int(depth_str) if depth_str.isdigit() else 1
                    else:
                        continue # Skip malformed filenames
                        
                    provider = "ollama" # Assuming ollama based on filenames
                    config_id = get_or_create_config(provider, quick, deep, depth)
                    
                    # Extract trading results
                    results = {}
                    final_decision = state.get("final_trade_decision", "")
                    rating_match = re.search(r"\*\*Rating\*\*:\s*(\w+)", final_decision)
                    results["rating"] = rating_match.group(1).capitalize() if rating_match else "Hold"
                    
                    trader_plan = state.get("trader_investment_plan", "")
                    if trader_plan:
                        action_match = re.search(r"\*\*Action\*\*:\s*(\w+)", trader_plan)
                        if action_match: results["action"] = action_match.group(1).capitalize()
                        
                        price_match = re.search(r"\*\*Entry Price\*\*:\s*([\d.]+)", trader_plan)
                        if price_match: results["entry_price"] = float(price_match.group(1))
                        
                        sl_match = re.search(r"\*\*Stop Loss\*\*:\s*([\d.]+)", trader_plan)
                        if sl_match: results["stop_loss"] = float(sl_match.group(1))
                        
                        tp_match = re.search(r"\*\*Price Target\*\*:\s*([\d.]+)", trader_plan)
                        if tp_match: results["price_target"] = float(tp_match.group(1))
                        
                    # Re-insert into runs
                    conn.execute("""
                        INSERT OR IGNORE INTO runs (
                            ticker, trade_date, provider, quick_model, deep_model, depth,
                            rating, action, entry_price, stop_loss, price_target,
                            status, outcome_status, report_dir, config_id, started_at, completed_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'completed', 'pending', ?, ?, ?, ?)
                    """, (
                        ticker, date_str, provider, quick, deep, depth,
                        results.get("rating"), results.get("action"), 
                        results.get("entry_price"), results.get("stop_loss"), results.get("price_target"),
                        date_path, config_id, datetime.now().isoformat(), datetime.now().isoformat()
                    ))
                    
                except Exception as e:
                    print(f"  Error recovering {file_path}: {e}")

    conn.commit()
    conn.close()
    print("Recovery complete.")

if __name__ == "__main__":
    recover()
