# Implementation Plan - Shared Stock Selection Across Pages

This plan outlines the design and steps to make stock selections common throughout all pages in the TradingAgents dashboard. When a user selects a set of tickers on one page (e.g. NVDA, TSLA, IBM), it will carry over to the other pages as they switch between them.

## Proposed Design & Mechanics

### 1. Shared Reactive Store
We will create a lightweight reactive store in [store.ts](file:///c:/Users/rober/dev_win/TradingAgents/frontend/src/store.ts) containing:
* selectedTickers: A reactive list (
ef<string[]>) of the tickers currently selected. Initially loaded from 	rading_tickers in localStorage.
* ctiveTicker: A reactive string (
ef<string>) of the currently active/focused ticker. Initially loaded from chart_ticker in localStorage, defaulting to the first entry in selectedTickers or SPY.
* Helper functions ddTicker(ticker) and setActiveTicker(ticker).
* Watchers that persist updates back to localStorage.

### 2. View Integration

#### [AnalysisView.vue](file:///c:/Users/rober/dev_win/TradingAgents/frontend/src/views/AnalysisView.vue)
* Sync the comma-separated 	ickersInput field with selectedTickers from the store.
* Set up a double watcher to ensure edits in the text area sync to the store, and external additions (e.g. from the Chart view) sync back to the text area without resetting the cursor.

#### [ChartView.vue](file:///c:/Users/rober/dev_win/TradingAgents/frontend/src/views/ChartView.vue)
* Sync the active chart ticker with the store's ctiveTicker.
* Render a horizontal row of quick-select button tabs for all tickers in selectedTickers. Clicking one changes ctiveTicker and switches the chart.
* When mounting or when the route parameter :ticker changes, automatically set that ticker as ctiveTicker and add it to selectedTickers.
* When selecting a ticker via the dropdown, add it to selectedTickers.

#### [PerformanceView.vue](file:///c:/Users/rober/dev_win/TradingAgents/frontend/src/views/PerformanceView.vue)
* Sync the filter selectedTicker with the store's ctiveTicker.
* Render a horizontal row of quick-select button tabs for ALL and each ticker in selectedTickers. Clicking one updates the performance filter and sets it as the active ticker.

---

## Proposed Changes

### Frontend

#### [NEW] [store.ts](file:///c:/Users/rober/dev_win/TradingAgents/frontend/src/store.ts)
* Create the shared state module with selectedTickers, ctiveTicker, ddTicker, and setActiveTicker.

#### [MODIFY] [AnalysisView.vue](file:///c:/Users/rober/dev_win/TradingAgents/frontend/src/views/AnalysisView.vue)
* Import selectedTickers and replace the direct localStorage binding of 	ickersInput with a synchronized local ref that watches the store.

#### [MODIFY] [ChartView.vue](file:///c:/Users/rober/dev_win/TradingAgents/frontend/src/views/ChartView.vue)
* Import selectedTickers, ctiveTicker, and setActiveTicker.
* Bind the dropdown and route parameter changes to the store.
* Add quick-select button tabs to the header layout.

#### [MODIFY] [PerformanceView.vue](file:///c:/Users/rober/dev_win/TradingAgents/frontend/src/views/PerformanceView.vue)
* Import selectedTickers, ctiveTicker, and setActiveTicker.
* Bind selectedTicker filter to ctiveTicker.
* Add quick-select button tabs to the filter header.

---

## Verification Plan

### Automated Build
* Run 
pm run build inside rontend/ to confirm that all TypeScript and Vue code compiles successfully without errors.

### Manual Verification
1. Open the **Analysis** page, enter NVDA, TSLA, IBM, and verify they save.
2. Navigate to the **Chart** page. Verify that quick-select buttons for NVDA, TSLA, and IBM are displayed.
3. Click TSLA in the quick-select list; verify that the chart switches to TSLA.
4. Enter/select a new ticker AAPL in the dropdown; verify that AAPL is added to the quick-select list.
5. Switch back to the **Analysis** page; verify that the target tickers now contain AAPL.
6. Switch to the **Performance** page; verify that quick-select buttons for ALL, NVDA, TSLA, IBM, and AAPL are present, and clicking them updates the simulation filter correctly.
