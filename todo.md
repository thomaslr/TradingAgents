# TradingAgents TODO & Future Ideas

- [ ] **Model Comparison Research View**
    - **Concept**: Compare performance of different LLMs (e.g., GPT-4o vs. Llama 3) on the same tickers.
    - **Implementation**: Parse the `deep_model` and `quick_model` fields from the run history and aggregate ROI/Alpha by model type.
    - **Goal**: Identify which models provide the most accurate trading signals and "AI Alpha."

- [ ] **Advanced Cost Simulation**
    - **Concept**: Move beyond a flat 0.1% fee to specific broker structures.
    - **Implementation**: Add support for IBKR-style tiered pricing ($0.005/share) and minimums.

- [ ] **Live Portfolio Integration**
    - **Concept**: Transition from paper trading to real execution.
    - **Implementation**: Integrate with IBKR/Alpaca APIs to execute the Portfolio Manager's decisions.
- [ ] Investigate additional news sources:
    - [ ] Finnhub (Earnings transcripts, SEC filings)
    - [ ] NewsAPI.org (General world news)
    - [ ] Polygon.io (Low-latency market news)
    - [ ] Direct RSS feeds (Bloomberg, Reuters, CNBC)
    - [ ] Social Media Integration (Reddit, X/Twitter scrapers for true sentiment)
