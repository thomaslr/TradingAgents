"""SQLite-backed registry of analysis runs.

Tracks every analysis (interactive or batch) with its configuration,
trading output, and completion status.  The database lives at
``~/.tradingagents/tradingagents.db`` by default.
"""

from __future__ import annotations

import hashlib
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

CREATE TABLE IF NOT EXISTS simulation_configs (
    config_id   TEXT    PRIMARY KEY,
    provider    TEXT    NOT NULL,
    quick_model TEXT    NOT NULL,
    deep_model  TEXT    NOT NULL,
    depth       INTEGER NOT NULL,
    label       TEXT,
    color       TEXT,
    created_at  TEXT,
    UNIQUE(provider, quick_model, deep_model, depth)
);
"""

# Columns added after the initial schema.  Each entry is
# (column_name, column_definition).  _ensure_schema() will
# attempt to ALTER TABLE for any that are missing, which is
# safe and idempotent in SQLite.
_MIGRATION_COLUMNS = [
    ("config_id",       "TEXT"),
    ("raw_return",      "REAL"),
    ("alpha_return",    "REAL"),
    ("holding_days",    "INTEGER"),
    ("reflection",      "TEXT"),
    ("runtime_sec",     "REAL"),
    ("outcome_status",  "TEXT"),
]

# Preset palette for auto-assigning config colors (12 distinct hues)
_CONFIG_COLORS = [
    "#10b981",  # emerald
    "#6366f1",  # indigo
    "#f59e0b",  # amber
    "#ef4444",  # red
    "#8b5cf6",  # violet
    "#06b6d4",  # cyan
    "#ec4899",  # pink
    "#84cc16",  # lime
    "#f97316",  # orange
    "#14b8a6",  # teal
    "#a855f7",  # purple
    "#eab308",  # yellow
]


def _now_iso() -> str:
    """UTC timestamp in ISO-8601."""
    return datetime.now(timezone.utc).isoformat()


def make_config_id(provider: str, quick_model: str, deep_model: str, depth: int) -> str:
    """Deterministic short hash for a simulation configuration."""
    key = f"{provider}|{quick_model}|{deep_model}|{depth}"
    return hashlib.md5(key.encode()).hexdigest()[:12]


class RunRegistry:
    """Lightweight wrapper around a single ``runs`` table."""

    def __init__(self, db_path: str | Path) -> None:
        db_path = Path(db_path)
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self.db_path = db_path
        self.conn = sqlite3.connect(str(db_path), check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA journal_mode=WAL")
        self._ensure_schema()

    # ------------------------------------------------------------------
    # Schema
    # ------------------------------------------------------------------

    def _ensure_schema(self) -> None:
        self.conn.executescript(_SCHEMA_SQL)
        self.conn.commit()
        # Safe migration: add columns that don't exist yet
        for col_name, col_def in _MIGRATION_COLUMNS:
            try:
                self.conn.execute(
                    f"ALTER TABLE runs ADD COLUMN {col_name} {col_def}"
                )
                self.conn.commit()
            except sqlite3.OperationalError:
                # Column already exists — expected on subsequent runs
                pass

    # ------------------------------------------------------------------
    # Simulation Configs
    # ------------------------------------------------------------------

    def get_or_create_config(
        self,
        provider: str,
        quick_model: str,
        deep_model: str,
        depth: int,
    ) -> str:
        """Return config_id, creating the config row if needed."""
        config_id = make_config_id(provider, quick_model, deep_model, depth)
        existing = self.conn.execute(
            "SELECT config_id FROM simulation_configs WHERE config_id = ?",
            (config_id,),
        ).fetchone()
        if existing:
            return config_id

        # Auto-generate label and pick next color
        label = f"{quick_model} / {deep_model} d{depth}"
        count = self.conn.execute(
            "SELECT COUNT(*) FROM simulation_configs"
        ).fetchone()[0]
        color = _CONFIG_COLORS[count % len(_CONFIG_COLORS)]

        self.conn.execute(
            """INSERT OR IGNORE INTO simulation_configs
                   (config_id, provider, quick_model, deep_model, depth,
                    label, color, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (config_id, provider, quick_model, deep_model, depth,
             label, color, _now_iso()),
        )
        self.conn.commit()
        return config_id

    def list_configs(self) -> List[Dict[str, Any]]:
        """List all simulation configurations."""
        rows = self.conn.execute(
            "SELECT * FROM simulation_configs ORDER BY created_at"
        ).fetchall()
        return [dict(r) for r in rows]

    def update_config_label(self, config_id: str, label: str) -> None:
        """Update user-friendly label for a config."""
        self.conn.execute(
            "UPDATE simulation_configs SET label = ? WHERE config_id = ?",
            (label, config_id),
        )
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

    def list_runs_for_performance(
        self,
        ticker: Optional[str] = None,
        config_id: Optional[str] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        limit: int = 5000,
    ) -> List[Dict[str, Any]]:
        """List runs with resolved outcomes for the performance dashboard.

        Joins with simulation_configs to include label and color.
        Only returns runs where outcome_status = 'resolved'.
        """
        clauses = ["r.outcome_status = 'resolved'"]
        params: List[Any] = []
        if ticker:
            clauses.append("r.ticker = ?")
            params.append(ticker)
        if config_id:
            clauses.append("r.config_id = ?")
            params.append(config_id)
        if date_from:
            clauses.append("r.trade_date >= ?")
            params.append(date_from)
        if date_to:
            clauses.append("r.trade_date <= ?")
            params.append(date_to)

        where = f"WHERE {' AND '.join(clauses)}"
        rows = self.conn.execute(
            f"""SELECT r.*, sc.label AS config_label, sc.color AS config_color
                FROM runs r
                LEFT JOIN simulation_configs sc ON r.config_id = sc.config_id
                {where}
                ORDER BY r.trade_date ASC
                LIMIT ?""",
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
        # Ensure config exists and get its ID
        config_id = self.get_or_create_config(
            provider, quick_model, deep_model, depth
        )

        cur = self.conn.execute(
            """INSERT INTO runs
                   (ticker, trade_date, provider, quick_model, deep_model,
                    depth, status, started_at, report_dir, config_id,
                    outcome_status)
               VALUES (?, ?, ?, ?, ?, ?, 'pending', ?, ?, ?, 'pending')
               ON CONFLICT(ticker, trade_date, provider, quick_model, deep_model, depth)
               DO UPDATE SET
                   status = 'pending',
                   started_at = EXCLUDED.started_at,
                   report_dir = EXCLUDED.report_dir,
                   config_id  = EXCLUDED.config_id,
                   rating = NULL,
                   action = NULL,
                   entry_price = NULL,
                   stop_loss = NULL,
                   price_target = NULL,
                   position_sizing = NULL,
                   time_horizon = NULL,
                   close_price = NULL,
                   error_message = NULL,
                   completed_at = NULL,
                   raw_return = NULL,
                   alpha_return = NULL,
                   holding_days = NULL,
                   reflection = NULL,
                   runtime_sec = NULL,
                   outcome_status = 'pending'
            """,
            (ticker, trade_date, provider, quick_model, deep_model,
             depth, _now_iso(), report_dir, config_id),
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
                   close_price   = ?,
                   runtime_sec   = ?
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
                results.get("runtime_sec"),
                run_id,
            ),
        )
        self.conn.commit()

    def mark_outcome(
        self,
        run_id: int,
        raw_return: float,
        alpha_return: float,
        holding_days: int,
        reflection: str,
    ) -> None:
        """Update a completed run with its resolved outcome data."""
        self.conn.execute(
            """UPDATE runs SET
                   raw_return     = ?,
                   alpha_return   = ?,
                   holding_days   = ?,
                   reflection     = ?,
                   outcome_status = 'resolved'
               WHERE id = ?""",
            (raw_return, alpha_return, holding_days, reflection, run_id),
        )
        self.conn.commit()

    def mark_outcome_by_key(
        self,
        ticker: str,
        trade_date: str,
        provider: str,
        quick_model: str,
        deep_model: str,
        depth: int,
        raw_return: float,
        alpha_return: float,
        holding_days: int,
        reflection: str,
    ) -> bool:
        """Update outcome on a run matched by its unique key. Returns True if updated."""
        cur = self.conn.execute(
            """UPDATE runs SET
                   raw_return     = ?,
                   alpha_return   = ?,
                   holding_days   = ?,
                   reflection     = ?,
                   outcome_status = 'resolved'
               WHERE ticker = ? AND trade_date = ? AND provider = ?
                 AND quick_model = ? AND deep_model = ? AND depth = ?
                 AND status = 'completed'""",
            (raw_return, alpha_return, holding_days, reflection,
             ticker, trade_date, provider, quick_model, deep_model, depth),
        )
        self.conn.commit()
        return cur.rowcount > 0

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
