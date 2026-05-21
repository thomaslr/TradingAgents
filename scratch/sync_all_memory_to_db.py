import os
import sys
import sqlite3
from datetime import datetime
from pathlib import Path

# Ensure project root is in sys.path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tradingagents.db.registry import RunRegistry
from tradingagents.agents.utils.memory import TradingMemoryLog
from tradingagents.default_config import DEFAULT_CONFIG

def normalize_model(model_name: str) -> str:
    """Normalize model names by replacing hyphens with colons if applicable."""
    if not model_name:
        return "unknown"
    # e.g., llama3.2-3b -> llama3.2:3b
    if "llama3.2-3b" in model_name:
        return "llama3.2:3b"
    if "llama3.1-8b" in model_name:
        return "llama3.1:8b"
    return model_name

def sync_all():
    db_path = DEFAULT_CONFIG["db_path"]
    memory_path = DEFAULT_CONFIG["memory_log_path"]
    
    print(f"DB Path: {db_path}")
    print(f"Memory Path: {memory_path}")
    
    registry = RunRegistry(db_path)
    memory_log = TradingMemoryLog({**DEFAULT_CONFIG, "memory_log_path": memory_path})
    
    entries = memory_log.load_entries()
    print(f"Loaded {len(entries)} entries from memory log.")
    
    created_count = 0
    updated_count = 0
    skipped_count = 0
    
    for i, e in enumerate(entries):
        ticker = e["ticker"]
        trade_date = e["date"]
        rating = e["rating"]
        is_pending = e["pending"]
        
        quick = normalize_model(e.get("quick_model", "unknown"))
        deep = normalize_model(e.get("deep_model", "unknown"))
        
        depth_str = e.get("depth", "1")
        try:
            depth = int(depth_str)
        except ValueError:
            depth = 1
            
        provider = "ollama"  # All NAS runs are ollama
        
        # Get or create config_id
        config_id = registry.get_or_create_config(provider, quick, deep, depth)
        
        # Parse returns
        raw_val = None
        alpha_val = None
        holding_days = None
        
        if not is_pending:
            raw_str = e.get("raw")
            alpha_str = e.get("alpha")
            holding_str = e.get("holding")
            
            try:
                raw_val = float(raw_str.replace("%", "")) / 100 if raw_str else 0.0
                alpha_val = float(alpha_str.replace("%", "")) / 100 if alpha_str else 0.0
                holding_days = int(holding_str.replace("d", "")) if holding_str else 5
            except Exception as err:
                print(f"  Error parsing returns for {ticker} on {trade_date}: {err}")
                raw_val = 0.0
                alpha_val = 0.0
                holding_days = 5
                
        runtime_str = e.get("runtime_sec", "0.0")
        try:
            runtime = float(runtime_str.rstrip("s"))
        except ValueError:
            runtime = 0.0
            
        reflection = e.get("reflection", "")
        decision = e.get("decision", "")
        
        # Check if run exists
        cursor = registry.conn.execute(
            """SELECT id, status, outcome_status, raw_return 
               FROM runs 
               WHERE ticker = ? AND trade_date = ? AND provider = ? 
                 AND quick_model = ? AND deep_model = ? AND depth = ?""",
            (ticker, trade_date, provider, quick, deep, depth)
        )
        row = cursor.fetchone()
        
        now_str = datetime.utcnow().isoformat() + "Z"
        
        if row is None:
            # Create run in DB
            registry.conn.execute(
                """INSERT INTO runs (
                    ticker, trade_date, provider, quick_model, deep_model, depth, config_id,
                    rating, action, status, outcome_status, raw_return, alpha_return, holding_days,
                    reflection, runtime_sec, started_at, completed_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'completed', ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    ticker, trade_date, provider, quick, deep, depth, config_id,
                    rating, rating, # Use rating as action fallback
                    'pending' if is_pending else 'resolved',
                    raw_val, alpha_val, holding_days,
                    reflection, runtime, now_str, now_str
                )
            )
            created_count += 1
        else:
            run_id = row[0]
            run_status = row[1]
            outcome_status = row[2]
            
            # If DB is pending but memory is resolved, update outcomes
            if not is_pending and outcome_status != 'resolved':
                registry.conn.execute(
                    """UPDATE runs SET
                           raw_return = ?,
                           alpha_return = ?,
                           holding_days = ?,
                           reflection = ?,
                           outcome_status = 'resolved',
                           status = 'completed'
                       WHERE id = ?""",
                    (raw_val, alpha_val, holding_days, reflection, run_id)
                )
                updated_count += 1
            else:
                skipped_count += 1
                
    registry.conn.commit()
    print(f"\nSync complete:")
    print(f"  Created runs: {created_count}")
    print(f"  Updated runs: {updated_count}")
    print(f"  Skipped runs: {skipped_count}")
    
    registry.close()

if __name__ == "__main__":
    sync_all()
