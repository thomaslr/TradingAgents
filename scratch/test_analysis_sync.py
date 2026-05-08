from api.routes.analysis import execute_analysis_task, AnalysisRequest
from tradingagents.default_config import DEFAULT_CONFIG
import asyncio

req = AnalysisRequest(
    tickers=["AAPL"],
    dates=["2026-05-08"],
    force=False,
    skip_completed=True,
    llm_provider="ollama",
    quick_think_llm="llama3.2:3b",
    deep_think_llm="llama3.1:8b",
    max_debate_rounds=1
)

config = DEFAULT_CONFIG.copy()
db_path = config["db_path"]

execute_analysis_task(req, config, db_path)
