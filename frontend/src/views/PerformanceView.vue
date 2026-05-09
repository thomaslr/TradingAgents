<script setup lang="ts">
import { ref, onMounted, computed, watch } from 'vue'
import { fetchMemoryEntries, clearMemoryEntries, type MemoryEntry } from '../api/client'
import { createChart, ColorType, LineSeries } from 'lightweight-charts'
import { Trophy, RefreshCw, Info, Filter, BarChart3, Trash2 } from 'lucide-vue-next'

const loading = ref(true)
const entries = ref<MemoryEntry[]>([])
const chartContainer = ref<HTMLDivElement>()

// Filters
const showCosts = ref(false)
const commissionPerTrade = ref(0.001) // 0.1% default simulation cost
const selectedTicker = ref('ALL')
const benchmarkType = ref<'SPY' | 'ASSET'>('ASSET') // Default to Buy & Hold comparison
const strategySource = ref<'RATING' | 'ACTION'>('RATING') // Expert Signal vs Final Action
const costModel = ref<'FLAT' | 'IBKR'>('FLAT')
const timeRange = ref<'1M' | '3M' | '6M' | 'YTD' | 'ALL'>('6M')



let chart: any = null
let strategySeries: any = null
let benchmarkSeries: any = null

onMounted(async () => {
  await loadData()
  initChart()
})

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
  const tickers = new Set(entries.value.map(e => e.ticker))
  return ['ALL', ...Array.from(tickers).sort()]
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
  if (timeRange.value !== 'ALL') {
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


const stats = computed(() => {
  if (filteredEntries.value.length === 0) return { totalRaw: 0, totalAlpha: 0, winRate: 0, count: 0 }
  
  const wins = filteredEntries.value.filter(e => parsePct(e.raw) > 0).length
  
  // Calculate dynamic alpha based on the last points of our lines
  const stratFinal = performanceData.value.stratPoints.length > 0 
    ? performanceData.value.stratPoints[performanceData.value.stratPoints.length - 1].value 
    : 100
  const benchFinal = performanceData.value.benchPoints.length > 0 
    ? performanceData.value.benchPoints[performanceData.value.benchPoints.length - 1].value 
    : 100
    
  return {
    totalRaw: 0,
    totalAlpha: stratFinal - benchFinal,
    winRate: (wins / filteredEntries.value.length) * 100,
    count: filteredEntries.value.length
  }
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



const expandedRows = ref<Set<string>>(new Set())

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
        <div class="flex flex-col gap-1">
          <span class="text-[10px] uppercase font-black text-[var(--color-text-muted)] ml-1">Range</span>
          <div class="flex items-center p-1 bg-[var(--color-bg-elevated)] border border-[var(--color-border-default)] rounded-lg">
            <button 
              v-for="range in (['1M', '3M', '6M', 'YTD', 'ALL'] as const)" 
              :key="range"
              @click="timeRange = range"
              class="px-2 py-1 text-[10px] font-bold rounded transition-colors"
              :class="timeRange === range ? 'bg-[var(--color-accent-primary)] text-white' : 'text-[var(--color-text-muted)] hover:text-white'"
            >
              {{ range }}
            </button>
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
          {{ performanceData.stratPoints.length > 0 ? ((performanceData.stratPoints[performanceData.stratPoints.length-1].value - 100)).toFixed(1) : '0' }}%
        </p>
      </div>
      <div class="glass p-4 rounded-xl space-y-1">
        <p class="text-xs text-[var(--color-text-muted)] font-medium uppercase tracking-wider">Benchmark ROI</p>
        <p class="text-2xl font-bold text-[#6366f1]">
          {{ performanceData.benchPoints.length > 0 ? ((performanceData.benchPoints[performanceData.benchPoints.length-1].value - 100)).toFixed(1) : '0' }}%
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
              <th class="px-6 py-4 font-semibold">Rating (AI)</th>
              <th class="px-6 py-4 font-semibold">Action (PM)</th>
              <th class="px-6 py-4 font-semibold">Return</th>
              <th class="px-6 py-4 font-semibold text-right">Alpha</th>
              <th class="px-6 py-4 font-semibold text-right">Details</th>
            </tr>
          </thead>
          <tbody class="divide-y divide-white/[0.03]">

            <template v-for="entry in [...filteredEntries].reverse()" :key="entry.date + entry.ticker">
              <tr class="hover:bg-white/[0.02] transition-colors group border-b border-white/[0.03]">
                <td class="px-6 py-4 text-sm font-mono text-[var(--color-text-muted)]">{{ entry.date }}</td>
                <td class="px-6 py-4 font-bold">{{ entry.ticker }}</td>
                <td class="px-6 py-4">
                  <span class="px-2 py-0.5 rounded text-[10px] font-black bg-white/5 border" :class="getRatingClass(entry.rating)">
                    {{ getSignalLabel(entry.rating) }}
                  </span>
                </td>
                <td class="px-6 py-4">
                  <span class="px-2 py-0.5 rounded text-[10px] font-black bg-white/5 border" :class="getRatingClass(entry.decision)">
                    {{ getSignalLabel(entry.decision) }}
                  </span>
                </td>
                <td class="px-6 py-4 font-mono font-bold text-sm" :class="parsePct(entry.raw) >= 0 ? 'text-green-400' : 'text-red-400'">
                  {{ entry.raw }}
                </td>
                <td class="px-6 py-4 font-mono text-xs" :class="parsePct(entry.alpha) >= 0 ? 'text-green-400' : 'text-red-400'">
                  {{ entry.alpha }}
                </td>
                <td class="px-6 py-4 text-right">
                  <button 
                    @click="toggleRow(entry.date + entry.ticker)"
                    class="text-[var(--color-accent-primary)] hover:underline text-xs font-bold"
                  >
                    {{ expandedRows.has(entry.date + entry.ticker) ? 'Hide Details' : 'View Reasoning' }}
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
