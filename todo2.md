# TODO - TradingAgents Research Mode

## High Priority: Simulation & Research Platform
- [ ] **Simulation ID Logic**: Decouple report storage using `{ticker}/{date}/{model}_{depth}_{ts}.json` format.
- [ ] **Metadata Capture**: Track `runtime_sec`, `quick_model`, `deep_model`, and `debate_depth` in `memory.json`.
- [ ] **Context Monitor**: Capture and store token usage/context length to identify model limits.
- [ ] **Dynamic UI Toggles**: Add Model and Depth filters to the Performance Dashboard.
- [ ] **Efficiency Scoring**: Implement "Alpha-per-Second" and "Alpha-per-Token" metrics.

## Performance & Optimization
- [ ] **NVDA Shootout**: Run comparative tests for NVDA (Apr 15 - May 1) at depths 1, 2, and 3.
- [ ] **Slippage Research**: Investigate real-world slippage models for high-volatility stocks like NVDA.
- [ ] **Multi-Model Support**: Verify stability when using different models for Analysts vs. Portfolio Manager.

## Future Research (Backlog)
- [ ] **Sentiment Source Expansion**:
    - [ ] Integrate Finnhub News API
    - [ ] Integrate Polygon.io Aggregates
    - [ ] Research RSS Feed Scrapers for financial blogs
    - [ ] Social Media Sentiment (X/Reddit) integration
- [ ] **Monte Carlo Replay**: Allow re-running a PM decision on existing analyst reports with different risk settings.
