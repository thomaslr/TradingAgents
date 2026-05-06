"""Non-interactive batch execution of TradingAgents analysis.

Used by the ``batch`` CLI subcommand to run analyses for multiple
tickers/dates without user interaction.
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

import yfinance as yf
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn

from tradingagents.graph.trading_graph import TradingAgentsGraph
from tradingagents.agents.utils.rating import parse_rating
from tradingagents.db.registry import RunRegistry

logger = logging.getLogger(__name__)
console = Console()

# All four analyst types — batch mode uses all of them.
ALL_ANALYSTS = ["market", "social", "news", "fundamentals"]


def _expand_dates(date_from: str, date_to: str) -> List[str]:
    """Generate every calendar day in [date_from, date_to] inclusive."""
    start = datetime.strptime(date_from, "%Y-%m-%d")
    end = datetime.strptime(date_to, "%Y-%m-%d")
    dates = []
    current = start
    while current <= end:
        dates.append(current.strftime("%Y-%m-%d"))
        current += timedelta(days=1)
    return dates


def _fetch_close_price(ticker: str, date_str: str) -> Optional[float]:
    """Fetch closing price from Yahoo Finance for a given date."""
    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        # Fetch 3-day window to handle weekends/holidays
        start = dt - timedelta(days=3)
        end = dt + timedelta(days=1)
        data = yf.download(
            ticker, start=start.strftime("%Y-%m-%d"),
            end=end.strftime("%Y-%m-%d"), progress=False
        )
        if data.empty:
            return None
        # Get the closest date <= target date
        target_data = data[data.index <= date_str]
        if target_data.empty:
            return None
        close = target_data["Close"].iloc[-1]
        # Handle both scalar and series returns
        return float(close.iloc[0]) if hasattr(close, "iloc") else float(close)
    except Exception as e:
        logger.warning("Could not fetch close price for %s on %s: %s", ticker, date_str, e)
        return None


def _extract_trading_results(final_state: dict, decision: str, ticker: str, trade_date: str) -> Dict[str, Any]:
    """Extract structured trading data from the graph's final state."""
    results: Dict[str, Any] = {
        "rating": decision,  # Already parsed via process_signal
    }

    # Try to extract trader proposal fields from the state
    trader_plan = final_state.get("trader_investment_plan", "")
    if isinstance(trader_plan, str):
        # Parse action from trader output
        action_match = re.search(r"\*\*Action\*\*:\s*(\w+)", trader_plan)
        if action_match:
            results["action"] = action_match.group(1).capitalize()

        # Parse entry price
        price_match = re.search(r"\*\*Entry Price\*\*:\s*([\d.]+)", trader_plan)
        if price_match:
            try:
                results["entry_price"] = float(price_match.group(1))
            except ValueError:
                pass

        # Parse stop loss
        sl_match = re.search(r"\*\*Stop Loss\*\*:\s*([\d.]+)", trader_plan)
        if sl_match:
            try:
                results["stop_loss"] = float(sl_match.group(1))
            except ValueError:
                pass

        # Parse position sizing
        sizing_match = re.search(r"\*\*Position Sizing\*\*:\s*(.+)", trader_plan)
        if sizing_match:
            results["position_sizing"] = sizing_match.group(1).strip()

    # Try to extract PM fields from final decision
    final_decision = final_state.get("final_trade_decision", "")
    if isinstance(final_decision, str):
        # Parse price target
        pt_match = re.search(r"\*\*Price Target\*\*:\s*([\d.]+)", final_decision)
        if pt_match:
            try:
                results["price_target"] = float(pt_match.group(1))
            except ValueError:
                pass

        # Parse time horizon
        th_match = re.search(r"\*\*Time Horizon\*\*:\s*(.+)", final_decision)
        if th_match:
            results["time_horizon"] = th_match.group(1).strip()

    # Fetch close price from market data
    results["close_price"] = _fetch_close_price(ticker, trade_date)

    return results


def run_batch_analysis(
    tickers: List[str],
    dates: List[str],
    config: dict,
    registry: RunRegistry,
    skip_completed: bool = True,
    force: bool = False,
) -> Dict[str, Any]:
    """Execute batch analysis sequentially.

    Returns a summary dict with counts of completed/skipped/failed runs.
    """
    provider = config["llm_provider"]
    quick_model = config["quick_think_llm"]
    deep_model = config["deep_think_llm"]
    depth = config.get("max_debate_rounds", 1)

    total_jobs = len(tickers) * len(dates)
    completed = 0
    skipped = 0
    failed = 0

    console.print(f"\n[bold cyan]Batch Analysis[/bold cyan]")
    console.print(f"  Tickers: {', '.join(tickers)}")
    console.print(f"  Dates:   {dates[0]}" + (f" → {dates[-1]}" if len(dates) > 1 else ""))
    console.print(f"  Provider: {provider} | Quick: {quick_model} | Deep: {deep_model}")
    console.print(f"  Depth: {depth} | Jobs: {total_jobs}\n")

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        console=console,
    ) as progress:
        task = progress.add_task("Running batch...", total=total_jobs)

        for ticker in tickers:
            for date in dates:
                progress.update(task, description=f"{ticker} {date}")

                # Check existing run
                existing = registry.find_run(
                    ticker, date, provider, quick_model, deep_model, depth
                )

                if existing and existing["status"] == "completed":
                    if force:
                        # Delete old entry to allow re-run
                        registry.delete_run(existing["id"])
                        console.print(f"  [yellow]↻ Force re-run: {ticker} {date}[/yellow]")
                    elif skip_completed:
                        skipped += 1
                        progress.advance(task)
                        console.print(f"  [dim]⏭ Skipped (completed): {ticker} {date}[/dim]")
                        continue

                if existing and existing["status"] == "running":
                    # Stale running entry from a crash — delete and re-run
                    registry.delete_run(existing["id"])

                # Create registry entry
                report_dir = str(
                    Path(config["results_dir"]) / ticker / date / "reports"
                )
                run_id = registry.create_run(
                    ticker=ticker,
                    trade_date=date,
                    provider=provider,
                    quick_model=quick_model,
                    deep_model=deep_model,
                    depth=depth,
                    report_dir=report_dir,
                )
                registry.mark_running(run_id)

                try:
                    # Build the graph
                    graph = TradingAgentsGraph(
                        ALL_ANALYSTS,
                        config=config,
                        debug=False,
                    )

                    # Run analysis
                    final_state, decision = graph.propagate(ticker, date)

                    # Extract results
                    results = _extract_trading_results(
                        final_state, decision, ticker, date
                    )
                    registry.mark_completed(run_id, results)
                    completed += 1
                    console.print(
                        f"  [green]✓ {ticker} {date}[/green] → "
                        f"[bold]{results.get('rating', 'N/A')}[/bold]"
                        + (f" (close: ${results['close_price']:.2f})" if results.get('close_price') else "")
                    )

                except Exception as e:
                    error_msg = str(e)
                    registry.mark_failed(run_id, error_msg)
                    failed += 1
                    console.print(f"  [red]✗ {ticker} {date}: {error_msg[:100]}[/red]")
                    logger.exception("Batch analysis failed for %s on %s", ticker, date)

                progress.advance(task)

    summary = {
        "total": total_jobs,
        "completed": completed,
        "skipped": skipped,
        "failed": failed,
    }

    console.print(f"\n[bold]Batch Summary:[/bold]")
    console.print(f"  ✓ Completed: {completed}  ⏭ Skipped: {skipped}  ✗ Failed: {failed}")
    console.print(f"  Database: {registry.db_path}\n")

    return summary
