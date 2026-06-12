# Walkthrough - Visible Range Time Scale Normalization on Chart View

We have successfully implemented dynamic start-date normalization linked directly to the chart's visible time-range event.

## Key Changes Made

### 1. Interactive Normalization via Time Scale Event Subscription
* **File modified**: [ChartView.vue](file:///c:/Users/rober/dev_win/TradingAgents/frontend/src/views/ChartView.vue)
* Captured all created strategy overlay LineSeries into an array of objects `activeStrategySeriesList` along with their raw points:
  ```typescript
  const activeStrategySeriesList: {
    series: any;
    rawPoints: { time: string; value: number }[];
  }[] = []
  ```
* Implemented an event-driven `updateNormalization` function that queries the active visible time scale range (`chart.timeScale().getVisibleRange()`), finds the left-most visible candle on the screen, and calculates:
  - `startPrice`: Close price of that first visible candle.
  - `startStratValue`: Accumulated return value of each strategy on that exact visible start date.
* Re-normalizes the strategy series data dynamically relative to these values:
  ```typescript
  const normalizedData = rawPoints
    .filter(p => priceMap.has(p.time) && p.time >= chartStartTime)
    .map(p => ({
      time: p.time,
      value: p.value * (startPrice / startStratValue)
    }))
  series.setData(normalizedData)
  ```
* Subscribed this function to the Lightweight Charts time scale updates:
  ```typescript
  chart.timeScale().subscribeVisibleTimeRangeChange(updateNormalization)
  ```
* Now, zooming in/out (e.g. via the **mouse wheel**) or dragging/scrolling the chart automatically triggers the visible-range listener, causing all strategy lines to immediately re-anchor themselves to start exactly at the stock price at the left-most visible edge of the screen.

### 2. Cash Backfilling for Prior Periods
* If the visible range includes earlier dates where the model hasn't been run, the strategy starts flat at the initial visible stock close price (holding Cash, 0% daily return) and remains flat until the first trading signal date, where it begins active performance tracking.

### 3. Build & Deployment
* Confirmed the frontend builds successfully (`npm run build`) with zero compilation errors.
* Redeployed the updated container to `homenas.local` under the `homenas` docker context.

---

## Verification Results

### Build Verification
* Successfully ran `npm run build` with zero TypeScript or Vue compilation errors.

### Manual Verification
1. Navigate to the **Charts** page.
2. Observe the strategy lines in the **1Y** preset. They start at the far left (June) matching the stock price, stay flat (Cash) until December, and then start trading.
3. Zoom in/out using the **mouse wheel** or drag the chart timeline left/right.
4. Verify that the strategy lines **dynamically slide and shift** so they are always anchored exactly at the stock price on the left edge of the visible window, reflecting relative return performance from whatever start date is currently displayed.
