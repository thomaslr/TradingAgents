<script setup lang="ts">
import { ref, onMounted, computed, watch } from 'vue'
import { fetchMemoryEntries, clearMemoryEntries, fetchTickers, type MemoryEntry } from '../api/client'
import { createChart, ColorType, LineSeries } from 'lightweight-charts'
import { Trophy, RefreshCw, Info, Filter, BarChart3, Trash2 } from 'lucide-vue-next'

const loading = ref(true)
const entries = ref<MemoryEntry[]>([])
const chartContainer = ref<HTMLDivElement>()
const registryTickers = ref<{ticker: string, name: string}[]>([])

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

// Research Mode Filters
const selectedQuickModel = ref(localStorage.getItem('perf_quick_model') || 'ALL')
const selectedDeepModel = ref(localStorage.getItem('perf_deep_model') || 'ALL')
const selectedDepth = ref(localStorage.getItem('perf_depth') || 'ALL')

// Persist Filters
watch(selectedTicker, (v) => localStorage.setItem('perf_ticker', v))
watch(benchmarkType, (v) => localStorage.setItem('perf_benchmark', v))
watch(strategySource, (v) => localStorage.setItem('perf_source', v))
watch(timeRange, (v) => localStorage.setItem('perf_range', v))
watch(dateFrom, (v) => localStorage.setItem('perf_from', v))
watch(dateTo, (v) => localStorage.setItem('perf_to', v))
watch(selectedQuickModel, (v) => localStorage.setItem('perf_quick_model', v))
watch(selectedDeepModel, (v) => localStorage.setItem('perf_deep_model', v))
watch(selectedDepth, (v) => localStorage.setItem('perf_depth', v))

const expandedRows = ref<Set<string>>(new Set())
const expandedReports = ref<Record<string, any>>({})




let chart: any = null
let strategySeries: any = null
let benchmarkSeries: any = null

onMounted(async () => {
  await Promise.all([
    loadData(),
    loadRegistryTickers()
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

async function loadData() {
  loading.value = true
  try {
    const rawEntries = await fetchMemoryEntries()
    // Sort by date initially
    entries.value = rawEntries
      .filter(e => !e.pending && e.raw)
      .sort((a, b) => a.date.localeCompare(b.date))
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
    entries.value = []
  } catch (e) {
    console.error('Failed to clear memory', e)
    alert('Failed to clear memory log.')
  } finally {
    loading.value = false
  }
}


const availableTickers = computed(() => {
  const memoryTickers = entries.value.map(e => e.ticker)
  const regTickers = registryTickers.value.map(t => t.ticker)
  const all = new Set([...memoryTickers, ...regTickers])
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

  // Research Mode Filters
  if (selectedQuickModel.value !== 'ALL') {
    result = result.filter(e => e.quick_model === selectedQuickModel.value)
  }
  if (selectedDeepModel.value !== 'ALL') {
    result = result.filter(e => e.deep_model === selectedDeepModel.value)
  }
  if (selectedDepth.value !== 'ALL') {
    result = result.filter(e => String(e.depth) === selectedDepth.value)
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

const stats = computed(() => {
  if (visibleEntries.value.length === 0) return { totalRaw: 0, totalAlpha: 0, winRate: 0, count: 0, totalRuntime: 0, stratROI: 0, benchROI: 0 }
  
  const wins = visibleEntries.value.filter(e => {
    // We need to determine if it was a win based on the strategy logic for THAT entry
    const signal = strategySource.value === 'RATING' ? e.rating : e.decision
    const isLong = (signal || '').toLowerCase().includes('buy') || (signal || '').toLowerCase().includes('overweight')
    const stratRet = isLong ? parsePct(e.raw) : 0
    
    const raw = parsePct(e.raw)
    const alpha = parsePct(e.alpha)
    const benchRet = benchmarkType.value === 'SPY' ? (raw - alpha) : raw
    
    return stratRet > benchRet
  }).length
  
  // Calculate dynamic ROI/Alpha based on the visible points
  // We need to recalculate ROI starting from the first visible date
  let strat = 100
  let bench = 100
  
  const dateGroups = new Map<string, MemoryEntry[]>()
  visibleEntries.value.forEach(e => {
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
    })

    const avgStratRet = totalStratRet / dayEntries.length
    const avgBenchRet = totalBenchRet / dayEntries.length
    strat = strat * (1 + avgStratRet)
    bench = bench * (1 + avgBenchRet)
  })

  const totalRuntime = visibleEntries.value.reduce((acc, e) => {
    const r = parseFloat(e.runtime_sec || '0')
    return acc + (isNaN(r) ? 0 : r)
  }, 0)

  return {
    totalRaw: strat - 100,
    totalAlpha: (strat - 100) - (bench - 100),
    winRate: (wins / visibleEntries.value.length) * 100,
    count: visibleEntries.value.length,
    totalRuntime,
    stratROI: strat - 100,
    benchROI: bench - 100
  }
})



const availableQuickModels = computed(() => {
  const models = new Set(entries.value.map(e => e.quick_model).filter(Boolean))
  return ['ALL', ...Array.from(models).sort()]
})

const availableDeepModels = computed(() => {
  const models = new Set(entries.value.map(e => e.deep_model).filter(Boolean))
  return ['ALL', ...Array.from(models).sort()]
})

const availableDepths = computed(() => {
  const depths = new Set(entries.value.map(e => String(e.depth)).filter(Boolean))
  return ['ALL', ...Array.from(depths).sort()]
})



const performanceData = computed(() => {
  let strat = 100 
  let bench = 100
  
  const stratPoints: any[] = []
  const benchPoints: any[] = []
  
  if (filteredEntries.value.length === 0) return { stratPoints, benchPoints }

  // Group entries by date
  const dateGroups = new Map<string, MemoryEntry[]>()
  filteredEntries.value.forEach(e => {
    if (!dateGroups.has(e.date)) dateGroups.set(e.date, [])
    dateGroups.get(e.date)!.push(e)
  })

  // Sort dates strictly
  const sortedDates = Array.from(dateGroups.keys()).sort()
  
  // Track state per ticker to handle 'Hold' signals correctly
  const tickerStates = new Map<string, boolean>()
  
  // Build points day by day
  sortedDates.forEach(date => {
    const dayEntries = dateGroups.get(date)!
    
    let totalStratRet = 0
    let totalBenchRet = 0
    
    dayEntries.forEach(e => {
      const raw = parsePct(e.raw)
      const alpha = parsePct(e.alpha)
      const spy = raw - alpha
      
      // Determine Signal Source
      const signal = strategySource.value === 'RATING' ? e.rating : e.decision
      const rating = signal.toLowerCase()
      
      if (rating.includes('buy') || rating.includes('overweight')) {
        tickerStates.set(e.ticker, true)
      } else if (rating.includes('sell') || rating.includes('underweight')) {
        tickerStates.set(e.ticker, false)
      }
      
      const isLong = tickerStates.get(e.ticker) || false
      let tickerStratRet = isLong ? raw : 0
      
      if (showCosts.value && isLong) {
        tickerStratRet -= (costModel.value === 'IBKR' ? 0.0015 : commissionPerTrade.value)
      }
      
      const tickerBenchRet = benchmarkType.value === 'SPY' ? spy : raw
      
      totalStratRet += tickerStratRet
      totalBenchRet += tickerBenchRet
    })

    // Average returns for the day if multiple tickers
    const avgStratRet = totalStratRet / dayEntries.length
    const avgBenchRet = totalBenchRet / dayEntries.length
    
    strat = strat * (1 + avgStratRet)
    bench = bench * (1 + avgBenchRet)
    
    // Only push if we have valid numbers
    if (!isNaN(strat) && !isNaN(bench)) {
      stratPoints.push({ time: date, value: strat })
      benchPoints.push({ time: date, value: bench })
    }
  })
  
  return { stratPoints, benchPoints }
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

  strategySeries = chart.addSeries(LineSeries, {
    color: '#10b981',
    lineWidth: 3,
    title: 'Strategy',
  })

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
  if (!strategySeries || !benchmarkSeries || !chart) return
  
  const stratData = performanceData.value.stratPoints
  const benchData = performanceData.value.benchPoints
  
  if (stratData.length > 0) {
    strategySeries.setData(stratData)
    benchmarkSeries.setData(benchData)
    chart.timeScale().fitContent()
  }
}


watch([showCosts, performanceData, benchmarkType, strategySource, costModel, timeRange], () => {
  updateChart()
})



function toggleRow(id: string) {
  if (expandedRows.value.has(id)) expandedRows.value.delete(id)
  else expandedRows.value.add(id)
}

function getRatingClass(rating: string) {
  const r = rating.toLowerCase()
  if (r.includes('buy') || r.includes('overweight')) return 'text-green-400 border-green-400/20'
  if (r.includes('sell') || r.includes('underweight')) return 'text-red-400 border-red-400/20'
  return 'text-amber-400 border-amber-400/20'
}

function getSignalLabel(text: string) {
  const t = text.toLowerCase()
  if (t.includes('buy')) return 'BUY'
  if (t.includes('sell')) return 'SELL'
  if (t.includes('overweight')) return 'OVERWEIGHT'
  if (t.includes('underweight')) return 'UNDERWEIGHT'
  return 'HOLD'
}

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
      
      <div class="flex flex-wrap items-center gap-3">
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
              v-for="range in (['1M', '3M', '6M', 'YTD', 'ALL'] as const)" 
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

        <!-- Benchmark Toggle -->
        <div class="flex flex-col gap-1">
          <span class="text-[10px] uppercase font-black text-[var(--color-text-muted)] ml-1">Benchmark</span>
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
          <span class="text-[10px] uppercase font-black text-[var(--color-text-muted)] ml-1">AI Signal Source</span>
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
          <span class="text-[10px] uppercase font-black text-[var(--color-text-muted)] ml-1">Trade Costs</span>
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

      <!-- Research Mode Filter Bar -->
      <div class="flex flex-wrap gap-4 items-center bg-white/5 p-4 rounded-xl border border-white/10 mt-4">
        <div class="flex flex-col gap-1">
          <span class="text-[10px] uppercase font-black text-[var(--color-text-muted)] ml-1">Quick LLM</span>
          <select v-model="selectedQuickModel" class="bg-[var(--color-bg-elevated)] border border-[var(--color-border-default)] rounded px-2 py-1 text-xs focus:outline-none focus:border-[var(--color-accent-primary)] min-w-[120px]">
            <option v-for="m in availableQuickModels" :key="m" :value="m">{{ m }}</option>
          </select>
        </div>
        <div class="flex flex-col gap-1">
          <span class="text-[10px] uppercase font-black text-[var(--color-text-muted)] ml-1">Deep LLM</span>
          <select v-model="selectedDeepModel" class="bg-[var(--color-bg-elevated)] border border-[var(--color-border-default)] rounded px-2 py-1 text-xs focus:outline-none focus:border-[var(--color-accent-primary)] min-w-[120px]">
            <option v-for="m in availableDeepModels" :key="m" :value="m">{{ m }}</option>
          </select>
        </div>
        <div class="flex flex-col gap-1">
          <span class="text-[10px] uppercase font-black text-[var(--color-text-muted)] ml-1">Debate Depth</span>
          <select v-model="selectedDepth" class="bg-[var(--color-bg-elevated)] border border-[var(--color-border-default)] rounded px-2 py-1 text-xs focus:outline-none focus:border-[var(--color-accent-primary)] min-w-[100px]">
            <option v-for="d in availableDepths" :key="d" :value="d">{{ d === 'ALL' ? 'ALL' : d + ' Rounds' }}</option>
          </select>
        </div>
        
        <div class="flex-1"></div>
        
        <!-- Efficiency Card -->
        <div v-if="stats.count > 0" class="flex flex-col items-end px-4 border-l border-white/10">
          <span class="text-[10px] uppercase font-black text-[var(--color-text-muted)]">Efficiency Score</span>
          <span class="text-lg font-bold text-yellow-400">{{ (stats.totalAlpha / (stats.totalRuntime / 60 || 1)).toFixed(2) }} <small class="text-[8px] opacity-50">Alpha/Min</small></span>
        </div>
      </div>
    </div>



    <!-- Stats Grid -->
    <div class="grid grid-cols-2 md:grid-cols-5 gap-4">
      <div class="glass p-4 rounded-xl space-y-1">
        <p class="text-xs text-[var(--color-text-muted)] font-medium uppercase tracking-wider">Trades Filtered</p>
        <p class="text-2xl font-bold">{{ stats.count }}</p>
      </div>
      <div class="glass p-4 rounded-xl space-y-1">
        <p class="text-xs text-[var(--color-text-muted)] font-medium uppercase tracking-wider">Win Rate</p>
        <p class="text-2xl font-bold text-blue-400">{{ stats.winRate.toFixed(1) }}%</p>
      </div>
      <div class="glass p-4 rounded-xl space-y-1">
        <p class="text-xs text-[var(--color-text-muted)] font-medium uppercase tracking-wider">Total Alpha</p>
        <p class="text-2xl font-bold" :class="stats.totalAlpha >= 0 ? 'text-green-400' : 'text-red-400'">
          {{ stats.totalAlpha >= 0 ? '+' : '' }}{{ stats.totalAlpha.toFixed(1) }}%
        </p>
      </div>
      <div class="glass p-4 rounded-xl space-y-1">
        <p class="text-xs text-[var(--color-text-muted)] font-medium uppercase tracking-wider">Strategy ROI</p>
        <p class="text-2xl font-bold text-[var(--color-accent-primary)]">
          {{ stats.stratROI.toFixed(1) }}%
        </p>
      </div>
      <div class="glass p-4 rounded-xl space-y-1">
        <p class="text-xs text-[var(--color-text-muted)] font-medium uppercase tracking-wider">Benchmark ROI</p>
        <p class="text-2xl font-bold text-[#6366f1]">
          {{ stats.benchROI.toFixed(1) }}%
        </p>
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
        <div class="flex items-center gap-4 text-xs font-medium">
          <div class="flex items-center gap-1.5">
            <div class="w-2.5 h-2.5 rounded-full bg-[#10b981]"></div>
            <span class="text-[var(--color-text-secondary)]">Strategy</span>
          </div>
          <div class="flex items-center gap-1.5">
            <div class="w-2.5 h-2.5 rounded-full bg-[#6366f1]"></div>
            <span class="text-[var(--color-text-secondary)]">{{ benchmarkType === 'SPY' ? 'S&P 500' : 'Buy & Hold' }}</span>
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
                <td class="px-6 py-4 text-right font-mono font-bold text-sm" :class="(() => {
                  const signal = strategySource === 'RATING' ? entry.rating : entry.decision
                  const isLong = (signal || '').toLowerCase().includes('buy') || (signal || '').toLowerCase().includes('overweight')
                  const stratRet = isLong ? parsePct(entry.raw) : 0
                  return stratRet >= 0 ? 'text-green-400' : 'text-red-400'
                })()">
                  {{ (() => {
                    const signal = strategySource === 'RATING' ? entry.rating : entry.decision
                    const isLong = (signal || '').toLowerCase().includes('buy') || (signal || '').toLowerCase().includes('overweight')
                    const stratRet = isLong ? parsePct(entry.raw) : 0
                    return (stratRet * 100).toFixed(2) + '%'
                  })() }}
                </td>

                <!-- Benchmark Return -->
                <td class="px-6 py-4 text-right font-mono text-xs text-[var(--color-text-muted)]">
                  {{ (() => {
                    const raw = parsePct(entry.raw)
                    const alpha = parsePct(entry.alpha)
                    const benchRet = benchmarkType === 'SPY' ? (raw - alpha) : raw
                    return (benchRet * 100).toFixed(2) + '%'
                  })() }}
                </td>

                <!-- Realized Alpha -->
                <td class="px-6 py-4 text-right font-mono font-bold text-sm" :class="(() => {
                  const signal = strategySource === 'RATING' ? entry.rating : entry.decision
                  const isLong = (signal || '').toLowerCase().includes('buy') || (signal || '').toLowerCase().includes('overweight')
                  const stratRet = isLong ? parsePct(entry.raw) : 0
                  const raw = parsePct(entry.raw)
                  const alpha = parsePct(entry.alpha)
                  const benchRet = benchmarkType === 'SPY' ? (raw - alpha) : raw
                  const realizedAlpha = stratRet - benchRet
                  return realizedAlpha >= 0 ? 'text-green-400' : 'text-red-400'
                })()">
                  {{ (() => {
                    const signal = strategySource === 'RATING' ? entry.rating : entry.decision
                    const isLong = (signal || '').toLowerCase().includes('buy') || (signal || '').toLowerCase().includes('overweight')
                    const stratRet = isLong ? parsePct(entry.raw) : 0
                    const raw = parsePct(entry.raw)
                    const alpha = parsePct(entry.alpha)
                    const benchRet = benchmarkType === 'SPY' ? (raw - alpha) : raw
                    const realizedAlpha = stratRet - benchRet
                    return (realizedAlpha >= 0 ? '+' : '') + (realizedAlpha * 100).toFixed(2) + '%'
                  })() }}
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
