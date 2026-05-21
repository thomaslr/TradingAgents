<script setup lang="ts">
import { ref, onMounted, onUnmounted, computed, watch } from 'vue'
import { fetchPerformanceData, fetchConfigs, clearMemoryEntries, fetchTickers, type PerformanceEntry, type SimulationConfig, type MemoryEntry } from '../api/client'
import { createChart, ColorType, LineSeries, LineStyle } from 'lightweight-charts'
import { Trophy, RefreshCw, Info, Filter, BarChart3, Trash2, Search } from 'lucide-vue-next'
import { selectedTickers, activeTicker, setActiveTicker } from '../store'

const loading = ref(true)
const rawDbEntries = ref<PerformanceEntry[]>([])
const configs = ref<SimulationConfig[]>([])
const enabledConfigs = ref<Set<string>>(new Set())
const configsSearchQuery = ref('')
const chartContainer = ref<HTMLDivElement>()
let chart: any = null
let benchmarkSeries: any = null
let strategySeriesMap = new Map<string, any>()
const registryTickers = ref<{ticker: string, name: string}[]>([])

function safeConfigColor(c: SimulationConfig): string {
  const color = c.color || '#10b981'
  const lower = color.toLowerCase().trim()
  if (lower === '#ffffff' || lower === '#fff' || lower === 'white' || lower === 'rgb(255,255,255)' || lower === 'rgba(255,255,255,1)') {
    return '#10b981'
  }
  return color
}

// Adapt DB entries to the MemoryEntry shape
const entries = computed<MemoryEntry[]>(() => {
  return rawDbEntries.value
    .map(e => ({
      date: e.trade_date,
      ticker: e.ticker,
      rating: e.rating || 'Hold',
      pending: false,
      raw: e.raw_return != null ? `${(e.raw_return * 100).toFixed(1)}%` : null,
      alpha: e.alpha_return != null ? `${(e.alpha_return * 100).toFixed(1)}%` : null,
      holding: e.holding_days != null ? `${e.holding_days}d` : null,
      decision: e.action || '',
      reflection: e.reflection || '',
      quick_model: e.quick_model,
      deep_model: e.deep_model,
      depth: String(e.depth),
      runtime_sec: e.runtime_sec != null ? String(e.runtime_sec) : '0',
      config_id: e.config_id,
    }))
    .sort((a, b) => a.date.localeCompare(b.date))
})

// Filters
const showCosts = ref(false)
const commissionPerTrade = ref(0.001) // 0.1% default simulation cost
const selectedTicker = ref(activeTicker.value || 'ALL')

watch(activeTicker, (v) => {
  if (v) {
    selectedTicker.value = v
  }
})

watch(selectedTicker, (v) => {
  if (v && v !== 'ALL') {
    setActiveTicker(v)
  }
})
const benchmarkType = ref<'SPY' | 'ASSET'>((localStorage.getItem('perf_benchmark') as any) || 'ASSET')
const strategySource = ref<'RATING' | 'ACTION'>((localStorage.getItem('perf_source') as any) || 'RATING')
const costModel = ref<'FLAT' | 'IBKR'>('FLAT')
const timeRange = ref<'1M' | '3M' | '6M' | 'YTD' | 'ALL' | 'CUSTOM'>((localStorage.getItem('perf_range') as any) || '6M')
const dateFrom = ref(localStorage.getItem('perf_from') || '')
const dateTo = ref(localStorage.getItem('perf_to') || '')

const showStrategyA = ref(localStorage.getItem('perf_show_strat_a') !== 'false')
const showStrategyB = ref(localStorage.getItem('perf_show_strat_b') !== 'false')

// Visible Chart Range (for dynamic stats)
const visibleTimeRange = ref<{ from: string; to: string } | null>(null)


// Persist Filters

watch(benchmarkType, (v) => localStorage.setItem('perf_benchmark', v))
watch(strategySource, (v) => localStorage.setItem('perf_source', v))
watch(timeRange, (v) => localStorage.setItem('perf_range', v))
watch(dateFrom, (v) => localStorage.setItem('perf_from', v))
watch(dateTo, (v) => localStorage.setItem('perf_to', v))
watch(showStrategyA, (v) => localStorage.setItem('perf_show_strat_a', String(v)))
watch(showStrategyB, (v) => localStorage.setItem('perf_show_strat_b', String(v)))


const expandedRows = ref<Set<string>>(new Set())




const filteredConfigs = computed(() => {
  if (!configsSearchQuery.value) return configs.value
  const q = configsSearchQuery.value.toLowerCase()
  return configs.value.filter(c => c.label.toLowerCase().includes(q))
})

function loadSharedConfigs() {
  try {
    const saved = localStorage.getItem('shared_enabled_configs')
    if (saved) {
      const parsed = JSON.parse(saved)
      if (Array.isArray(parsed) && parsed.length > 0) {
        enabledConfigs.value = new Set(parsed)
        return
      }
    }
  } catch (e) {
    console.error('Failed to parse shared configs', e)
  }
  enabledConfigs.value = new Set(configs.value.map(c => c.config_id))
}

function selectAllConfigs() {
  enabledConfigs.value = new Set(configs.value.map(c => c.config_id))
  localStorage.setItem('shared_enabled_configs', JSON.stringify(Array.from(enabledConfigs.value)))
  if (chart) initChart()
}

function clearAllConfigs() {
  enabledConfigs.value = new Set()
  localStorage.setItem('shared_enabled_configs', JSON.stringify([]))
  if (chart) initChart()
}

function handleStorageEvent(event: StorageEvent) {
  if (event.key === 'shared_enabled_configs') {
    loadSharedConfigs()
    if (chart) initChart()
  }
}

onMounted(async () => {
  await Promise.all([
    loadData(),
    loadRegistryTickers(),
    loadConfigs()
  ])
  window.addEventListener('storage', handleStorageEvent)
  initChart()
})

onUnmounted(() => {
  window.removeEventListener('storage', handleStorageEvent)
})

async function loadRegistryTickers() {
  try {
    registryTickers.value = await fetchTickers()
  } catch (e) {
    console.error('Failed to load registry tickers', e)
  }
}

async function loadConfigs() {
  try {
    configs.value = await fetchConfigs()
    loadSharedConfigs()
  } catch (e) {
    console.error('Failed to load configs', e)
  }
}

function toggleConfig(configId: string) {
  const s = new Set(enabledConfigs.value)
  if (s.has(configId)) s.delete(configId)
  else s.add(configId)
  enabledConfigs.value = s
  localStorage.setItem('shared_enabled_configs', JSON.stringify(Array.from(s)))
  if (chart) initChart()
}

async function loadData() {
  loading.value = true
  try {
    rawDbEntries.value = await fetchPerformanceData()
  } catch (e) {
    console.error('Failed to load performance data', e)
  } finally {
    loading.value = false
  }
}

async function handleClearMemory() {
  if (!confirm('Are you sure you want to clear all paper trade history? This will wipe the AI\'s performance memory and cannot be undone.')) {
    return
  }
  
  loading.value = true
  try {
    await clearMemoryEntries()
    rawDbEntries.value = []
  } catch (e) {
    console.error('Failed to clear memory', e)
    alert('Failed to clear memory log.')
  } finally {
    loading.value = false
  }
}


const availableTickers = computed(() => {
  const dbTickers = rawDbEntries.value.map(e => e.ticker)
  const regTickers = registryTickers.value.map(t => t.ticker)
  const all = new Set([...dbTickers, ...regTickers])
  return ['ALL', ...Array.from(all).sort()]
})

function parsePct(val: string | null): number {
  if (!val) return 0
  const parsed = parseFloat(val.replace('%', ''))
  return isNaN(parsed) ? 0 : parsed / 100
}


const filteredEntries = computed(() => {
  let result = entries.value
  
  // Apply Ticker Filter
  if (selectedTicker.value !== 'ALL') {
    result = result.filter(e => e.ticker === selectedTicker.value)
  }
  
  // Apply Time Range Filter
  if (timeRange.value === 'CUSTOM') {
    if (dateFrom.value) result = result.filter(e => e.date >= dateFrom.value)
    if (dateTo.value) result = result.filter(e => e.date <= dateTo.value)
  } else if (timeRange.value !== 'ALL') {
    const now = new Date()
    let cutoff = new Date()
    
    if (timeRange.value === '1M') cutoff.setMonth(now.getMonth() - 1)
    else if (timeRange.value === '3M') cutoff.setMonth(now.getMonth() - 3)
    else if (timeRange.value === '6M') cutoff.setMonth(now.getMonth() - 6)
    else if (timeRange.value === 'YTD') cutoff = new Date(now.getFullYear(), 0, 1)
    
    const cutoffStr = cutoff.toISOString().split('T')[0]
    result = result.filter(e => e.date >= cutoffStr)
  }


  // Apply Config Filter: only show enabled configurations
  if (enabledConfigs.value.size > 0) {
    result = result.filter(e => e.config_id && enabledConfigs.value.has(e.config_id))
  } else {
    result = []
  }
  
  return result
})

function padDate(val: string): string {
  if (!val) return val
  const parts = val.split('-').map(p => p.trim())
  if (parts.length === 3) {
    let [y, m, d] = parts
    if (y.length === 2) y = '20' + y
    if (m.length === 1) m = '0' + m
    if (d.length === 1) d = '0' + d
    if (y.length === 4 && m.length === 2 && d.length === 2) {
      return `${y}-${m}-${d}`
    }
  }
  return val
}

const visibleEntries = computed(() => {
  if (!visibleTimeRange.value) return filteredEntries.value
  return filteredEntries.value.filter(e => 
    e.date >= visibleTimeRange.value!.from && 
    e.date <= visibleTimeRange.value!.to
  )
})

function isWeekend(dateStr: string): boolean {
  const date = new Date(dateStr + 'T00:00:00Z')
  const day = date.getUTCDay()
  return day === 0 || day === 6
}

function getNextWeekday(dateStr: string): string {
  const d = new Date(dateStr + 'T00:00:00Z')
  do {
    d.setUTCDate(d.getUTCDate() + 1)
  } while (d.getUTCDay() === 0 || d.getUTCDay() === 6)
  return d.toISOString().split('T')[0]
}

function getWeekdaysBetween(startStr: string, endStr: string): string[] {
  const list: string[] = []
  const endDate = new Date(endStr + 'T00:00:00Z')
  const currDate = new Date(startStr + 'T00:00:00Z')
  
  while (currDate <= endDate) {
    const day = currDate.getUTCDay()
    if (day !== 0 && day !== 6) {
      list.push(currDate.toISOString().split('T')[0])
    }
    currDate.setUTCDate(currDate.getUTCDate() + 1)
  }
  return list
}

function getEndDateWithBuffer(lastDateStr: string, daysBuffer = 5): string {
  let curr = lastDateStr
  for (let i = 0; i < daysBuffer; i++) {
    curr = getNextWeekday(curr)
  }
  return curr
}

interface ActiveTrade {
  startIdx: number
  endIdx: number
  dailyReturn: number
  ticker: string
}

function getTargetWeight(rating: string, prevWeight: number): number {
  const r = rating.toLowerCase()
  if (r.includes('buy')) return 1.0
  if (r.includes('overweight')) return 1.5
  if (r.includes('underweight')) return 0.5
  if (r.includes('sell')) return 0.0
  return prevWeight
}

function computeConfigReturns(configEntries: MemoryEntry[]) {
  const weekdayEntries = configEntries.filter(e => !isWeekend(e.date))
  if (weekdayEntries.length === 0) {
    return {
      stratAPoints: [],
      stratBPoints: [],
      benchPoints: [],
      stratAROI: 0,
      stratBROI: 0,
      benchROI: 0,
    }
  }

  // Get active tickers in this config
  const activeTickers = Array.from(new Set(weekdayEntries.map(e => e.ticker)))
  const tickerCount = activeTickers.length || 1
  const slotsPerTicker = 5
  const totalSlots = slotsPerTicker * tickerCount

  // Group entries by date
  const dateGroups = new Map<string, MemoryEntry[]>()
  weekdayEntries.forEach(e => {
    if (!dateGroups.has(e.date)) dateGroups.set(e.date, [])
    dateGroups.get(e.date)!.push(e)
  })

  // Determine the sorted sequence of run dates
  const runDates = Array.from(new Set(weekdayEntries.map(e => e.date)))
    .filter(d => !isWeekend(d))
    .sort()

  if (runDates.length === 0) {
    return {
      stratAPoints: [],
      stratBPoints: [],
      benchPoints: [],
      stratAROI: 0,
      stratBROI: 0,
      benchROI: 0,
    }
  }

  // Generate a continuous sequence of weekdays starting from the first run date
  // to 5 weekdays after the last run date to allow all trades to compound to completion.
  const startDate = runDates[0]
  const lastRunDate = runDates[runDates.length - 1]
  const endDate = getEndDateWithBuffer(lastRunDate, 5)
  const datasetDates = getWeekdaysBetween(startDate, endDate)

  let stratAValue = 100
  let stratBValue = 100
  let benchValue = 100
  const stratAPoints: { time: string; value: number }[] = []
  const stratBPoints: { time: string; value: number }[] = []
  const benchPoints: { time: string; value: number }[] = []

  let stratATrades: ActiveTrade[] = []
  let benchTrades: ActiveTrade[] = []

  // Initialize weights for Strategy B
  const tickerWeights = new Map<string, number>()
  activeTickers.forEach(t => tickerWeights.set(t, 0.0))

  datasetDates.forEach((date, idx) => {
    // 1. Clear completed trades
    stratATrades = stratATrades.filter(t => idx < t.endIdx)
    benchTrades = benchTrades.filter(t => idx < t.endIdx)

    // 2. Add new trades starting today
    const dayEntries = dateGroups.get(date) || []
    let stratBTradeCostsToday = 0

    dayEntries.forEach(e => {
      const raw = parsePct(e.raw)
      const alpha = parsePct(e.alpha)
      const spy = raw - alpha

      const baseBench = Math.max(0.0001, 1 + (benchmarkType.value === 'SPY' ? spy : raw))
      const dailyBenchRet = Math.pow(baseBench, 1 / 5) - 1

      benchTrades.push({
        startIdx: idx,
        endIdx: idx + 5,
        dailyReturn: dailyBenchRet,
        ticker: e.ticker
      })

      const signal = strategySource.value === 'RATING' ? e.rating : e.decision
      const rating = (signal || '').toLowerCase()
      const isLong = rating.includes('buy') || rating.includes('overweight')

      if (isLong) {
        let dailyStratRet = dailyBenchRet
        if (showCosts.value) {
          const cost = costModel.value === 'IBKR' ? 0.0015 : commissionPerTrade.value
          dailyStratRet -= (cost / 5)
        }
        stratATrades.push({
          startIdx: idx,
          endIdx: idx + 5,
          dailyReturn: dailyStratRet,
          ticker: e.ticker
        })
      }

      // Update weight for Strategy B
      const prevWeight = tickerWeights.get(e.ticker) ?? 0.0
      const newWeight = getTargetWeight(rating, prevWeight)
      if (newWeight !== prevWeight) {
        tickerWeights.set(e.ticker, newWeight)
        if (showCosts.value) {
          const cost = costModel.value === 'IBKR' ? 0.0015 : commissionPerTrade.value
          const costForTicker = cost * Math.abs(newWeight - prevWeight) / tickerCount
          stratBTradeCostsToday += costForTicker
        }
      }
    })

    // 3. Compute daily returns across all slots for Strategy A & Benchmark
    const benchDailyRet = benchTrades.reduce((sum, t) => sum + t.dailyReturn, 0) / totalSlots
    const stratADailyRet = stratATrades.reduce((sum, t) => sum + t.dailyReturn, 0) / totalSlots

    // 4. Compute daily returns for Strategy B
    let stratBDailyRetSum = 0
    activeTickers.forEach(T => {
      const weight = tickerWeights.get(T) ?? 0.0
      const activeBenchTradesForTicker = benchTrades.filter(t => t.ticker === T)
      const sumActiveBenchReturns = activeBenchTradesForTicker.reduce((sum, t) => sum + t.dailyReturn, 0)
      const tickerDailyBenchmarkReturn = sumActiveBenchReturns / 5
      stratBDailyRetSum += weight * tickerDailyBenchmarkReturn
    })
    let stratBDailyRet = stratBDailyRetSum / tickerCount
    if (showCosts.value) {
      stratBDailyRet -= stratBTradeCostsToday
    }

    // 5. Compound
    benchValue = benchValue * (1 + benchDailyRet)
    stratAValue = stratAValue * (1 + stratADailyRet)
    stratBValue = stratBValue * (1 + stratBDailyRet)

    stratAPoints.push({ time: date, value: stratAValue })
    stratBPoints.push({ time: date, value: stratBValue })
    benchPoints.push({ time: date, value: benchValue })
  })

  return {
    stratAPoints,
    stratBPoints,
    benchPoints,
    stratAROI: stratAValue - 100,
    stratBROI: stratBValue - 100,
    benchROI: benchValue - 100,
  }
}

const multiConfigStats = computed(() => {
  if (visibleEntries.value.length === 0 || configs.value.length === 0) return []
  
  const targetConfigs = enabledConfigs.value.size > 0 
    ? configs.value.filter(c => enabledConfigs.value.has(c.config_id))
    : configs.value

  return targetConfigs
    .filter(config => visibleEntries.value.some(e => e.config_id === config.config_id))
    .map(config => {
      const cid = config.config_id
      const configEntries = visibleEntries.value.filter(e => e.config_id === cid)
      
      const winsA = configEntries.filter(e => {
        const signal = strategySource.value === 'RATING' ? e.rating : e.decision
        const isLong = (signal || '').toLowerCase().includes('buy') || (signal || '').toLowerCase().includes('overweight')
        const stratRet = isLong ? parsePct(e.raw) : 0
        const raw = parsePct(e.raw)
        const alpha = parsePct(e.alpha)
        const benchRet = benchmarkType.value === 'SPY' ? (raw - alpha) : raw
        return stratRet > benchRet
      }).length

      let winsB = 0
      const tickerWeights = new Map<string, number>()
      const sortedEntries = [...configEntries].sort((a, b) => a.date.localeCompare(b.date))
      sortedEntries.forEach(e => {
        const signal = strategySource.value === 'RATING' ? e.rating : e.decision
        const rating = (signal || '').toLowerCase()
        const prevWeight = tickerWeights.get(e.ticker) ?? 0.0
        const newWeight = getTargetWeight(rating, prevWeight)
        tickerWeights.set(e.ticker, newWeight)
        
        const raw = parsePct(e.raw)
        const alpha = parsePct(e.alpha)
        const benchRet = benchmarkType.value === 'SPY' ? (raw - alpha) : raw
        const stratRet = newWeight * benchRet
        
        if (stratRet > benchRet) {
          winsB++
        }
      })

      const { benchROI, stratAROI, stratBROI } = computeConfigReturns(configEntries)
      let totalRuntime = 0
      configEntries.forEach(e => {
        totalRuntime += parseFloat(e.runtime_sec || '0')
      })

      return {
        config,
        count: configEntries.length,
        winRateA: (winsA / configEntries.length) * 100,
        winRateB: (winsB / configEntries.length) * 100,
        totalAlphaA: stratAROI - benchROI,
        totalAlphaB: stratBROI - benchROI,
        stratAROI,
        stratBROI,
        benchROI,
        totalRuntime
      }
    })
})

const performanceData = computed(() => {
  const targetConfigs = enabledConfigs.value.size > 0 
    ? configs.value.filter(c => enabledConfigs.value.has(c.config_id))
    : configs.value

  const stratAMaps: Record<string, any[]> = {}
  const stratBMaps: Record<string, any[]> = {}
  let benchPoints: any[] = []

  targetConfigs.forEach(config => {
    const cid = config.config_id
    const configEntries = filteredEntries.value.filter(e => e.config_id === cid)
    if (configEntries.length === 0) return

    const { stratAPoints, stratBPoints, benchPoints: currentBenchPoints } = computeConfigReturns(configEntries)
    
    stratAMaps[cid] = stratAPoints
    stratBMaps[cid] = stratBPoints
    if (benchPoints.length === 0) benchPoints = currentBenchPoints
  })

  return { stratAMaps, stratBMaps, benchPoints }
})



function initChart() {
  if (!chartContainer.value) return
  
  chart = createChart(chartContainer.value, {
    layout: {
      background: { type: ColorType.Solid, color: 'transparent' },
      textColor: '#94a3b8',
    },
    grid: {
      vertLines: { color: '#1e293b' },
      horzLines: { color: '#1e293b' },
    },
    rightPriceScale: {
      borderColor: '#1e293b',
      autoScale: true,
    },
    timeScale: {
      borderColor: '#1e293b',
      timeVisible: false,
    },
    handleScroll: true,
    handleScale: true,
  })

  // Benchmark is always added once
  benchmarkSeries = chart.addSeries(LineSeries, {
    color: '#ffffff',
    lineWidth: 2,
    lineStyle: LineStyle.Dashed, 
    title: 'Benchmark',
  })

  // Subscribe to visible range changes
  chart.timeScale().subscribeVisibleTimeRangeChange((range: any) => {
    if (range && range.from && range.to) {
       try {
         const from = typeof range.from === 'string' ? range.from : new Date(range.from * 1000).toISOString().split('T')[0]
         const to = typeof range.to === 'string' ? range.to : new Date(range.to * 1000).toISOString().split('T')[0]
         visibleTimeRange.value = { from, to }
       } catch (e) {
         console.warn("Invalid chart range:", range)
       }
    }
  })

  // Handle Resizing
  const handleResize = () => {
    if (chart && chartContainer.value) {
      chart.applyOptions({ 
        width: chartContainer.value.clientWidth,
        height: chartContainer.value.clientHeight 
      })
    }
  }
  window.addEventListener('resize', handleResize)
  
  updateChart()
  // Force a resize calculation after initial render
  setTimeout(handleResize, 100)
}


function updateChart() {
  if (!chart || !benchmarkSeries) return
  
  // Clear old strategy series
  strategySeriesMap.forEach(s => chart.removeSeries(s))
  strategySeriesMap.clear()

  const { stratAMaps, stratBMaps, benchPoints } = performanceData.value
  
  // Set Benchmark
  if (benchPoints.length > 0) {
    benchmarkSeries.setData(benchPoints)
  }

  // Add Strategy A series if enabled
  if (showStrategyA.value) {
    Object.entries(stratAMaps).forEach(([cid, data]) => {
      const config = configs.value.find(c => c.config_id === cid)
      if (!config) return

      const series = chart.addSeries(LineSeries, {
        color: safeConfigColor(config),
        lineWidth: 3,
        title: `${config.label} (Current)`,
      })
      series.setData(data)
      strategySeriesMap.set(`${cid}_A`, series)
    })
  }

  // Add Strategy B series if enabled
  if (showStrategyB.value) {
    Object.entries(stratBMaps).forEach(([cid, data]) => {
      const config = configs.value.find(c => c.config_id === cid)
      if (!config) return

      const series = chart.addSeries(LineSeries, {
        color: safeConfigColor(config),
        lineWidth: 3,
        lineStyle: LineStyle.Dotted,
        title: `${config.label} (Strat B)`,
      })
      series.setData(data)
      strategySeriesMap.set(`${cid}_B`, series)
    })
  }

  if (benchPoints.length > 0) {
    chart.timeScale().fitContent()
  }
}


watch([showCosts, performanceData, benchmarkType, strategySource, costModel, timeRange, enabledConfigs, showStrategyA, showStrategyB], () => {
  updateChart()
})



function toggleRow(id: string) {
  if (expandedRows.value.has(id)) expandedRows.value.delete(id)
  else expandedRows.value.add(id)
}



function getSignalLabel(text: string) {
  const t = text.toLowerCase()
  if (t.includes('buy')) return 'BUY'
  if (t.includes('sell')) return 'SELL'
  if (t.includes('overweight')) return 'OVERWEIGHT'
  if (t.includes('underweight')) return 'UNDERWEIGHT'
  return 'HOLD'
}

function getEntryStratRet(entry: MemoryEntry) {
  const signal = strategySource.value === 'RATING' ? entry.rating : entry.decision
  const isLong = (signal || '').toLowerCase().includes('buy') || (signal || '').toLowerCase().includes('overweight')
  return isLong ? parsePct(entry.raw) : 0
}

function getEntryBenchRet(entry: MemoryEntry) {
  const raw = parsePct(entry.raw)
  const alpha = parsePct(entry.alpha)
  return benchmarkType.value === 'SPY' ? (raw - alpha) : raw
}

function getEntryAlpha(entry: MemoryEntry) {
  return getEntryStratRet(entry) - getEntryBenchRet(entry)
}

const TIME_RANGES = ['1M', '3M', '6M', 'YTD', 'ALL'] as const

</script>

<template>
  <div class="p-6 max-w-7xl mx-auto space-y-6 pb-20 md:pb-6">
    <!-- Header -->
    <div class="flex flex-col md:flex-row md:items-center justify-between gap-4">
      <div>
        <h1 class="text-2xl font-bold flex items-center gap-2">
          <Trophy class="text-[var(--color-accent-primary)]" />
          Performance Dashboard
        </h1>
        <p class="text-[var(--color-text-muted)] text-sm mt-1">
          Tracking the cumulative performance of AI-driven paper trades.
        </p>
      </div>
      
      <div class="flex flex-col items-end gap-3">
        <!-- Row 1: Primary Filters -->
        <div class="flex flex-wrap items-center justify-end gap-3">
          <!-- Ticker Filter -->
          <div class="flex items-center gap-2 px-3 py-1.5 bg-[var(--color-bg-elevated)] border border-[var(--color-border-default)] rounded-lg">
            <Filter :size="14" class="text-[var(--color-text-muted)]" />
            <select v-model="selectedTicker" class="bg-transparent border-none text-xs font-bold focus:ring-0 cursor-pointer">
              <option v-for="t in availableTickers" :key="t" :value="t">{{ t }}</option>
            </select>
          </div>

          <!-- Time Range -->
          <div class="flex items-center gap-4 bg-[var(--color-bg-elevated)] p-1.5 rounded-xl border border-[var(--color-border-default)]">
            <div class="flex items-center p-1 bg-black/20 rounded-lg">
              <button 
                v-for="range in TIME_RANGES" 
                :key="range"
                @click="timeRange = range; dateFrom = ''; dateTo = ''"
                class="px-2 py-1 text-[10px] font-bold rounded transition-colors"
                :class="timeRange === range ? 'bg-[var(--color-accent-primary)] text-white' : 'text-[var(--color-text-muted)] hover:text-white'"
              >
                {{ range }}
              </button>
            </div>
            <div class="w-px h-8 bg-[var(--color-border-default)]"></div>
            <div class="flex items-center gap-3 px-2">
              <div class="flex flex-col gap-0.5">
                <span class="text-[9px] uppercase font-black text-[var(--color-text-muted)]">Start Date</span>
                <input v-model="dateFrom" @input="timeRange = 'CUSTOM'" @blur="dateFrom = padDate(dateFrom)" type="text" placeholder="YYYY-MM-DD" class="bg-transparent border-none text-[11px] font-bold focus:ring-0 w-24 p-0" />
              </div>
              <div class="flex flex-col gap-0.5">
                <span class="text-[9px] uppercase font-black text-[var(--color-text-muted)]">End Date</span>
                <input v-model="dateTo" @input="timeRange = 'CUSTOM'" @blur="dateTo = padDate(dateTo)" type="text" placeholder="YYYY-MM-DD" class="bg-transparent border-none text-[11px] font-bold focus:ring-0 w-24 p-0" />
              </div>
            </div>
          </div>
        </div>

        <!-- Row 2: Strategy & Benchmark -->
        <div class="flex flex-wrap items-center justify-end gap-3">
          <!-- Benchmark Toggle -->
          <div class="flex flex-col gap-1">
            <div class="flex items-center gap-1.5 ml-1">
              <span class="text-[10px] uppercase font-black text-[var(--color-text-muted)]">Benchmark</span>
              <div class="group relative">
                <Info :size="10" class="text-[var(--color-text-muted)] cursor-help hover:text-[var(--color-text-primary)] transition-colors" />
                <div class="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 w-48 p-2 bg-[var(--color-bg-card)] border border-[var(--color-border-default)] rounded-lg text-[10px] text-[var(--color-text-primary)] opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none z-50 shadow-2xl backdrop-blur-md">
                  Compare against holding the asset itself, or against the S&P 500 index.
                </div>
              </div>
            </div>
            <div class="flex items-center gap-2 px-3 py-1.5 bg-[var(--color-bg-elevated)] border border-[var(--color-border-default)] rounded-lg">
              <BarChart3 :size="14" class="text-[var(--color-text-muted)]" />
              <select v-model="benchmarkType" class="bg-transparent border-none text-xs font-bold focus:ring-0 cursor-pointer">
                <option value="SPY">S&P 500 (SPY)</option>
                <option value="ASSET">Buy & Hold (Asset)</option>
              </select>
            </div>
          </div>

          <!-- Strategy Source -->
          <div class="flex flex-col gap-1">
            <div class="flex items-center gap-1.5 ml-1">
              <span class="text-[10px] uppercase font-black text-[var(--color-text-muted)]">AI Signal Source</span>
              <div class="group relative">
                <Info :size="10" class="text-[var(--color-text-muted)] cursor-help hover:text-[var(--color-text-primary)] transition-colors" />
                <div class="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 w-56 p-2 bg-[var(--color-bg-card)] border border-[var(--color-border-default)] rounded-lg text-[10px] text-[var(--color-text-primary)] opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none z-50 shadow-2xl backdrop-blur-md">
                  <strong>Expert Ratings:</strong> Raw consensus of all AI analysts.<br>
                  <strong>Final Actions:</strong> The Portfolio Manager's definitive decision.
                </div>
              </div>
            </div>
            <div class="flex items-center gap-2 px-3 py-1.5 bg-[var(--color-bg-elevated)] border border-[var(--color-border-default)] rounded-lg">
              <Info :size="14" class="text-[var(--color-text-muted)]" />
              <select v-model="strategySource" class="bg-transparent border-none text-xs font-bold focus:ring-0 cursor-pointer">
                <option value="RATING">Expert Ratings</option>
                <option value="ACTION">Final Actions (PM)</option>
              </select>
            </div>
          </div>

          <!-- Strategies Selector -->
          <div class="flex flex-col gap-1">
            <div class="flex items-center gap-1.5 ml-1">
              <span class="text-[10px] uppercase font-black text-[var(--color-text-muted)]">Strategies</span>
              <div class="group relative">
                <Info :size="10" class="text-[var(--color-text-muted)] cursor-help hover:text-[var(--color-text-primary)] transition-colors" />
                <div class="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 w-48 p-2 bg-[var(--color-bg-card)] border border-[var(--color-border-default)] rounded-lg text-[10px] text-[var(--color-text-primary)] opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none z-50 shadow-2xl backdrop-blur-md">
                  Select which trading strategies to visualize and compare.
                </div>
              </div>
            </div>
            <div class="flex items-center gap-2 px-3 py-1.5 bg-[var(--color-bg-elevated)] border border-[var(--color-border-default)] rounded-lg">
              <label class="flex items-center gap-1.5 cursor-pointer text-xs font-bold text-white select-none">
                <input type="checkbox" v-model="showStrategyA" class="rounded bg-white/5 border-white/10 text-[var(--color-accent-primary)] focus:ring-0 focus:ring-offset-0 w-3.5 h-3.5" />
                <span>Current</span>
              </label>
              <div class="w-px h-4 bg-[var(--color-border-default)]"></div>
              <label class="flex items-center gap-1.5 cursor-pointer text-xs font-bold text-white select-none">
                <input type="checkbox" v-model="showStrategyB" class="rounded bg-white/5 border-white/10 text-[var(--color-accent-primary)] focus:ring-0 focus:ring-offset-0 w-3.5 h-3.5" />
                <span>Strat B</span>
              </label>
            </div>
          </div>

          <!-- Cost Simulation -->
          <div class="flex flex-col gap-1">
            <div class="flex items-center gap-1.5 ml-1">
              <span class="text-[10px] uppercase font-black text-[var(--color-text-muted)]">Trade Costs</span>
              <div class="group relative">
                <Info :size="10" class="text-[var(--color-text-muted)] cursor-help hover:text-[var(--color-text-primary)] transition-colors" />
                <div class="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 w-48 p-2 bg-[var(--color-bg-card)] border border-[var(--color-border-default)] rounded-lg text-[10px] text-[var(--color-text-primary)] opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none z-50 shadow-2xl backdrop-blur-md">
                  Simulate realistic trading fees and market slippage for each action.
                </div>
              </div>
            </div>
            <div class="flex items-center gap-3 px-3 py-1.5 bg-[var(--color-bg-elevated)] border border-[var(--color-border-default)] rounded-lg">
              <select v-if="showCosts" v-model="costModel" class="bg-transparent border-none text-[10px] font-bold focus:ring-0 cursor-pointer p-0 mr-1">
                <option value="FLAT">0.1% Flat</option>
                <option value="IBKR">IBKR Tiered</option>
              </select>
              <button 
                @click="showCosts = !showCosts"
                class="relative inline-flex h-4 w-7 items-center rounded-full transition-colors focus:outline-none"
                :class="showCosts ? 'bg-[var(--color-accent-primary)]' : 'bg-gray-700'"
              >
                <span 
                  class="inline-block h-2.5 w-2.5 transform rounded-full bg-white transition-transform"
                  :class="showCosts ? 'translate-x-3.5' : 'translate-x-1'"
                />
              </button>
            </div>
          </div>

          <div class="flex items-center gap-2 mt-auto pb-0.5">
            <button @click="loadData" class="p-2 rounded-lg bg-[var(--color-bg-elevated)] hover:bg-[var(--color-bg-card)] border border-[var(--color-border-default)] transition-colors">
              <RefreshCw :size="18" :class="{ 'animate-spin': loading }" />
            </button>
            <button 
              @click="handleClearMemory" 
              class="p-2 rounded-lg bg-[var(--color-bg-elevated)] hover:bg-red-500/20 text-[var(--color-text-muted)] hover:text-red-400 border border-[var(--color-border-default)] transition-colors"
              title="Clear History"
            >
              <Trash2 :size="18" />
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- Quick Select Tickers -->
    <div class="flex flex-wrap gap-2 items-center bg-[var(--color-bg-card)] border border-[var(--color-border-default)] p-3 rounded-xl shadow-sm">
      <span class="text-xs font-black uppercase text-[var(--color-text-muted)] mr-2">Quick Select:</span>
      <button
        @click="selectedTicker = 'ALL'"
        class="px-3 py-1.5 rounded-lg text-xs font-bold transition-all border"
        :class="selectedTicker === 'ALL'
          ? 'bg-[var(--color-accent-primary)] text-white border-[var(--color-accent-primary)] shadow-sm shadow-[var(--color-accent-primary)]/20'
          : 'bg-[var(--color-bg-elevated)] text-[var(--color-text-muted)] border-[var(--color-border-default)] hover:text-[var(--color-text-primary)] hover:border-[var(--color-text-muted)]'"
      >
        ALL
      </button>
      <button
        v-for="ticker in selectedTickers"
        :key="ticker"
        @click="selectedTicker = ticker"
        class="px-3 py-1.5 rounded-lg text-xs font-bold transition-all border"
        :class="selectedTicker === ticker
          ? 'bg-[var(--color-accent-primary)] text-white border-[var(--color-accent-primary)] shadow-sm shadow-[var(--color-accent-primary)]/20'
          : 'bg-[var(--color-bg-elevated)] text-[var(--color-text-muted)] border-[var(--color-border-default)] hover:text-[var(--color-text-primary)] hover:border-[var(--color-text-muted)]'"
      >
        {{ ticker }}
      </button>
    </div>

      <!-- Simulation Configs Filter Panel -->
      <div v-if="configs.length > 0" class="bg-white/5 p-4 rounded-xl border border-white/10 mt-4 flex flex-col gap-3 shadow-lg">
        <div class="flex flex-col md:flex-row md:items-center justify-between gap-3 border-b border-white/5 pb-3">
          <div class="flex items-center gap-2">
            <Filter :size="14" class="text-[var(--color-accent-primary)] opacity-80" />
            <span class="text-xs uppercase font-black tracking-widest text-white">Isolate Simulation Configs</span>
            <span class="text-[10px] text-[var(--color-text-muted)] font-mono">({{ enabledConfigs.size }} / {{ configs.length }} active)</span>
          </div>
          
          <!-- Controls & Search Bar -->
          <div class="flex flex-wrap items-center gap-2">
            <!-- Small Autocomplete/Search input -->
            <div class="relative w-44">
              <Search class="absolute left-2.5 top-1/2 -translate-y-1/2 text-white/40" :size="12" />
              <input 
                v-model="configsSearchQuery"
                type="text" 
                placeholder="Search configs..." 
                class="w-full pl-7 pr-2.5 py-1 bg-white/5 border border-white/10 rounded-lg text-[10px] focus:outline-none focus:border-[var(--color-accent-primary)] text-white font-medium bg-[#0f172a]"
              />
            </div>
            
            <button 
              @click="selectAllConfigs" 
              class="px-2.5 py-1 rounded bg-white/5 hover:bg-white/10 border border-white/10 text-[9px] font-black uppercase tracking-wider text-white transition-colors"
            >
              Select All
            </button>
            <button 
              @click="clearAllConfigs" 
              class="px-2.5 py-1 rounded bg-red-500/10 hover:bg-red-500/20 border border-red-500/20 text-[9px] font-black uppercase tracking-wider text-red-400 transition-colors"
            >
              Clear All
            </button>
          </div>
        </div>

        <!-- Config Buttons list: capped height with premium scrolling -->
        <div class="max-h-24 overflow-y-auto pr-1 custom-scrollbar">
          <div class="flex flex-wrap gap-2 py-0.5">
            <button
              v-for="c in filteredConfigs"
              :key="c.config_id"
              @click="toggleConfig(c.config_id)"
              class="flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs font-bold border transition-all select-none"
              :class="enabledConfigs.has(c.config_id)
                ? 'border-white/20 bg-white/10 text-white shadow-sm'
                : 'border-white/5 bg-white/[0.02] text-[var(--color-text-muted)] opacity-40'"
            >
              <div class="w-2.5 h-2.5 rounded-full" :style="{ backgroundColor: safeConfigColor(c) }"></div>
              <span>{{ c.label }}</span>
            </button>
            <div v-if="filteredConfigs.length === 0" class="text-[10px] text-[var(--color-text-muted)] italic py-2 pl-1">
              No configurations match your search criteria.
            </div>
          </div>
        </div>
      </div>
    <div class="space-y-4">
      <div v-for="s in multiConfigStats" :key="s.config.config_id" 
           class="glass p-4 rounded-2xl border border-[var(--color-border-default)] transition-all hover:border-white/20"
           :style="{ borderLeft: `4px solid ${safeConfigColor(s.config)}` }">
        <div class="flex flex-wrap items-center justify-between gap-4">
          <!-- Config Header -->
          <div class="flex flex-col min-w-[200px]">
            <span class="text-[10px] uppercase font-black text-[var(--color-text-muted)] tracking-widest">Simulation Config</span>
            <span class="text-sm font-bold text-white">{{ s.config.label }}</span>
            <div class="flex items-center gap-2 mt-1">
               <span class="text-[10px] text-[var(--color-text-muted)]">{{ s.count }} Trades</span>
            </div>
          </div>

          <!-- KPI Mini Cards -->
          <div class="flex flex-1 flex-wrap gap-4 md:gap-8 justify-end">
            <!-- Efficiency -->
            <div class="flex flex-col items-end">
              <div class="flex items-center gap-1.5 mb-1">
                <span class="text-[9px] uppercase font-bold text-yellow-400">Efficiency</span>
                <div class="group/tt relative">
                  <Info :size="10" class="text-yellow-400/50 cursor-help hover:text-yellow-400 transition-colors" />
                  <div class="absolute bottom-full right-0 mb-2 w-56 p-2 bg-[var(--color-bg-card)] border border-yellow-500/20 rounded-lg text-[10px] text-white opacity-0 group-hover/tt:opacity-100 transition-opacity pointer-events-none z-50 shadow-2xl backdrop-blur-md">
                    <strong>Alpha per Minute:</strong> How much excess return the AI generates for every 60 seconds of "thinking" time. Helps identify high-performance models that aren't over-calculating.
                  </div>
                </div>
              </div>
              <div class="flex items-center gap-2">
                <div class="flex flex-col items-end bg-white/[0.02] px-2 py-0.5 rounded border border-white/5 min-w-[50px]">
                  <span class="text-[8px] text-[var(--color-text-muted)] uppercase font-medium">Curr</span>
                  <span class="text-xs font-bold text-yellow-400/90">{{ (s.totalAlphaA / (s.totalRuntime / 60 || 1)).toFixed(2) }}</span>
                </div>
                <div class="flex flex-col items-end bg-white/[0.02] px-2 py-0.5 rounded border border-white/5 min-w-[50px]">
                  <span class="text-[8px] text-[var(--color-text-muted)] uppercase font-medium">Strat B</span>
                  <span class="text-xs font-bold text-yellow-300">{{ (s.totalAlphaB / (s.totalRuntime / 60 || 1)).toFixed(2) }}</span>
                </div>
              </div>
            </div>

            <!-- Win Rate -->
            <div class="flex flex-col items-end">
              <div class="flex items-center gap-1.5 mb-1">
                <span class="text-[9px] uppercase font-bold text-[var(--color-text-muted)]">Win Rate</span>
                <div class="group/tt relative">
                  <Info :size="10" class="text-[var(--color-text-muted)] cursor-help hover:text-[var(--color-text-primary)] transition-colors" />
                  <div class="absolute bottom-full right-0 mb-2 w-48 p-2 bg-[var(--color-bg-card)] border border-[var(--color-border-default)] rounded-lg text-[10px] text-white opacity-0 group-hover/tt:opacity-100 transition-opacity pointer-events-none z-50 shadow-2xl backdrop-blur-md">
                    Percentage of trades/actions that resulted in a positive return relative to the benchmark.
                  </div>
                </div>
              </div>
              <div class="flex items-center gap-2">
                <div class="flex flex-col items-end bg-white/[0.02] px-2 py-0.5 rounded border border-white/5 min-w-[50px]">
                  <span class="text-[8px] text-[var(--color-text-muted)] uppercase font-medium">Curr</span>
                  <span class="text-xs font-bold text-blue-400">{{ s.winRateA.toFixed(1) }}%</span>
                </div>
                <div class="flex flex-col items-end bg-white/[0.02] px-2 py-0.5 rounded border border-white/5 min-w-[50px]">
                  <span class="text-[8px] text-[var(--color-text-muted)] uppercase font-medium">Strat B</span>
                  <span class="text-xs font-bold text-blue-300">{{ s.winRateB.toFixed(1) }}%</span>
                </div>
              </div>
            </div>

            <!-- Total Alpha -->
            <div class="flex flex-col items-end">
              <div class="flex items-center gap-1.5 mb-1">
                <span class="text-[9px] uppercase font-bold text-[var(--color-text-muted)]">Total Alpha</span>
                <div class="group/tt relative">
                  <Info :size="10" class="text-[var(--color-text-muted)] cursor-help hover:text-[var(--color-text-primary)] transition-colors" />
                  <div class="absolute bottom-full right-0 mb-2 w-48 p-2 bg-[var(--color-bg-card)] border border-[var(--color-border-default)] rounded-lg text-[10px] text-white opacity-0 group-hover/tt:opacity-100 transition-opacity pointer-events-none z-50 shadow-2xl backdrop-blur-md">
                    Excess return generated by the strategy relative to the chosen benchmark.
                  </div>
                </div>
              </div>
              <div class="flex items-center gap-2">
                <div class="flex flex-col items-end bg-white/[0.02] px-2 py-0.5 rounded border border-white/5 min-w-[50px]">
                  <span class="text-[8px] text-[var(--color-text-muted)] uppercase font-medium">Curr</span>
                  <span class="text-xs font-bold" :class="s.totalAlphaA >= 0 ? 'text-green-400' : 'text-red-400'">
                    {{ s.totalAlphaA >= 0 ? '+' : '' }}{{ s.totalAlphaA.toFixed(1) }}%
                  </span>
                </div>
                <div class="flex flex-col items-end bg-white/[0.02] px-2 py-0.5 rounded border border-white/5 min-w-[50px]">
                  <span class="text-[8px] text-[var(--color-text-muted)] uppercase font-medium">Strat B</span>
                  <span class="text-xs font-bold" :class="s.totalAlphaB >= 0 ? 'text-green-300' : 'text-red-300'">
                    {{ s.totalAlphaB >= 0 ? '+' : '' }}{{ s.totalAlphaB.toFixed(1) }}%
                  </span>
                </div>
              </div>
            </div>

            <!-- Strategy ROI -->
            <div class="flex flex-col items-end">
              <div class="flex items-center gap-1.5 mb-1">
                <span class="text-[9px] uppercase font-bold text-[var(--color-text-muted)]">Strategy ROI</span>
                <div class="group/tt relative">
                  <Info :size="10" class="text-[var(--color-text-muted)] cursor-help hover:text-[var(--color-text-primary)] transition-colors" />
                  <div class="absolute bottom-full right-0 mb-2 w-48 p-2 bg-[var(--color-bg-card)] border border-[var(--color-border-default)] rounded-lg text-[10px] text-white opacity-0 group-hover/tt:opacity-100 transition-opacity pointer-events-none z-50 shadow-2xl backdrop-blur-md">
                    Total cumulative return on investment generated by following strategy signals.
                  </div>
                </div>
              </div>
              <div class="flex items-center gap-2">
                <div class="flex flex-col items-end bg-white/[0.02] px-2 py-0.5 rounded border border-white/5 min-w-[50px]">
                  <span class="text-[8px] text-[var(--color-text-muted)] uppercase font-medium">Curr</span>
                  <span class="text-xs font-bold text-[var(--color-accent-primary)]">{{ s.stratAROI.toFixed(1) }}%</span>
                </div>
                <div class="flex flex-col items-end bg-white/[0.02] px-2 py-0.5 rounded border border-white/5 min-w-[50px]">
                  <span class="text-[8px] text-[var(--color-text-muted)] uppercase font-medium">Strat B</span>
                  <span class="text-xs font-bold text-emerald-400">{{ s.stratBROI.toFixed(1) }}%</span>
                </div>
              </div>
            </div>

            <!-- Benchmark (Common) -->
            <div class="flex flex-col items-end justify-center">
              <div class="flex items-center gap-1.5 mb-1">
                <span class="text-[9px] uppercase font-bold text-[var(--color-text-muted)]">Benchmark</span>
                <div class="group/tt relative">
                  <Info :size="10" class="text-[var(--color-text-muted)] cursor-help hover:text-[var(--color-text-primary)] transition-colors" />
                  <div class="absolute bottom-full right-0 mb-2 w-48 p-2 bg-[var(--color-bg-card)] border border-[var(--color-border-default)] rounded-lg text-[10px] text-white opacity-0 group-hover/tt:opacity-100 transition-opacity pointer-events-none z-50 shadow-2xl backdrop-blur-md">
                    Return of a reference asset (e.g. Buy & Hold of the underlying stock) over the same period.
                  </div>
                </div>
              </div>
              <div class="flex items-center justify-center bg-white/[0.02] px-3 py-1 rounded border border-white/5 min-h-[30px] min-w-[70px]">
                <span class="text-sm font-bold text-[#6366f1]">{{ s.benchROI.toFixed(1) }}%</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>


    <!-- Chart -->
    <div class="glass p-4 rounded-2xl border border-[var(--color-border-default)]">
      <div class="flex items-center justify-between mb-4 px-2">
        <h3 class="font-bold flex items-center gap-2 text-sm md:text-base">
          Cumulative Return (Indexed to 100)
          <div class="group relative inline-block">
            <Info :size="14" class="text-[var(--color-text-muted)] cursor-help" />
            <div class="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 w-64 p-3 bg-[var(--color-bg-card)] border border-[var(--color-border-default)] rounded-lg shadow-2xl text-[10px] opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none z-50">
              <p class="font-bold text-[var(--color-accent-primary)] mb-1">Strategy Logic</p>
              <p class="mb-2">Cumulative ROI based on {{ strategySource === 'RATING' ? 'Expert Ratings (Overweight/Buy)' : 'Final Portfolio Actions (Buy/Hold)' }}.</p>
              <p class="font-bold text-[var(--color-accent-primary)] mb-1">Benchmark</p>
              <p>{{ benchmarkType === 'SPY' ? 'S&P 500 Index (SPY) for the same period.' : 'Pure Buy & Hold strategy for the underlying assets.' }}</p>
            </div>

          </div>
        </h3>
        <div class="flex flex-wrap items-center gap-3 text-[10px] font-bold uppercase tracking-wider">
          <!-- Dynamic Strategy Toggles -->
          <button 
            v-for="c in configs" 
            :key="c.config_id" 
            @click="toggleConfig(c.config_id)"
            class="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg border transition-all cursor-pointer select-none"
            :class="enabledConfigs.has(c.config_id) 
              ? 'bg-white/5 border-white/10 opacity-100 hover:bg-white/10 text-white' 
              : 'bg-transparent border-transparent opacity-30 hover:opacity-50 text-[var(--color-text-muted)]'"
          >
            <div class="w-2.5 h-2.5 rounded-full" :style="{ backgroundColor: safeConfigColor(c) }"></div>
            <span>{{ c.label }}</span>
          </button>
          <div v-if="showStrategyA" class="flex items-center gap-1.5 bg-white/5 px-2.5 py-1.5 rounded-lg border border-white/5 text-white">
            <div class="w-4 h-0.5 bg-[var(--color-accent-primary)]"></div>
            <span>Current (Solid)</span>
          </div>
          <div v-if="showStrategyB" class="flex items-center gap-1.5 bg-white/5 px-2.5 py-1.5 rounded-lg border border-white/5 text-white">
            <div class="w-4 h-0.5 border-t-2 border-dotted border-[var(--color-accent-primary)]"></div>
            <span>Strat B (Dotted)</span>
          </div>
          <!-- Benchmark Legend -->
          <div class="flex items-center gap-1.5 bg-white/5 px-2.5 py-1.5 rounded-lg border border-white/5 text-white">
            <div class="w-2.5 h-2.5 rounded-full bg-white border border-dashed border-white/40"></div>
            <span>Benchmark ({{ benchmarkType === 'SPY' ? 'S&P 500' : 'Hold' }})</span>
          </div>
        </div>
      </div>
      <div ref="chartContainer" class="h-80 w-full"></div>
    </div>

    <!-- Trade List -->
    <div class="glass overflow-hidden rounded-2xl border border-[var(--color-border-default)]">
      <div class="p-4 border-b border-[var(--color-border-default)] bg-[var(--color-bg-elevated)]/50 flex items-center justify-between">
        <h3 class="font-bold">Paper Trade History</h3>
        <span class="text-xs text-[var(--color-text-muted)] font-mono">{{ filteredEntries.length }} entries</span>
      </div>
      <div class="overflow-x-auto">
        <table class="w-full text-left border-collapse">
          <thead>
            <tr class="text-xs uppercase tracking-wider text-[var(--color-text-muted)] border-b border-[var(--color-border-default)]">
              <th class="px-6 py-4 font-semibold">Date</th>
              <th class="px-6 py-4 font-semibold">Ticker</th>
              <th class="px-6 py-4 font-semibold">Sim Configuration</th>
              <th class="px-6 py-4 font-semibold text-right">Strat Return</th>
              <th class="px-6 py-4 font-semibold text-right">Bench Return</th>
              <th class="px-6 py-4 font-semibold text-right">Alpha</th>
              <th class="px-6 py-4 font-semibold text-right">Runtime</th>
              <th class="px-6 py-4 font-semibold text-right">Details</th>
            </tr>

          </thead>
          <tbody class="divide-y divide-white/[0.03]">

            <template v-for="entry in [...filteredEntries].reverse()" :key="entry.date + entry.ticker">
              <tr class="hover:bg-white/[0.02] transition-colors group border-b border-white/[0.03]">
                <td class="px-6 py-4 text-sm font-mono text-[var(--color-text-muted)]">{{ entry.date }}</td>
                <td class="px-6 py-4 font-bold">{{ entry.ticker }}</td>
                <td class="px-6 py-4">
                  <div class="flex flex-col gap-1.5 py-1">
                    <div class="flex items-center gap-2">
                      <span class="text-[8px] font-black uppercase text-amber-500/70 tracking-widest w-10">Quick</span>
                      <span class="text-[10px] font-bold text-white/90 bg-white/5 px-2 py-0.5 rounded border border-white/5 font-mono">{{ entry.quick_model }}</span>
                    </div>
                    <div class="flex items-center gap-2">
                      <span class="text-[8px] font-black uppercase text-blue-400/70 tracking-widest w-10">Deep</span>
                      <span class="text-[10px] font-bold text-white/90 bg-white/5 px-2 py-0.5 rounded border border-white/5 font-mono">{{ entry.deep_model }}</span>
                    </div>
                    <div class="flex items-center gap-2">
                      <span class="text-[8px] font-black uppercase text-purple-400/70 tracking-widest w-10">Depth</span>
                      <span class="text-[9px] font-bold text-purple-400/90 bg-purple-500/10 px-2 py-0.5 rounded border border-purple-500/10 font-mono">{{ entry.depth }} Rounds</span>
                      
                      <span class="text-[8px] font-bold px-1.5 py-0.5 rounded border font-mono ml-auto"
                            :class="getSignalLabel(entry.rating) === 'BUY' || getSignalLabel(entry.rating) === 'OVERWEIGHT' ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/10'
                                  : getSignalLabel(entry.rating) === 'SELL' || getSignalLabel(entry.rating) === 'UNDERWEIGHT' ? 'bg-rose-500/10 text-rose-400 border-rose-500/10'
                                  : 'bg-amber-500/5 text-amber-500/80 border-amber-500/10'">
                        {{ getSignalLabel(entry.rating) }}
                      </span>
                    </div>
                  </div>
                </td>

                <!-- Realized Strategy Return -->
                <td class="px-6 py-4 text-right font-mono font-bold text-sm" :class="getEntryStratRet(entry) >= 0 ? 'text-green-400' : 'text-red-400'">
                  {{ (getEntryStratRet(entry) * 100).toFixed(2) }}%
                </td>

                <!-- Benchmark Return -->
                <td class="px-6 py-4 text-right font-mono text-xs text-[var(--color-text-muted)]">
                  {{ (getEntryBenchRet(entry) * 100).toFixed(2) }}%
                </td>

                <!-- Realized Alpha -->
                <td class="px-6 py-4 text-right font-mono font-bold text-sm" :class="getEntryAlpha(entry) >= 0 ? 'text-green-400' : 'text-red-400'">
                  {{ getEntryAlpha(entry) >= 0 ? '+' : '' }}{{ (getEntryAlpha(entry) * 100).toFixed(2) }}%
                </td>

                <td class="px-6 py-4 text-right font-mono text-xs text-[var(--color-text-muted)]">
                  {{ entry.runtime_sec ? parseFloat(entry.runtime_sec).toFixed(1) + 's' : 'n/a' }}
                </td>

                <td class="px-6 py-4 text-right">
                  <button 
                    @click="toggleRow(entry.date + entry.ticker)"
                    class="text-[var(--color-accent-primary)] hover:underline text-xs font-bold"
                  >
                    {{ expandedRows.has(entry.date + entry.ticker) ? 'Hide' : 'Why?' }}
                  </button>
                </td>

              </tr>
              <!-- Expanded Detail Row -->
              <tr v-if="expandedRows.has(entry.date + entry.ticker)" class="bg-black/40">
                <td colspan="7" class="px-8 py-6">
                  <div class="grid grid-cols-1 md:grid-cols-2 gap-8">
                    <div class="space-y-2">
                      <h4 class="text-[10px] uppercase font-black text-[var(--color-text-muted)] tracking-widest">Portfolio Action Detail</h4>
                      <p class="text-sm leading-relaxed text-[var(--color-text-secondary)]">{{ entry.decision }}</p>
                    </div>
                    <div class="space-y-2">
                      <h4 class="text-[10px] uppercase font-black text-[var(--color-text-muted)] tracking-widest">Performance Reflection</h4>
                      <p class="text-sm leading-relaxed text-[var(--color-text-secondary)] italic">{{ entry.reflection }}</p>
                    </div>
                  </div>
                </td>
              </tr>
            </template>

          </tbody>
        </table>
      </div>
      <div v-if="filteredEntries.length === 0 && !loading" class="p-12 text-center text-[var(--color-text-muted)]">
        <Trophy :size="48" class="mx-auto mb-4 opacity-20" />
        <p>No settled paper trades found for the current filter.</p>
      </div>
    </div>
  </div>
</template>

<style scoped>
.glass {
  background: rgba(15, 23, 42, 0.6);
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
}
/* Style the select elements for better appearance in dark mode */
select option {
  background-color: #0f172a;
  color: #f8fafc;
}
</style>
