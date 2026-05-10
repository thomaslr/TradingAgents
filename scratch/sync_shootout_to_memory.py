import json
from pathlib import Path
from datetime import datetime
import os
from tradingagents.agents.utils.memory import TradingMemoryLog
from tradingagents.default_config import DEFAULT_CONFIG

def inject_nvda_history():
    # Use the same config as the app
    config = DEFAULT_CONFIG.copy()
    memory_log = TradingMemoryLog(config)
    
    # Path to where shootout reports are stored
    logs_root = Path(config["results_dir"]) / "NVDA"
    if not logs_root.exists():
        print(f"No logs found at {logs_root}")
        return

    print(f"Scanning {logs_root} for shootout results...")
    
    injected_count = 0
    # Walk through each date folder
    for date_dir in sorted(logs_root.iterdir()):
        if not date_dir.is_dir():
            continue
            
        trade_date = date_dir.name
        # Find the latest report for this date
        reports = sorted(date_dir.glob("*.json"))
        if not reports:
            continue
            
        latest_report = reports[-1]
        try:
            with open(latest_report, 'r', encoding='utf-8') as f:
                data = json.load(f)
                
            # Extract decision and metadata
            decision = data.get("final_trade_decision", "Hold")
            # Simulation metadata might be in the filename or the data
            # Format: {model}_{depth}_{timestamp}.json
            parts = latest_report.stem.split('_')
            quick = parts[0] if len(parts) > 0 else "unknown"
            deep = parts[1] if len(parts) > 1 else "unknown"
            depth_str = parts[2] if len(parts) > 2 else "d1"
            depth = int(depth_str[1:]) if depth_str.startswith('d') else 1
            
            # Use the existing store_decision logic
            memory_log.store_decision(
                ticker="NVDA",
                trade_date=trade_date,
                final_trade_decision=decision,
                quick_model=quick,
                deep_model=deep,
                depth=depth,
                runtime_sec=data.get("runtime_sec", 0.0)
            )
            injected_count += 1
            print(f"  [+] Injected NVDA {trade_date}")
            
        except Exception as e:
            print(f"  [!] Error processing {latest_report}: {e}")

    print(f"Done! Injected {injected_count} entries. Now triggering outcome updates...")
    
    # Now trigger the outcome update to move them from 'pending' to 'realized'
    # This requires price data, so we'll call the batch runner's resolver logic
    from tradingagents.graph.trading_graph import TradingAgentsGraph
    graph = TradingAgentsGraph(config)
    graph._resolve_pending_entries("NVDA")
    print("Outcomes resolved. NVDA should now appear on the Performance page.")

if __name__ == "__main__":
    inject_nvda_history()
