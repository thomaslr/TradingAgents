"""Settle all pending run outcomes by fetching actual market returns and generating AI reflections.

This is a reusable script — run it anytime pending outcomes accumulate.

Usage:
    python scripts/settle_outcomes.py [--db PATH] [--no-reflections] [--holding-days N]

Docker (on NAS):
    docker --context homenas exec trading-agents python scripts/settle_outcomes.py
"""

import argparse
import os
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

# Ensure the project root is on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import yfinance as yf
from tradingagents.db.registry import RunRegistry
from tradingagents.default_config import DEFAULT_CONFIG


def fetch_returns(ticker: str, trade_date: str, holding_days: int = 5):
    """Fetch raw and alpha return for a ticker over holding_days from trade_date.

    Returns (raw_return, alpha_return, actual_holding_days) or (None, None, None).
    """
    try:
        start = datetime.strptime(trade_date, "%Y-%m-%d")
        end = start + timedelta(days=holding_days + 10)
        end_str = end.strftime("%Y-%m-%d")

        stock = yf.Ticker(ticker).history(start=trade_date, end=end_str)
        spy = yf.Ticker("SPY").history(start=trade_date, end=end_str)

        if len(stock) < 2 or len(spy) < 2:
            return None, None, None

        actual_days = min(holding_days, len(stock) - 1, len(spy) - 1)
        raw = float(
            (stock["Close"].iloc[actual_days] - stock["Close"].iloc[0])
            / stock["Close"].iloc[0]
        )
        spy_ret = float(
            (spy["Close"].iloc[actual_days] - spy["Close"].iloc[0])
            / spy["Close"].iloc[0]
        )
        alpha = raw - spy_ret
        return raw, alpha, actual_days
    except Exception as e:
        print(f"    ⚠ Price fetch failed for {ticker} on {trade_date}: {e}")
        return None, None, None


def create_reflector(config: dict):
    """Create a Reflector instance using the configured LLM."""
    try:
        from tradingagents.llm_clients import create_llm_client
        from tradingagents.graph.reflection import Reflector

        client = create_llm_client(
            provider=config["llm_provider"],
            model=config["quick_think_llm"],
            base_url=config.get("backend_url"),
        )
        return Reflector(client.get_llm())
    except Exception as e:
        print(f"⚠ Could not create reflector: {e}")
        return None


def settle_outcomes(db_path: str, holding_days: int, do_reflections: bool) -> None:
    registry = RunRegistry(db_path)

    # Find all pending outcomes
    pending = registry.conn.execute(
        """SELECT id, ticker, trade_date, rating, action, config_id
           FROM runs
           WHERE status = 'completed'
             AND (outcome_status = 'pending' OR outcome_status IS NULL)
           ORDER BY trade_date ASC"""
    ).fetchall()

    if not pending:
        print("✓ No pending outcomes to settle.")
        registry.close()
        return

    print(f"Found {len(pending)} pending outcomes to settle.")

    # Set up reflector if requested
    reflector = None
    if do_reflections:
        config = {**DEFAULT_CONFIG}
        # Check for env overrides
        ollama_url = os.getenv("OLLAMA_BASE_URL")
        if ollama_url:
            config["backend_url"] = ollama_url
        provider = os.getenv("LLM_PROVIDER", config.get("llm_provider", "ollama"))
        config["llm_provider"] = provider
        print(f"  LLM: {config['llm_provider']} / {config['quick_think_llm']}")
        reflector = create_reflector(config)
        if not reflector:
            print("  → Continuing without reflections")

    # Cache price data per ticker to avoid redundant yfinance calls
    resolved = 0
    skipped = 0
    failed = 0
    start_time = time.time()

    for i, row in enumerate(pending):
        run_id = row["id"]
        ticker = row["ticker"]
        trade_date = row["trade_date"]
        rating = row["rating"] or "Hold"

        pct = ((i + 1) / len(pending)) * 100
        print(f"  [{i+1}/{len(pending)}] ({pct:.0f}%) {ticker} {trade_date} ...", end=" ", flush=True)

        raw, alpha, days = fetch_returns(ticker, trade_date, holding_days)
        if raw is None:
            print("⏭ skipped (no price data)")
            skipped += 1
            continue

        # Generate reflection
        reflection = ""
        if reflector:
            try:
                decision_text = f"Rating: {rating}. Action: {row['action'] or 'N/A'}"
                reflection = reflector.reflect_on_final_decision(
                    final_decision=decision_text,
                    raw_return=raw,
                    alpha_return=alpha,
                )
            except Exception as e:
                print(f"(reflection failed: {e}) ", end="")

        registry.mark_outcome(run_id, raw, alpha, days, reflection)
        resolved += 1
        print(f"✓ raw={raw:+.2%} alpha={alpha:+.2%} ({days}d)")

    elapsed = time.time() - start_time
    time_str = f"{elapsed:.0f}s" if elapsed < 60 else f"{int(elapsed//60)}m {int(elapsed%60)}s"

    print(f"\n{'='*50}")
    print(f"✓ Settlement complete in {time_str}")
    print(f"  Resolved: {resolved}")
    print(f"  Skipped:  {skipped} (no price data yet)")
    print(f"  Failed:   {failed}")
    print(f"  Total:    {len(pending)}")

    registry.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Settle pending run outcomes")
    parser.add_argument("--db", default=None, help="Path to tradingagents.db")
    parser.add_argument("--no-reflections", action="store_true",
                        help="Skip AI reflections (faster)")
    parser.add_argument("--holding-days", type=int, default=5,
                        help="Number of trading days to hold (default: 5)")
    args = parser.parse_args()

    db = args.db or os.getenv("TRADINGAGENTS_DB_PATH", DEFAULT_CONFIG["db_path"])

    print(f"DB: {db}")
    print(f"Holding days: {args.holding_days}")
    print(f"Reflections: {'OFF' if args.no_reflections else 'ON'}")
    print()
    settle_outcomes(db, args.holding_days, not args.no_reflections)
