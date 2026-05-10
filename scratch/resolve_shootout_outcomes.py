import yfinance as yf
from datetime import datetime, timedelta
from tradingagents.agents.utils.memory import TradingMemoryLog
from tradingagents.default_config import DEFAULT_CONFIG

def resolve_outcomes():
    config = DEFAULT_CONFIG.copy()
    memory_log = TradingMemoryLog(config)
    pending = [e for e in memory_log.get_pending_entries() if e["ticker"] == "NVDA"]
    
    if not pending:
        print("No pending NVDA entries to resolve.")
        return

    print(f"Resolving outcomes for {len(pending)} NVDA entries...")
    updates = []
    
    for entry in pending:
        ticker = "NVDA"
        trade_date = entry["date"]
        holding_days = 5
        
        try:
            start = datetime.strptime(trade_date, "%Y-%m-%d")
            end = start + timedelta(days=holding_days + 7)
            end_str = end.strftime("%Y-%m-%d")

            stock = yf.Ticker(ticker).history(start=trade_date, end=end_str)
            spy = yf.Ticker("SPY").history(start=trade_date, end=end_str)

            if len(stock) < 2 or len(spy) < 2:
                continue

            actual_days = min(holding_days, len(stock) - 1, len(spy) - 1)
            raw = float((stock["Close"].iloc[actual_days] - stock["Close"].iloc[0]) / stock["Close"].iloc[0])
            spy_ret = float((spy["Close"].iloc[actual_days] - spy["Close"].iloc[0]) / spy["Close"].iloc[0])
            alpha = raw - spy_ret
            
            updates.append({
                "ticker": ticker,
                "trade_date": trade_date,
                "raw_return": raw,
                "alpha_return": alpha,
                "holding_days": actual_days,
                "reflection": "Shootout Sync: Outcome realized from historical data."
            })
            print(f"  [✓] Resolved {trade_date}: Alpha {alpha:+.1%}")
            
        except Exception as e:
            print(f"  [!] Failed {trade_date}: {e}")

    if updates:
        # We need to add batch_update_with_outcomes to memory.py or use update_with_outcome loop
        # For simplicity, let's use the loop
        for u in updates:
            memory_log.update_with_outcome(**u)
        print(f"Successfully realized {len(updates)} trades.")

if __name__ == "__main__":
    resolve_outcomes()
