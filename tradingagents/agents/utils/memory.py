"""Append-only markdown decision log for TradingAgents."""

from typing import List, Optional
from pathlib import Path
import re

from tradingagents.agents.utils.rating import parse_rating


class TradingMemoryLog:
    """Append-only markdown log of trading decisions and reflections."""

    # HTML comment: cannot appear in LLM prose output, safe as a hard delimiter
    _SEPARATOR = "\n\n<!-- ENTRY_END -->\n\n"
    # Precompiled patterns — avoids re-compilation on every load_entries() call
    _DECISION_RE = re.compile(r"DECISION:\n(.*?)(?=\nREFLECTION:|\Z)", re.DOTALL)
    _REFLECTION_RE = re.compile(r"REFLECTION:\n(.*?)$", re.DOTALL)

    def __init__(self, config: dict = None):
        cfg = config or {}
        self._log_path = None
        path = cfg.get("memory_log_path")
        if path:
            self._log_path = Path(path).expanduser()
            self._log_path.parent.mkdir(parents=True, exist_ok=True)
        # Optional cap on resolved entries. None disables rotation.
        self._max_entries = cfg.get("memory_log_max_entries")

    # --- Write path (Phase A) ---

    def store_decision(
        self,
        ticker: str,
        trade_date: str,
        final_trade_decision: str,
        quick_model: str = "unknown",
        deep_model: str = "unknown",
        depth: int = 1,
        runtime_sec: float = 0.0
    ) -> None:
        """Append pending entry at end of propagate(). No LLM call."""
        if not self._log_path:
            return
            
        rating = parse_rating(final_trade_decision)
        # Store metadata in the tag: [date | ticker | rating | pending | quick | deep | depth | runtime]
        tag = f"[{trade_date} | {ticker} | {rating} | pending | {quick_model} | {deep_model} | {depth} | {runtime_sec:.1f}s]"
        entry = f"{tag}\n\nDECISION:\n{final_trade_decision}{self._SEPARATOR}"
        with open(self._log_path, "a", encoding="utf-8") as f:
            f.write(entry)


    # --- Read path (Phase A) ---

    def load_entries(self) -> List[dict]:
        """Parse all entries from log. Returns list of dicts."""
        if not self._log_path or not self._log_path.exists():
            return []
        text = self._log_path.read_text(encoding="utf-8")
        raw_entries = [e.strip() for e in text.split(self._SEPARATOR) if e.strip()]
        entries = []
        for raw in raw_entries:
            parsed = self._parse_entry(raw)
            if parsed:
                entries.append(parsed)
        return entries

    def get_pending_entries(self) -> List[dict]:
        """Return entries with outcome:pending (for Phase B)."""
        return [e for e in self.load_entries() if e.get("pending")]

    def get_past_context(self, ticker: str, n_same: int = 5, n_cross: int = 3) -> str:
        """Return formatted past context string for agent prompt injection."""
        entries = [e for e in self.load_entries() if not e.get("pending")]
        if not entries:
            return ""

        same, cross = [], []
        for e in reversed(entries):
            if len(same) >= n_same and len(cross) >= n_cross:
                break
            if e["ticker"] == ticker and len(same) < n_same:
                same.append(e)
            elif e["ticker"] != ticker and len(cross) < n_cross:
                cross.append(e)

        if not same and not cross:
            return ""

        parts = []
        if same:
            parts.append(f"Past analyses of {ticker} (most recent first):")
            parts.extend(self._format_full(e) for e in same)
        if cross:
            parts.append("Recent cross-ticker lessons:")
            parts.extend(self._format_reflection_only(e) for e in cross)
        return "\n\n".join(parts)

    # --- Update path (Phase B) ---

    def update_with_outcome(
        self,
        ticker: str,
        trade_date: str,
        raw_return: float,
        alpha_return: float,
        holding_days: int,
        reflection: str,
    ) -> None:
        """Replace pending tag and append REFLECTION section using atomic write.

        Finds the first pending entry matching (trade_date, ticker), updates
        its tag with return figures, and appends a REFLECTION section.  Uses
        a temp-file + os.replace() so a crash mid-write never corrupts the log.
        """
        if not self._log_path or not self._log_path.exists():
            return

        text = self._log_path.read_text(encoding="utf-8")
        blocks = text.split(self._SEPARATOR)

        pending_prefix = f"[{trade_date} | {ticker} |"
        raw_pct = f"{raw_return:+.1%}"
        alpha_pct = f"{alpha_return:+.1%}"

        updated = False
        new_blocks = []
        for block in blocks:
            stripped = block.strip()
            if not stripped:
                new_blocks.append(block)
                continue

            lines = stripped.splitlines()
            tag_line = lines[0].strip()

            if (
                not updated
                and tag_line.startswith(pending_prefix)
                and " | pending" in tag_line
            ):

                # Parse fields from the existing pending tag
                fields = [f.strip() for f in tag_line[1:-1].split("|")]
                rating = fields[2]
                
                # Reconstruct tag with outcomes, preserving any extra research metadata (model, depth, etc.)
                new_fields = [trade_date, ticker, rating, raw_pct, alpha_pct, f"{holding_days}d"]
                if len(fields) > 4:
                    # Append everything after the original 'pending' marker
                    new_fields.extend(fields[4:])
                
                new_tag = "[" + " | ".join(new_fields) + "]"

                rest = "\n".join(lines[1:])
                new_blocks.append(
                    f"{new_tag}\n\n{rest.lstrip()}\n\nREFLECTION:\n{reflection}"
                )
                updated = True
            else:
                new_blocks.append(block)

        if not updated:
            return

        new_blocks = self._apply_rotation(new_blocks)
        new_text = self._SEPARATOR.join(new_blocks)
        tmp_path = self._log_path.with_suffix(".tmp")
        tmp_path.write_text(new_text, encoding="utf-8")
        tmp_path.replace(self._log_path)

    def batch_update_with_outcomes(self, updates: List[dict]) -> None:
        """Apply multiple outcome updates in a single read + atomic write.

        Each element of updates must have keys: ticker, trade_date,
        raw_return, alpha_return, holding_days, reflection.
        """
        if not self._log_path or not self._log_path.exists() or not updates:
            return

        text = self._log_path.read_text(encoding="utf-8")
        blocks = text.split(self._SEPARATOR)

        # Build lookup keyed by configuration parameters to uniquely identify matching blocks
        update_map = {}
        for u in updates:
            key = (
                u["trade_date"],
                u["ticker"],
                u.get("quick_model", "unknown"),
                u.get("deep_model", "unknown"),
                str(u.get("depth", "1"))
            )
            update_map[key] = u

        new_blocks = []
        for block in blocks:
            stripped = block.strip()
            if not stripped:
                new_blocks.append(block)
                continue

            lines = stripped.splitlines()
            tag_line = lines[0].strip()

            matched = False
            if tag_line.startswith("[") and (" | pending" in tag_line or tag_line.endswith("| pending]")):
                fields = [f.strip() for f in tag_line[1:-1].split("|")]
                if len(fields) >= 4:
                    block_date = fields[0]
                    block_ticker = fields[1]
                    block_quick = fields[4] if len(fields) > 4 else "unknown"
                    block_deep = fields[5] if len(fields) > 5 else "unknown"
                    block_depth = fields[6] if len(fields) > 6 else "1"
                    
                    key = (block_date, block_ticker, block_quick, block_deep, block_depth)
                    if key in update_map:
                        upd = update_map[key]
                        rating = fields[2]
                        raw_pct = f"{upd['raw_return']:+.1%}"
                        alpha_pct = f"{upd['alpha_return']:+.1%}"
                        
                        # Preserve metadata fields after the outcome fields:
                        # [date | ticker | rating | raw | alpha | holding | quick_model | deep_model | depth | runtime]
                        new_fields = [
                            block_date,
                            block_ticker,
                            rating,
                            raw_pct,
                            alpha_pct,
                            f"{upd['holding_days']}d",
                            block_quick,
                            block_deep,
                            block_depth,
                            fields[7] if len(fields) > 7 else "0.0"
                        ]
                        new_tag = "[" + " | ".join(new_fields) + "]"
                        
                        rest = "\n".join(lines[1:])
                        new_blocks.append(
                            f"{new_tag}\n\n{rest.lstrip()}\n\nREFLECTION:\n{upd['reflection']}"
                        )
                        del update_map[key]
                        matched = True

            if not matched:
                new_blocks.append(block)

        new_blocks = self._apply_rotation(new_blocks)
        new_text = self._SEPARATOR.join(new_blocks)
        tmp_path = self._log_path.with_suffix(".tmp")
        tmp_path.write_text(new_text, encoding="utf-8")
        tmp_path.replace(self._log_path)

    # --- Helpers ---

    def _apply_rotation(self, blocks: List[str]) -> List[str]:
        """Drop oldest resolved blocks when their count exceeds max_entries.

        Pending blocks are always kept (they represent unprocessed work).
        Returns ``blocks`` unchanged when rotation is disabled or under cap.
        """
        if not self._max_entries or self._max_entries <= 0:
            return blocks

        # Tag each block with (kept, is_resolved) by parsing tag-line markers.
        decisions = []
        for block in blocks:
            stripped = block.strip()
            if not stripped:
                decisions.append((block, False))
                continue
            tag_line = stripped.splitlines()[0].strip()
            is_resolved = (
                tag_line.startswith("[")
                and tag_line.endswith("]")
                and " | pending" not in tag_line
            )
            decisions.append((block, is_resolved))

        resolved_count = sum(1 for _, r in decisions if r)
        if resolved_count <= self._max_entries:
            return blocks

        to_drop = resolved_count - self._max_entries
        kept: List[str] = []
        for block, is_resolved in decisions:
            if is_resolved and to_drop > 0:
                to_drop -= 1
                continue
            kept.append(block)
        return kept

    def _parse_entry(self, raw: str) -> Optional[dict]:
        lines = raw.strip().splitlines()
        if not lines:
            return None
        tag_line = lines[0].strip()
        if not (tag_line.startswith("[") and tag_line.endswith("]")):
            return None
        fields = [f.strip() for f in tag_line[1:-1].split("|")]
        if len(fields) < 4:
            return None
            
        # [date | ticker | rating | outcome/pending | ...metadata ]
        is_pending = fields[3] == "pending"
        
        entry = {
            "date": fields[0],
            "ticker": fields[1],
            "rating": fields[2],
            "pending": is_pending,
        }
        
        if is_pending:
            entry["raw"] = None
            entry["alpha"] = None
            entry["holding"] = None
            # New metadata fields for research (Simulation ID support)
            entry["quick_model"] = fields[4] if len(fields) > 4 else "unknown"
            entry["deep_model"] = fields[5] if len(fields) > 5 else "unknown"
            entry["depth"] = fields[6] if len(fields) > 6 else "1"
            entry["runtime_sec"] = fields[7] if len(fields) > 7 else "0.0"
        else:
            entry["raw"] = fields[3]
            entry["alpha"] = fields[4] if len(fields) > 4 else None
            entry["holding"] = fields[5] if len(fields) > 5 else None
            # Legacy entries might not have these, but new ones will shift them
            entry["quick_model"] = fields[6] if len(fields) > 6 else "unknown"
            entry["deep_model"] = fields[7] if len(fields) > 7 else "unknown"
            entry["depth"] = fields[8] if len(fields) > 8 else "1"
            entry["runtime_sec"] = fields[9] if len(fields) > 9 else "0.0"

        body = "\n".join(lines[1:]).strip()
        decision_match = self._DECISION_RE.search(body)
        reflection_match = self._REFLECTION_RE.search(body)
        entry["decision"] = decision_match.group(1).strip() if decision_match else ""
        entry["reflection"] = reflection_match.group(1).strip() if reflection_match else ""
        return entry


    def _format_full(self, e: dict) -> str:
        raw = e["raw"] or "n/a"
        alpha = e["alpha"] or "n/a"
        holding = e["holding"] or "n/a"
        tag = f"[{e['date']} | {e['ticker']} | {e['rating']} | {raw} | {alpha} | {holding}]"
        parts = [tag, f"DECISION:\n{e['decision']}"]
        if e["reflection"]:
            parts.append(f"REFLECTION:\n{e['reflection']}")
        return "\n\n".join(parts)

    def _format_reflection_only(self, e: dict) -> str:
        tag = f"[{e['date']} | {e['ticker']} | {e['rating']} | {e['raw'] or 'n/a'}]"
        if e["reflection"]:
            return f"{tag}\n{e['reflection']}"
        text = e["decision"][:300]
        suffix = "..." if len(e["decision"]) > 300 else ""
        return f"{tag}\n{text}{suffix}"
