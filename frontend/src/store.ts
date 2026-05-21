import { ref, watch } from 'vue'

// Helper to parse comma-separated tickers from localStorage
function parseTickers(str: string | null): string[] {
  if (!str) return []
  return str
    .split(',')
    .map(t => t.trim().toUpperCase())
    .filter(t => t.length > 0)
}

// 1. Shared list of selected tickers
export const selectedTickers = ref<string[]>(
  parseTickers(localStorage.getItem('trading_tickers'))
)

// 2. Active ticker
export const activeTicker = ref<string>(
  localStorage.getItem('chart_ticker') || (selectedTickers.value[0] || 'SPY')
)

// Watch selectedTickers and update localStorage
watch(
  selectedTickers,
  (tickers) => {
    localStorage.setItem('trading_tickers', tickers.join(', '))
  },
  { deep: true }
)

// Watch activeTicker and update localStorage
watch(
  activeTicker,
  (ticker) => {
    if (ticker) {
      localStorage.setItem('chart_ticker', ticker)
      localStorage.setItem('perf_ticker', ticker)
    }
  }
)

// Add a ticker to the selection if not already present
export function addTicker(ticker: string) {
  const t = ticker.trim().toUpperCase()
  if (t && !selectedTickers.value.includes(t)) {
    selectedTickers.value.push(t)
  }
}

// Set the active ticker and add to selection
export function setActiveTicker(ticker: string) {
  const t = ticker.trim().toUpperCase()
  if (t) {
    activeTicker.value = t
    addTicker(t)
  }
}
