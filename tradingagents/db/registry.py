"""SQLite-backed registry of analysis runs.

Tracks every analysis (interactive or batch) with its configuration,
trading output, and completion status.  The database lives at
``~/.tradingagents/tradingagents.db`` by default.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


_SCHEMA_SQL = """\
CREATE TABLE IF NOT EXISTS runs (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker          TEXT    NOT NULL,
    trade_date      TEXT    NOT NULL,
    provider        TEXT    NOT NULL,
    quick_model     TEXT    NOT NULL,
    deep_model      TEXT    NOT NULL,
    depth           INTEGER NOT NULL,
    -- Trading output (populated on completion)
    rating          TEXT,
    action          TEXT,
    entry_price     REAL,
    stop_loss       REAL,
    price_target    REAL,
    position_sizing TEXT,
    time_horizon    TEXT,
    close_price     REAL,
    -- Metadata
    status          TEXT    NOT NULL DEFAULT 'pending',
    error_message   TEXT,
    started_at      TEXT,
    completed_at    TEXT,
    report_dir      TEXT,
    UNIQUE(ticker, trade_date, provider, quick_model, deep_model, depth)
);
"""


def _now_iso() -> str:
    """UTC timestamp in ISO-8601."""
    return datetime.now(timezone.utc).isoformat()


class RunRegistry:
    """Lightweight wrapper around a single ``runs`` table."""

    def __init__(self, db_path: str | Path) -> None:
        db_path = Path(db_path)
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self.db_path = db_path
        self.conn = sqlite3.connect(str(db_path))
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA journal_mode=WAL")
        self._ensure_schema()

    # ------------------------------------------------------------------
    # Schema
    # ------------------------------------------------------------------

    def _ensure_schema(self) -> None:
        self.conn.executescript(_SCHEMA_SQL)
        self.conn.commit()

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def find_run(
        self,
        ticker: str,
        trade_date: str,
        provider: str,
        quick_model: str,
        deep_model: str,
        depth: int,
    ) -> Optional[Dict[str, Any]]:
        """Return the existing run row matching these exact params, or None."""
        row = self.conn.execute(
            """SELECT * FROM runs
               WHERE ticker = ? AND trade_date = ? AND provider = ?
                 AND quick_model = ? AND deep_model = ? AND depth = ?""",
            (ticker, trade_date, provider, quick_model, deep_model, depth),
        ).fetchone()
        return dict(row) if row else None

    def get_run(self, run_id: int) -> Optional[Dict[str, Any]]:
        """Return the run row by its ID."""
        row = self.conn.execute("SELECT * FROM runs WHERE id = ?", (run_id,)).fetchone()
        return dict(row) if row else None

    def list_runs(
        self,
        ticker: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """List runs with optional filters, newest first."""
        clauses: List[str] = []
        params: List[Any] = []
        if ticker:
            clauses.append("ticker = ?")
            params.append(ticker)
        if status:
            clauses.append("status = ?")
            params.append(status)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        rows = self.conn.execute(
            f"SELECT * FROM runs {where} ORDER BY id DESC LIMIT ?",
            params + [limit],
        ).fetchall()
        return [dict(r) for r in rows]

    # ------------------------------------------------------------------
    # Mutations
    # ------------------------------------------------------------------

    def create_run(
        self,
        ticker: str,
        trade_date: str,
        provider: str,
        quick_model: str,
        deep_model: str,
        depth: int,
        report_dir: Optional[str] = None,
    ) -> int:
        """Insert a new pending run. Returns the run ID."""
        cur = self.conn.execute(
            """INSERT INTO runs
                   (ticker, trade_date, provider, quick_model, deep_model,
                    depth, status, started_at, report_dir)
               VALUES (?, ?, ?, ?, ?, ?, 'pending', ?, ?)
               ON CONFLICT(ticker, trade_date, provider, quick_model, deep_model, depth)
               DO UPDATE SET
                   status = 'pending',
                   started_at = EXCLUDED.started_at,
                   report_dir = EXCLUDED.report_dir,
                   rating = NULL,
                   action = NULL,
                   entry_price = NULL,
                   stop_loss = NULL,
                   price_target = NULL,
                   position_sizing = NULL,
                   time_horizon = NULL,
                   close_price = NULL,
                   error_message = NULL,
                   completed_at = NULL
            """,
            (ticker, trade_date, provider, quick_model, deep_model,
             depth, _now_iso(), report_dir),
        )

        self.conn.commit()
        return cur.lastrowid  # type: ignore[return-value]

    def mark_running(self, run_id: int) -> None:
        self.conn.execute(
            "UPDATE runs SET status = 'running', started_at = ? WHERE id = ?",
            (_now_iso(), run_id),
        )
        self.conn.commit()

    def mark_completed(self, run_id: int, results: Dict[str, Any]) -> None:
        """Update a run with its trading results and mark as completed."""
        self.conn.execute(
            """UPDATE runs SET
                   status        = 'completed',
                   completed_at  = ?,
                   rating        = ?,
                   action        = ?,
                   entry_price   = ?,
                   stop_loss     = ?,
                   price_target  = ?,
                   position_sizing = ?,
                   time_horizon  = ?,
                   close_price   = ?
               WHERE id = ?""",
            (
                _now_iso(),
                results.get("rating"),
                results.get("action"),
                results.get("entry_price"),
                results.get("stop_loss"),
                results.get("price_target"),
                results.get("position_sizing"),
                results.get("time_horizon"),
                results.get("close_price"),
                run_id,
            ),
        )
        self.conn.commit()

    def mark_failed(self, run_id: int, error: str) -> None:
        self.conn.execute(
            """UPDATE runs SET status = 'failed', error_message = ?,
                   completed_at = ? WHERE id = ?""",
            (error, _now_iso(), run_id),
        )
        self.conn.commit()

    def delete_run(self, run_id: int) -> None:
        """Remove a run entry (used by --force to allow re-creation)."""
        self.conn.execute("DELETE FROM runs WHERE id = ?", (run_id,))
        self.conn.commit()

    def delete_runs_for_ticker_date(self, ticker: str, trade_date: str) -> None:
        """Remove all runs for a specific ticker and date."""
        self.conn.execute("DELETE FROM runs WHERE ticker = ? AND trade_date = ?", (ticker, trade_date))
        self.conn.commit()

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def close(self) -> None:
        self.conn.close()
