"""One-time migration: backfill config_id on existing runs and sync memory outcomes into DB.

Usage:
    python scripts/migrate_memory_to_db.py [--db PATH] [--memory PATH]

When run inside Docker:
    docker --context homenas exec trading-agents python scripts/migrate_memory_to_db.py
"""

import argparse
import os
import sys
from pathlib import Path

# Ensure the project root is on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tradingagents.db.registry import RunRegistry, make_config_id
from tradingagents.agents.utils.memory import TradingMemoryLog
from tradingagents.default_config import DEFAULT_CONFIG


def migrate(db_path: str, memory_path: str) -> None:
    registry = RunRegistry(db_path)

    # ── Step 1: Backfill config_id on all existing runs ──────────────
    rows = registry.conn.execute(
        "SELECT id, provider, quick_model, deep_model, depth FROM runs WHERE config_id IS NULL"
    ).fetchall()
    print(f"[1/3] Backfilling config_id on {len(rows)} runs...")
    for row in rows:
        cid = registry.get_or_create_config(
            row["provider"], row["quick_model"], row["deep_model"], row["depth"]
        )
        registry.conn.execute(
            "UPDATE runs SET config_id = ? WHERE id = ?", (cid, row["id"])
        )
    registry.conn.commit()
    print(f"      Done. Created {len(registry.list_configs())} config(s).")

    # ── Step 2: Sync resolved memory entries into runs ───────────────
    config = {**DEFAULT_CONFIG, "memory_log_path": memory_path}
    memory = TradingMemoryLog(config)
    entries = memory.load_entries()
    resolved = [e for e in entries if not e.get("pending") and e.get("raw")]
    print(f"[2/3] Syncing {len(resolved)} resolved memory entries to DB...")

    synced = 0
    for e in resolved:
        raw_str = e.get("raw", "0")
        alpha_str = e.get("alpha", "0")
        raw_val = float(raw_str.replace("%", "")) / 100 if raw_str else 0
        alpha_val = float(alpha_str.replace("%", "")) / 100 if alpha_str else 0
        holding_str = e.get("holding", "0d")
        holding_days = int(holding_str.replace("d", "")) if holding_str else 0

        quick = e.get("quick_model", "unknown")
        deep = e.get("deep_model", "unknown")
        depth_str = e.get("depth", "1")
        depth = int(depth_str) if depth_str.isdigit() else 1

        # Find matching run
        run = registry.find_run(
            ticker=e["ticker"],
            trade_date=e["date"],
            provider="ollama",  # all NAS runs are ollama
            quick_model=quick,
            deep_model=deep,
            depth=depth,
        )
        if run and run.get("outcome_status") != "resolved":
            runtime_str = e.get("runtime_sec", "0")
            try:
                runtime = float(runtime_str.rstrip("s"))
            except (ValueError, AttributeError):
                runtime = 0.0

            registry.conn.execute(
                """UPDATE runs SET
                       raw_return = ?, alpha_return = ?, holding_days = ?,
                       reflection = ?, runtime_sec = ?, outcome_status = 'resolved'
                   WHERE id = ?""",
                (raw_val, alpha_val, holding_days,
                 e.get("reflection", ""), runtime, run["id"]),
            )
            synced += 1

    registry.conn.commit()
    print(f"      Synced {synced} entries.")

    # ── Step 3: Mark remaining completed runs as outcome pending ─────
    updated = registry.conn.execute(
        """UPDATE runs SET outcome_status = 'pending'
           WHERE status = 'completed' AND outcome_status IS NULL"""
    ).rowcount
    registry.conn.commit()
    print(f"[3/3] Marked {updated} completed runs as outcome_status='pending'.")

    # Summary
    configs = registry.list_configs()
    total = registry.conn.execute("SELECT COUNT(*) FROM runs").fetchone()[0]
    resolved_count = registry.conn.execute(
        "SELECT COUNT(*) FROM runs WHERE outcome_status = 'resolved'"
    ).fetchone()[0]
    print(f"\n✓ Migration complete: {total} total runs, {resolved_count} resolved, {len(configs)} config(s)")
    for c in configs:
        print(f"  [{c['color']}] {c['label']}")

    registry.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Migrate memory log data into runs DB")
    parser.add_argument("--db", default=None, help="Path to tradingagents.db")
    parser.add_argument("--memory", default=None, help="Path to trading_memory.md")
    args = parser.parse_args()

    db = args.db or DEFAULT_CONFIG["db_path"]
    mem = args.memory or DEFAULT_CONFIG["memory_log_path"]

    print(f"DB:     {db}")
    print(f"Memory: {mem}")
    print()
    migrate(db, mem)
