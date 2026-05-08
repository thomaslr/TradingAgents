import os
from dotenv import load_dotenv

# Load .env file explicitly
load_dotenv()

_TRADINGAGENTS_HOME = os.path.join(os.path.expanduser("~"), ".tradingagents")


def _resolve_provider_var(provider: str, var_name: str, fallback: str = "") -> str:
    """Resolve a config value with provider-prefix priority.

    Lookup order:
    1. ``{PROVIDER}_{VAR_NAME}`` (e.g. ``OLLAMA_QUICK_THINK_MODEL``)
    2. ``{VAR_NAME}``            (e.g. ``QUICK_THINK_MODEL``)
    3. ``fallback``              (hardcoded default)
    """
    prefixed = os.getenv(f"{provider.upper()}_{var_name}")
    generic = os.getenv(var_name)
    return prefixed or generic or fallback


_ACTIVE_PROVIDER = os.getenv("LLM_PROVIDER", "openai")

DEFAULT_CONFIG = {
    "project_dir": os.path.abspath(os.path.join(os.path.dirname(__file__), ".")),
    "results_dir": os.getenv("TRADINGAGENTS_RESULTS_DIR", os.path.join(_TRADINGAGENTS_HOME, "logs")),
    "data_cache_dir": os.getenv("TRADINGAGENTS_CACHE_DIR", os.path.join(_TRADINGAGENTS_HOME, "cache")),
    "db_path": os.getenv("TRADINGAGENTS_DB_PATH", os.path.join(_TRADINGAGENTS_HOME, "tradingagents.db")),
    "memory_log_path": os.getenv("TRADINGAGENTS_MEMORY_LOG_PATH", os.path.join(_TRADINGAGENTS_HOME, "memory", "trading_memory.md")),
    # Optional cap on the number of resolved memory log entries. When set,
    # the oldest resolved entries are pruned once this limit is exceeded.
    # Pending entries are never pruned. None disables rotation entirely.
    "memory_log_max_entries": None,
    # LLM settings — resolved via provider-prefixed env vars
    "llm_provider": _ACTIVE_PROVIDER,
    "deep_think_llm": _resolve_provider_var(_ACTIVE_PROVIDER, "DEEP_THINK_MODEL", "gpt-5.4"),
    "quick_think_llm": _resolve_provider_var(_ACTIVE_PROVIDER, "QUICK_THINK_MODEL", "gpt-5.4-mini"),
    # When None, each provider's client falls back to its own default endpoint
    # (api.openai.com for OpenAI, generativelanguage.googleapis.com for Gemini, ...).
    # The CLI overrides this per provider when the user picks one. Keeping a
    # provider-specific URL here would leak (e.g. OpenAI's /v1 was previously
    # being forwarded to Gemini, producing malformed request URLs).
    "backend_url": None,
    # Provider-specific thinking configuration
    "google_thinking_level": None,      # "high", "minimal", etc.
    "openai_reasoning_effort": None,    # "medium", "high", "low"
    "anthropic_effort": None,           # "high", "medium", "low"
    # Checkpoint/resume: when True, LangGraph saves state after each node
    # so a crashed run can resume from the last successful step.
    "checkpoint_enabled": False,
    # Output language for analyst reports and final decision
    # Internal agent debate stays in English for reasoning quality
    "output_language": "English",
    # Debate and discussion settings
    "max_debate_rounds": 1,
    "max_risk_discuss_rounds": 1,
    "max_recur_limit": int(os.getenv("MAX_RECUR_LIMIT", 100)),
    # Data vendor configuration
    # Category-level configuration (default for all tools in category)
    "data_vendors": {
        "core_stock_apis": "yfinance",       # Options: alpha_vantage, yfinance
        "technical_indicators": "yfinance",  # Options: alpha_vantage, yfinance
        "fundamental_data": "yfinance",      # Options: alpha_vantage, yfinance
        "news_data": "yfinance",             # Options: alpha_vantage, yfinance
    },
    # Tool-level configuration (takes precedence over category-level)
    "tool_vendors": {
        # Example: "get_stock_data": "alpha_vantage",  # Override category default
    },
}
