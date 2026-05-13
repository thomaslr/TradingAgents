<script setup lang="ts">
import { ref, onMounted, computed, watch } from 'vue'
import { fetchPerformanceData, fetchConfigs, clearMemoryEntries, fetchTickers, type PerformanceEntry, type SimulationConfig, type MemoryEntry } from '../api/client'
import { createChart, ColorType, LineSeries } from 'lightweight-charts'
import { Trophy, RefreshCw, Info, Filter, BarChart3, Trash2 } from 'lucide-vue-next'

const loading = ref(true)
const rawDbEntries = ref<PerformanceEntry[]>([])
const configs = ref<SimulationConfig[]>([])
const enabledConfigs = ref<Set<string>>(new Set())
const chartContainer = ref<HTMLDivElement>()
let chart: any = null
let benchmarkSeries: any = null
let strategySeriesMap = new Map<string, any>()
const registryTickers = ref<{ticker: string, name: string}[]>([])

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
const selectedTicker = ref(localStorage.getItem('perf_ticker') || 'ALL')
const benchmarkType = ref<'SPY' | 'ASSET'>((localStorage.getItem('perf_benchmark') as any) || 'ASSET')
const strategySource = ref<'RATING' | 'ACTION'>((localStorage.getItem('perf_source') as any) || 'RATING')
const costModel = ref<'FLAT' | 'IBKR'>('FLAT')
const timeRange = ref<'1M' | '3M' | '6M' | 'YTD' | 'ALL' | 'CUSTOM'>((localStorage.getItem('perf_range') as any) || '6M')
const dateFrom = ref(localStorage.getItem('perf_from') || '')
const dateTo = ref(localStorage.getItem('perf_to') || '')

// Visible Chart Range (for dynamic stats)
const visibleTimeRange = ref<{ from: string; to: string } | null>(null)


// Persist Filters
watch(selectedTicker, (v) => localStorage.setItem('perf_ticker', v))
watch(benchmarkType, (v) => localStorage.setItem('perf_benchmark', v))
watch(strategySource, (v) => localStorage.setItem('perf_source', v))
watch(timeRange, (v) => localStorage.setItem('perf_range', v))
watch(dateFrom, (v) => localStorage.setItem('perf_from', v))
watch(dateTo, (v) => localStorage.setItem('perf_to', v))


const expandedRows = ref<Set<string>>(new Set())




onMounted(async () => {
  await Promise.all([
    loadData(),
    loadRegistryTickers(),
    loadConfigs()
  ])
  initChart()
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
    // Enable all configs by default
    enabledConfigs.value = new Set(configs.value.map(c => c.config_id))
  } catch (e) {
    console.error('Failed to load configs', e)
  }
}

function toggleConfig(configId: string) {
  const s = new Set(enabledConfigs.value)
  if (s.has(configId)) s.delete(configId)
  else s.add(configId)
  enabledConfigs.value = s
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

const multiConfigStats = computed(() => {
  if (visibleEntries.value.length === 0 || configs.value.length === 0) return []
  
  // Use either selected configs or all configs if none selected
  const targetConfigs = enabledConfigs.value.size > 0 
    ? configs.value.filter(c => enabledConfigs.value.has(c.config_id))
    : configs.value

  return targetConfigs
    .filter(config => visibleEntries.value.some(e => e.config_id === config.config_id))
    .map(config => {
      const cid = config.config_id
      const configEntries = visibleEntries.value.filter(e => e.config_id === cid)
      
      const wins = configEntries.filter(e => {
        const signal = strategySource.value === 'RATING' ? e.rating : e.decision
        const isLong = (signal || '').toLowerCase().includes('buy') || (signal || '').toLowerCase().includes('overweight')
        const stratRet = isLong ? parsePct(e.raw) : 0
        const raw = parsePct(e.raw)
        const alpha = parsePct(e.alpha)
        const benchRet = benchmarkType.value === 'SPY' ? (raw - alpha) : raw
        return stratRet > benchRet
      }).length

      let strat = 100
      let bench = 100
      let totalRuntime = 0

      const dateGroups = new Map<string, MemoryEntry[]>()
      configEntries.forEach(e => {
        if (!dateGroups.has(e.date)) dateGroups.set(e.date, [])
        dateGroups.get(e.date)!.push(e)
      })

      const sortedDates = Array.from(dateGroups.keys()).sort()
      const tickerStates = new Map<string, boolean>()

      sortedDates.forEach(date => {
        const dayEntries = dateGroups.get(date)!
        let totalStratRet = 0
        let totalBenchRet = 0
        
        dayEntries.forEach(e => {
          const raw = parsePct(e.raw)
          const alpha = parsePct(e.alpha)
          const spy = raw - alpha
          const signal = strategySource.value === 'RATING' ? e.rating : e.decision
          const rating = signal.toLowerCase()
          
          if (rating.includes('buy') || rating.includes('overweight')) tickerStates.set(e.ticker, true)
          else if (rating.includes('sell') || rating.includes('underweight')) tickerStates.set(e.ticker, false)
          
          const isLong = tickerStates.get(e.ticker) || false
          let tickerStratRet = isLong ? raw : 0
          if (showCosts.value && isLong) {
            tickerStratRet -= (costModel.value === 'IBKR' ? 0.0015 : commissionPerTrade.value)
          }
          
          const tickerBenchRet = benchmarkType.value === 'SPY' ? spy : raw
          totalStratRet += tickerStratRet
          totalBenchRet += tickerBenchRet
          totalRuntime += parseFloat(e.runtime_sec || '0')
        })

        const avgStratRet = totalStratRet / dayEntries.length
        const avgBenchRet = totalBenchRet / dayEntries.length
        strat = strat * (1 + avgStratRet)
        bench = bench * (1 + avgBenchRet)
      })

      return {
        config,
        count: configEntries.length,
        winRate: (wins / configEntries.length) * 100,
        totalAlpha: ((strat - bench) / 100) * 100,
        stratROI: strat - 100,
        benchROI: bench - 100,
        totalRuntime
      }
    })
})


const activeConfigs = computed(() => {
  return configs.value.filter(c => enabledConfigs.value.size === 0 || enabledConfigs.value.has(c.config_id))
})


const performanceData = computed(() => {
  // Returns a map of config_id -> points, plus the shared benchmark
  const targetConfigs = enabledConfigs.value.size > 0 
    ? configs.value.filter(c => enabledConfigs.value.has(c.config_id))
    : configs.value

  const results: Record<string, any[]> = {}
  let benchPoints: any[] = []

  targetConfigs.forEach(config => {
    const cid = config.config_id
    const configEntries = filteredEntries.value.filter(e => e.config_id === cid)
    if (configEntries.length === 0) return

    let strat = 100
    let bench = 100
    const stratPoints: any[] = []
    const currentBenchPoints: any[] = []

    const dateGroups = new Map<string, MemoryEntry[]>()
    configEntries.forEach(e => {
      if (!dateGroups.has(e.date)) dateGroups.set(e.date, [])
      dateGroups.get(e.date)!.push(e)
    })

    const sortedDates = Array.from(dateGroups.keys()).sort()
    const tickerStates = new Map<string, boolean>()

    sortedDates.forEach(date => {
      const dayEntries = dateGroups.get(date)!
      let totalStratRet = 0
      let totalBenchRet = 0
      
      dayEntries.forEach(e => {
        const raw = parsePct(e.raw)
        const alpha = parsePct(e.alpha)
        const spy = raw - alpha
        const signal = strategySource.value === 'RATING' ? e.rating : e.decision
        const rating = signal.toLowerCase()
        
        if (rating.includes('buy') || rating.includes('overweight')) tickerStates.set(e.ticker, true)
        else if (rating.includes('sell') || rating.includes('underweight')) tickerStates.set(e.ticker, false)
        
        const isLong = tickerStates.get(e.ticker) || false
        let tickerStratRet = isLong ? raw : 0
        if (showCosts.value && isLong) tickerStratRet -= (costModel.value === 'IBKR' ? 0.0015 : commissionPerTrade.value)
        
        const tickerBenchRet = benchmarkType.value === 'SPY' ? spy : raw
        totalStratRet += tickerStratRet
        totalBenchRet += tickerBenchRet
      })

      strat = strat * (1 + (totalStratRet / dayEntries.length))
      bench = bench * (1 + (totalBenchRet / dayEntries.length))
      stratPoints.push({ time: date, value: strat })
      currentBenchPoints.push({ time: date, value: bench })
    })
    
    results[cid] = stratPoints
    if (benchPoints.length === 0) benchPoints = currentBenchPoints
  })

  return { stratMaps: results, benchPoints }
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
    color: '#6366f1',
    lineWidth: 2,
    lineStyle: 2, 
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

  const { stratMaps, benchPoints } = performanceData.value
  
  // Set Benchmark
  if (benchPoints.length > 0) {
    benchmarkSeries.setData(benchPoints)
  }

  // Add a series for each config
  Object.entries(stratMaps).forEach(([cid, data]) => {
    const config = configs.value.find(c => c.config_id === cid)
    if (!config) return

    const series = chart.addSeries(LineSeries, {
      color: config.color,
      lineWidth: 3,
      title: config.label,
    })
    series.setData(data)
    strategySeriesMap.set(cid, series)
  })

  if (benchPoints.length > 0) {
    chart.timeScale().fitContent()
  }
}


watch([showCosts, performanceData, benchmarkType, strategySource, costModel, timeRange, enabledConfigs], () => {
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

      <!-- Simulation Config Toggle Bar -->
      <div v-if="configs.length > 0" class="flex flex-wrap gap-4 items-center bg-white/5 p-4 rounded-xl border border-white/10 mt-4">
        <div class="flex flex-col gap-1">
          <span class="text-[10px] uppercase font-black text-[var(--color-text-muted)] ml-1">Simulation Configs</span>
          <div class="flex flex-wrap gap-2">
            <button
              v-for="c in configs"
              :key="c.config_id"
              @click="toggleConfig(c.config_id)"
              class="flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs font-bold border transition-all"
              :class="enabledConfigs.has(c.config_id)
                ? 'border-white/20 bg-white/10 text-white'
                : 'border-white/5 bg-white/[0.02] text-[var(--color-text-muted)] opacity-40'"
            >
              <span class="w-2.5 h-2.5 rounded-full" :style="{ backgroundColor: c.color }"></span>
              {{ c.label }}
            </button>
          </div>
        </div>
      </div>
    <div class="space-y-4">
      <div v-for="s in multiConfigStats" :key="s.config.config_id" 
           class="glass p-4 rounded-2xl border border-[var(--color-border-default)] transition-all hover:border-white/20"
           :style="{ borderLeft: `4px solid ${s.config.color}` }">
        <div class="flex flex-wrap items-center justify-between gap-4">
          <!-- Config Header -->
          <div class="flex flex-col min-w-[200px]">
            <span class="text-[10px] uppercase font-black text-[var(--color-text-muted)] tracking-widest">Simulation Config</span>
            <span class="text-sm font-bold text-white">{{ s.config.label }}</span>
            <div class="flex items-center gap-2 mt-1">
               <span class="text-[10px] text-yellow-400 font-bold">{{ (s.totalAlpha / (s.totalRuntime / 60 || 1)).toFixed(2) }} <small class="opacity-50">Alpha/Min</small></span>
               <span class="text-[10px] text-[var(--color-text-muted)]">•</span>
               <span class="text-[10px] text-[var(--color-text-muted)]">{{ s.count }} Trades</span>
            </div>
          </div>

          <!-- KPI Mini Cards -->
          <div class="flex flex-1 flex-wrap gap-4 md:gap-8 justify-end">
            <div class="flex flex-col items-end">
              <span class="text-[9px] uppercase font-bold text-[var(--color-text-muted)]">Win Rate</span>
              <span class="text-lg font-bold text-blue-400">{{ s.winRate.toFixed(1) }}%</span>
            </div>
            <div class="flex flex-col items-end">
              <span class="text-[9px] uppercase font-bold text-[var(--color-text-muted)]">Total Alpha</span>
              <span class="text-lg font-bold" :class="s.totalAlpha >= 0 ? 'text-green-400' : 'text-red-400'">
                {{ s.totalAlpha >= 0 ? '+' : '' }}{{ s.totalAlpha.toFixed(1) }}%
              </span>
            </div>
            <div class="flex flex-col items-end">
              <span class="text-[9px] uppercase font-bold text-[var(--color-text-muted)]">Strategy ROI</span>
              <span class="text-lg font-bold text-[var(--color-accent-primary)]">{{ s.stratROI.toFixed(1) }}%</span>
            </div>
            <div class="flex flex-col items-end">
              <span class="text-[9px] uppercase font-bold text-[var(--color-text-muted)]">Benchmark</span>
              <span class="text-lg font-bold text-[#6366f1]">{{ s.benchROI.toFixed(1) }}%</span>
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
        <div class="flex flex-wrap items-center gap-4 text-[10px] font-bold uppercase tracking-wider">
          <!-- Dynamic Strategy Legends -->
          <div v-for="c in activeConfigs" 
               :key="c.config_id" class="flex items-center gap-1.5 bg-white/5 px-2 py-1 rounded-md border border-white/5">
            <div class="w-2 h-2 rounded-full" :style="{ backgroundColor: c.color }"></div>
            <span class="text-[var(--color-text-secondary)]">{{ c.label }}</span>
          </div>
          <!-- Benchmark Legend -->
          <div class="flex items-center gap-1.5 bg-white/5 px-2 py-1 rounded-md border border-white/5">
            <div class="w-2 h-2 rounded-full bg-[#6366f1] border border-dashed border-white/20"></div>
            <span class="text-[var(--color-text-secondary)]">Benchmark ({{ benchmarkType === 'SPY' ? 'S&P 500' : 'Hold' }})</span>
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
                  <div class="flex flex-col">
                    <span class="text-xs font-bold text-white">{{ entry.quick_model }}</span>
                    <span class="text-[10px] text-[var(--color-text-muted)]">Depth: {{ entry.depth }} | Rating: {{ getSignalLabel(entry.rating) }}</span>
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
