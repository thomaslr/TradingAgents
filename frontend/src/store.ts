import { ref, watch } from 'vue'
import { fetchConfigs, type SimulationConfig } from './api/client'

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

// 2.05 Select all tickers
export const allTickersSelected = ref<boolean>(
  localStorage.getItem('all_tickers_selected') === 'true'
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

watch(
  allTickersSelected,
  (selected) => {
    localStorage.setItem('all_tickers_selected', String(selected))
  }
)

// 2.1 Active date (shared across views)
export const activeDate = ref<string>(
  localStorage.getItem('shared_active_date') || '2026-05-06'
)

// Watch activeDate and update localStorage
watch(activeDate, (date) => {
  if (date) {
    localStorage.setItem('shared_active_date', date)
    localStorage.setItem('report_date', date)
  }
})

// 2.2 Global model execution configuration state
export const provider = ref<string>(
  localStorage.getItem('trading_provider') || 'openai'
)
export const quickModel = ref<string>(
  localStorage.getItem('trading_quick_model') || ''
)
export const deepModel = ref<string>(
  localStorage.getItem('trading_deep_model') || ''
)
export const depth = ref<number>(
  Number(localStorage.getItem('trading_depth')) || 1
)

watch(provider, (v) => localStorage.setItem('trading_provider', v))
watch(quickModel, (v) => localStorage.setItem('trading_quick_model', v))
watch(deepModel, (v) => localStorage.setItem('trading_deep_model', v))
watch(depth, (v) => localStorage.setItem('trading_depth', String(v)))

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

// 3. Shared simulation configurations
export const configs = ref<SimulationConfig[]>([])
export const enabledConfigs = ref<Set<string>>(new Set())

// Load configs from API and sync enabled selection
export async function loadConfigs() {
  try {
    const fetched = await fetchConfigs()
    configs.value = fetched
    
    const saved = localStorage.getItem('shared_enabled_configs')
    if (saved) {
      const parsed = JSON.parse(saved)
      if (Array.isArray(parsed)) {
        enabledConfigs.value = new Set(parsed)
        return
      }
    }
    // Default: enable all configs
    enabledConfigs.value = new Set(fetched.map(c => c.config_id))
  } catch (e) {
    console.error('Failed to load configs in store', e)
  }
}

export function toggleConfig(configId: string) {
  const s = new Set(enabledConfigs.value)
  if (s.has(configId)) {
    s.delete(configId)
  } else {
    s.add(configId)
  }
  enabledConfigs.value = s
  localStorage.setItem('shared_enabled_configs', JSON.stringify(Array.from(s)))
}

export function selectAllConfigs() {
  enabledConfigs.value = new Set(configs.value.map(c => c.config_id))
  localStorage.setItem('shared_enabled_configs', JSON.stringify(Array.from(enabledConfigs.value)))
}

export function clearAllConfigs() {
  enabledConfigs.value = new Set()
  localStorage.setItem('shared_enabled_configs', JSON.stringify([]))
}

// Listen for storage changes to sync across browser tabs/windows
if (typeof window !== 'undefined') {
  window.addEventListener('storage', (event) => {
    if (event.key === 'shared_enabled_configs' && event.newValue !== null) {
      try {
        const parsed = JSON.parse(event.newValue)
        if (Array.isArray(parsed)) {
          enabledConfigs.value = new Set(parsed)
        }
      } catch (e) {
        console.error('Failed to sync configs on storage event', e)
      }
    } else if (event.key === 'trading_tickers' && event.newValue !== null) {
      selectedTickers.value = parseTickers(event.newValue)
    } else if (event.key === 'chart_ticker' && event.newValue !== null) {
      activeTicker.value = event.newValue
    } else if (event.key === 'all_tickers_selected' && event.newValue !== null) {
      allTickersSelected.value = event.newValue === 'true'
    } else if (event.key === 'shared_active_date' && event.newValue !== null) {
      activeDate.value = event.newValue
    } else if (event.key === 'trading_provider' && event.newValue !== null) {
      provider.value = event.newValue
    } else if (event.key === 'trading_quick_model' && event.newValue !== null) {
      quickModel.value = event.newValue
    } else if (event.key === 'trading_deep_model' && event.newValue !== null) {
      deepModel.value = event.newValue
    } else if (event.key === 'trading_depth' && event.newValue !== null) {
      depth.value = Number(event.newValue) || 1
    }
  })
}
