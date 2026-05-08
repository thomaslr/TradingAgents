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
const benchmarkType = ref<'SPY' | 'ASSET'>('SPY')

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
  return parseFloat(val.replace('%', '')) / 100
}

const filteredEntries = computed(() => {
  if (selectedTicker.value === 'ALL') return entries.value
  return entries.value.filter(e => e.ticker === selectedTicker.value)
})

const stats = computed(() => {
  if (filteredEntries.value.length === 0) return { totalRaw: 0, totalAlpha: 0, winRate: 0, count: 0 }
  
  let wins = 0
  let totalRaw = 0
  let totalAlpha = 0
  
  filteredEntries.value.forEach(e => {
    const r = parsePct(e.raw)
    const a = parsePct(e.alpha)
    totalRaw += r
    totalAlpha += a
    if (r > 0) wins++
  })
  
  return {
    totalRaw: totalRaw * 100,
    totalAlpha: totalAlpha * 100,
    winRate: (wins / filteredEntries.value.length) * 100,
    count: filteredEntries.value.length
  }
})

const performanceData = computed(() => {
  let strat = 100 
  let bench = 100
  
  const stratPoints = []
  const benchPoints = []
  
  // Track state per ticker to handle 'Hold' signals correctly
  const tickerStates = new Map<string, boolean>()
  
  if (filteredEntries.value.length > 0) {
    // Starting point
    stratPoints.push({ time: filteredEntries.value[0].date, value: strat })
    benchPoints.push({ time: filteredEntries.value[0].date, value: bench })
  }

  filteredEntries.value.forEach(e => {
    const raw = parsePct(e.raw)
    const alpha = parsePct(e.alpha)
    const spy = raw - alpha
    
    // 1. Determine State (Stateful Logic)
    const rating = e.rating.toLowerCase()
    if (rating.includes('buy') || rating.includes('overweight')) {
      tickerStates.set(e.ticker, true)
    } else if (rating.includes('sell') || rating.includes('underweight')) {
      tickerStates.set(e.ticker, false)
    }
    // If rating is 'hold', the tickerStates[e.ticker] remains unchanged.
    
    const isLong = tickerStates.get(e.ticker) || false
    let stratRet = isLong ? raw : 0
    
    if (showCosts.value && isLong) {
      stratRet -= commissionPerTrade.value
    }
    
    // 2. Calculate Benchmark Return
    const benchRet = benchmarkType.value === 'SPY' ? spy : raw
    
    strat = strat * (1 + stratRet)
    bench = bench * (1 + benchRet)
    
    stratPoints.push({ time: e.date, value: strat })
    benchPoints.push({ time: e.date, value: bench })
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
    },
    timeScale: {
      borderColor: '#1e293b',
    },
    handleScroll: true,
    handleScale: true,
  })

  strategySeries = chart.addSeries(LineSeries, {
    color: '#10b981',
    lineWidth: 2,
    title: 'Strategy',
  })

  benchmarkSeries = chart.addSeries(LineSeries, {
    color: '#6366f1',
    lineWidth: 2,
    lineStyle: 2, 
    title: 'Benchmark',
  })

  updateChart()
}

function updateChart() {
  if (!strategySeries || !benchmarkSeries) return
  strategySeries.setData(performanceData.value.stratPoints)
  benchmarkSeries.setData(performanceData.value.benchPoints)
  chart.timeScale().fitContent()
}

watch([showCosts, performanceData, benchmarkType], () => {
  updateChart()
})

function getRatingClass(rating: string) {
  const r = rating.toLowerCase()
  if (r.includes('buy') || r.includes('overweight')) return 'text-green-400'
  if (r.includes('sell') || r.includes('underweight')) return 'text-red-400'
  return 'text-amber-400'
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

        <!-- Benchmark Toggle -->
        <div class="flex items-center gap-2 px-3 py-1.5 bg-[var(--color-bg-elevated)] border border-[var(--color-border-default)] rounded-lg">
          <BarChart3 :size="14" class="text-[var(--color-text-muted)]" />
          <select v-model="benchmarkType" class="bg-transparent border-none text-xs font-bold focus:ring-0 cursor-pointer">
            <option value="SPY">Market (SPY)</option>
            <option value="ASSET">Underlying Assets</option>
          </select>
        </div>

        <!-- Cost Simulation -->
        <div class="flex items-center gap-2 px-3 py-2 bg-[var(--color-bg-elevated)] border border-[var(--color-border-default)] rounded-lg">
          <span class="text-xs font-medium text-[var(--color-text-secondary)]">Costs</span>
          <button 
            @click="showCosts = !showCosts"
            class="relative inline-flex h-5 w-9 items-center rounded-full transition-colors focus:outline-none"
            :class="showCosts ? 'bg-[var(--color-accent-primary)]' : 'bg-gray-700'"
          >
            <span 
              class="inline-block h-3.5 w-3.5 transform rounded-full bg-white transition-transform"
              :class="showCosts ? 'translate-x-5' : 'translate-x-1'"
            />
          </button>
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
    <div class="grid grid-cols-2 md:grid-cols-4 gap-4">
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
    </div>

    <!-- Chart -->
    <div class="glass p-4 rounded-2xl border border-[var(--color-border-default)]">
      <div class="flex items-center justify-between mb-4 px-2">
        <h3 class="font-bold flex items-center gap-2 text-sm md:text-base">
          Cumulative Return (Indexed to 100)
          <div class="group relative inline-block">
            <Info :size="14" class="text-[var(--color-text-muted)] cursor-help" />
            <div class="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 w-48 p-2 bg-[var(--color-bg-card)] border border-[var(--color-border-default)] rounded text-[10px] opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none z-50">
              Strategy: Long on Buy/Overweight, Cash otherwise.<br>
              Benchmark: {{ benchmarkType === 'SPY' ? 'S&P 500 Index' : 'Selected Assets (Buy & Hold)' }}.
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
              <th class="px-6 py-4 font-semibold">Rating</th>
              <th class="px-6 py-4 font-semibold">Return</th>
              <th class="px-6 py-4 font-semibold">Alpha (vs SPY)</th>
              <th class="px-6 py-4 font-semibold">Reflection</th>
            </tr>
          </thead>
          <tbody class="divide-y divide-[var(--color-border-default)]">
            <tr v-for="entry in [...filteredEntries].reverse()" :key="entry.date + entry.ticker" class="hover:bg-white/[0.02] transition-colors group">
              <td class="px-6 py-4 text-sm font-mono text-[var(--color-text-muted)]">{{ entry.date }}</td>
              <td class="px-6 py-4 font-bold">{{ entry.ticker }}</td>
              <td class="px-6 py-4">
                <span class="px-2 py-0.5 rounded text-xs font-bold bg-white/5 border border-white/10" :class="getRatingClass(entry.rating)">
                  {{ entry.rating.toUpperCase() }}
                </span>
              </td>
              <td class="px-6 py-4 font-mono font-bold" :class="parsePct(entry.raw) >= 0 ? 'text-green-400' : 'text-red-400'">
                {{ entry.raw }}
              </td>
              <td class="px-6 py-4 font-mono text-sm" :class="parsePct(entry.alpha) >= 0 ? 'text-green-400' : 'text-red-400'">
                {{ entry.alpha }}
              </td>
              <td class="px-6 py-4">
                <p class="text-xs text-[var(--color-text-secondary)] line-clamp-2 max-w-md group-hover:line-clamp-none transition-all duration-300 cursor-default">
                  {{ entry.reflection }}
                </p>
              </td>
            </tr>
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
