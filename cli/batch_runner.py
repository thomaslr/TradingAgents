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
import time
import threading
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn, TimeElapsedColumn
from langchain_core.callbacks import BaseCallbackHandler

from tradingagents.graph.trading_graph import TradingAgentsGraph
from tradingagents.agents.utils.rating import parse_rating
from tradingagents.db.registry import RunRegistry

logger = logging.getLogger(__name__)
console = Console()

# All four analyst types — batch mode uses all of them.
ALL_ANALYSTS = ["market", "social", "news", "fundamentals"]


class TokenTracker(BaseCallbackHandler):
    """Callback handler to track total token usage across multiple LLM calls."""
    def __init__(self, progress=None, task_id=None):
        self.input_tokens = 0
        self.output_tokens = 0
        self.progress = progress
        self.task_id = task_id

    def on_llm_end(self, response, **kwargs) -> None:
        """Collect token usage from the LLM response metadata."""
        for generations in response.generations:
            for generation in generations:
                # Different providers use different metadata keys for tokens
                # We try to handle the most common ones (OpenAI, Ollama, Anthropic, Gemini)
                usage = generation.message.response_metadata.get("token_usage") or \
                        generation.message.response_metadata.get("usage") or \
                        generation.message.additional_kwargs.get("token_usage")
                
                if usage:
                    self.input_tokens += usage.get("prompt_tokens", 0) or usage.get("input_tokens", 0)
                    self.output_tokens += usage.get("completion_tokens", 0) or usage.get("output_tokens", 0)
                    
                    if self.progress and self.task_id is not None:
                        tokens_str = f"[blue]{self.input_tokens}ᵢ[/blue]/[cyan]{self.output_tokens}ₒ[/cyan]"
                        self.progress.update(self.task_id, tokens=tokens_str)
                    


class StatusTracker(BaseCallbackHandler):
    """Callback to update the progress bar status label."""
    def __init__(self, progress, task_id):
        self.progress = progress
        self.task_id = task_id

    def on_chain_start(self, serialized, inputs, **kwargs):
        """Update status when a new node/chain starts."""
        name = serialized.get("name") or "Agent"
        if name in ["market_analyst_node", "sentiment_analyst_node", "news_analyst_node", "fundamentals_analyst_node"]:
            status = name.replace("_node", "").replace("_", " ").title()
            self.progress.update(self.task_id, status=f"[yellow]{status}[/yellow]")
        elif "debate" in name.lower():
            self.progress.update(self.task_id, status="[orange1]Debating[/orange1]")
        elif "trader" in name.lower():
            self.progress.update(self.task_id, status="[cyan]Planning Trade[/cyan]")


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


from typing import Any, Dict, List, Optional, Callable


def run_batch_analysis(
    tickers: List[str],
    dates: List[str],
    config: dict,
    registry: RunRegistry,
    skip_completed: bool = True,
    force: bool = False,
    abort_event: Optional[threading.Event] = None,
    progress_callback: Optional[Callable[[str, str], None]] = None,
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
        TextColumn("{task.fields[status]}", justify="right"),
        TextColumn("({task.fields[tokens]})", justify="right"),
        TimeElapsedColumn(),
        console=console,
    ) as progress:
        task = progress.add_task("Running batch...", total=total_jobs, status="[dim]Starting...[/dim]", tokens="0/0")

        for ticker in tickers:
            for date in dates:
                if abort_event and abort_event.is_set():
                    console.print(f"\n[bold yellow]⚠ Abort requested. Stopping batch...[/bold yellow]")
                    progress.update(task, status="[yellow]Aborted[/yellow]")
                    return {
                        "total": total_jobs,
                        "completed": completed,
                        "skipped": skipped,
                        "failed": failed,
                        "aborted": True
                    }

                progress.update(task, description=f"{ticker} {date}")
                if progress_callback:
                    progress_callback(ticker, date)

                # Check existing run
                existing = registry.find_run(
                    ticker, date, provider, quick_model, deep_model, depth
                )

                if existing or force:
                    # We also check if we're forcing so we can wipe ANY provider/model config for this date
                    if force or (existing and existing["status"] == "running"):
                        # Clear ALL existing runs for this ticker/date to prevent duplicates
                        runs_to_clear = registry.list_runs(ticker=ticker)
                        runs_to_clear = [r for r in runs_to_clear if r["trade_date"] == date]
                        
                        for r in runs_to_clear:
                            # Clean up file system
                            report_dir = r.get("report_dir")
                            if report_dir and Path(report_dir).exists():
                                import shutil
                                shutil.rmtree(report_dir, ignore_errors=True)
                        
                        # Delete from DB
                        registry.delete_runs_for_ticker_date(ticker, date)

                        if force:
                            console.print(f"  [yellow]↻ Force re-run (cleared existing): {ticker} {date}[/yellow]")
                    elif existing and skip_completed and existing["status"] == "completed":
                        skipped += 1
                        progress.advance(task)
                        console.print(f"  [dim]⏭ Skipped (completed): {ticker} {date}[/dim]")
                        continue
                    elif existing and existing["status"] == "completed":
                        # Not skipping, but not forcing — just move on
                        skipped += 1
                        progress.advance(task)
                        continue

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
                    tracker = TokenTracker(progress, task)
                    status_cb = StatusTracker(progress, task)
                    graph = TradingAgentsGraph(
                        ALL_ANALYSTS,
                        config=config,
                        debug=False,
                        callbacks=[tracker, status_cb]
                    )

                    # Run analysis
                    start_time = time.time()
                    progress.update(task, status="[yellow]Initializing[/yellow]")
                    
                    # We use a simple timeout check (though a true async timeout is better, 
                    # for a CLI this helps us catch loops between steps)
                    final_state, decision = graph.propagate(ticker, date)
                    
                    elapsed = time.time() - start_time

                    # Extract results
                    results = _extract_trading_results(
                        final_state, decision, ticker, date
                    )
                    registry.mark_completed(run_id, results)
                    completed += 1
                    
                    progress.update(task, status="[green]Done[/green]")
                    
                    time_str = f"{elapsed:.1f}s" if elapsed < 60 else f"{int(elapsed // 60)}m {int(elapsed % 60)}s"
                    
                    # Format token display (In / Out)
                    tokens_str = f"[blue]{tracker.input_tokens}ᵢ[/blue]/[cyan]{tracker.output_tokens}ₒ[/cyan]"
                    
                    console.print(
                        f"  [green]✓ {ticker} {date}[/green] → "
                        f"[bold]{results.get('rating', 'N/A')}[/bold]"
                        + (f" (close: ${results['close_price']:.2f})" if results.get('close_price') else "")
                        + f" [dim]({tokens_str} | {time_str})[/dim]"
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
    console.print(f"  Database: {registry.db_path}\n")

    return summary
