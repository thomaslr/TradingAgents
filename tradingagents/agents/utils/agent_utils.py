from langchain_core.messages import HumanMessage, RemoveMessage

# Import tools from separate utility files
from tradingagents.agents.utils.core_stock_tools import (
    get_stock_data
)
from tradingagents.agents.utils.technical_indicators_tools import (
    get_indicators
)
from tradingagents.agents.utils.fundamental_data_tools import (
    get_fundamentals,
    get_balance_sheet,
    get_cashflow,
    get_income_statement
)
from tradingagents.agents.utils.news_data_tools import (
    get_news,
    get_insider_transactions,
    get_global_news
)


def get_language_instruction() -> str:
    """Return a prompt instruction for the configured output language.

    Returns empty string when English (default), so no extra tokens are used.
    Only applied to user-facing agents (analysts, portfolio manager).
    Internal debate agents stay in English for reasoning quality.
    """
    from tradingagents.dataflows.config import get_config
    lang = get_config().get("output_language", "English")
    if lang.strip().lower() == "english":
        return " Write your entire response in English."
    return f" Write your entire response in {lang}."


def build_instrument_context(ticker: str) -> str:
    """Describe the exact instrument so agents preserve exchange-qualified tickers."""
    return (
        f"The instrument to analyze is `{ticker}`. "
        "Use this exact ticker in every tool call, report, and recommendation, "
        "preserving any exchange suffix (e.g. `.TO`, `.L`, `.HK`, `.T`)."
    )

def create_msg_delete():
    def delete_messages(state):
        """Clear messages and add placeholder for Anthropic compatibility"""
        messages = state["messages"]

        # Remove all messages
        removal_operations = [RemoveMessage(id=m.id) for m in messages]

        # Add a minimal placeholder message
        placeholder = HumanMessage(content="Continue")

        return {"messages": removal_operations + [placeholder]}

    return delete_messages


def check_and_cache_analyst(state: dict, analyst_type: str, system_message: str, run_node_fn):
    """Checks if a cached report exists for the given analyst criteria.
    
    If cache hit occurs, skips execution and returns cached state.
    Otherwise, executes run_node_fn, saves report to cache, and returns state.
    """
    import hashlib
    import json
    import logging
    from pathlib import Path
    from langchain_core.messages import AIMessage
    from tradingagents.dataflows.config import get_config
    from tradingagents.db.registry import RunRegistry
    from tradingagents.dataflows.utils import safe_ticker_component

    config = get_config()
    db_path = config.get("db_path")
    
    ticker = state.get("company_of_interest", "unknown")
    trade_date = state.get("trade_date", "unknown")
    model = config.get("quick_think_llm", "unknown")
    prompt_hash = hashlib.md5(system_message.encode("utf-8")).hexdigest()
    
    # Check force flag
    force_run = config.get("force", False)
    
    report_key = f"{analyst_type}_report" if analyst_type != "social" else "sentiment_report"
    
    if not force_run and db_path:
        try:
            registry = RunRegistry(db_path)
            cached_report = registry.get_cached_analyst_report(
                ticker=ticker,
                trade_date=trade_date,
                model=model,
                analyst_type=analyst_type,
                prompt_hash=prompt_hash
            )
            registry.close()
            
            if cached_report:
                logging.info(f"🚀 [CACHE HIT] {analyst_type.capitalize()} Analyst cached report reused for {ticker} {trade_date} ({model})")
                return {
                    "messages": [AIMessage(content=cached_report)],
                    report_key: cached_report
                }
        except Exception as e:
            logging.warning(f"Failed to read from analyst cache: {e}")

    # Cache MISS - run the live node
    logging.info(f"⏳ [CACHE MISS] Running {analyst_type.capitalize()} Analyst live for {ticker} {trade_date} ({model})")
    result_state = run_node_fn(state)
    
    report_text = result_state.get(report_key, "")
    if report_text and db_path:
        try:
            safe_ticker = safe_ticker_component(ticker)
            safe_model = model.replace(":", "-")
            
            shared_dir = Path(db_path).parent / "shared_reports" / safe_ticker / str(trade_date) / safe_model
            shared_dir.mkdir(parents=True, exist_ok=True)
            
            shared_file_path = shared_dir / f"{analyst_type}.json"
            
            with open(shared_file_path, "w", encoding="utf-8") as f:
                json.dump({
                    "ticker": ticker,
                    "trade_date": trade_date,
                    "model": model,
                    "analyst_type": analyst_type,
                    "prompt_hash": prompt_hash,
                    "report": report_text
                }, f, indent=4)
                
            registry = RunRegistry(db_path)
            registry.save_cached_analyst_report(
                ticker=ticker,
                trade_date=trade_date,
                model=model,
                analyst_type=analyst_type,
                file_path=str(shared_file_path),
                prompt_hash=prompt_hash
            )
            registry.close()
            logging.info(f"💾 [CACHE SAVE] {analyst_type.capitalize()} Analyst report saved to cache library: {shared_file_path}")
        except Exception as e:
            logging.warning(f"Failed to save analyst report to cache: {e}")
            
    return result_state


        
