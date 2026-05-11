<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount, watch, nextTick } from 'vue'
import { createChart, type IChartApi, type ISeriesApi, ColorType, CandlestickSeries, HistogramSeries, createSeriesMarkers } from 'lightweight-charts'
import { fetchOHLC, fetchRuns, fetchTickers, type Run, type VolumeItem } from '../api/client'
import { ArrowLeft, RefreshCw, Clock } from 'lucide-vue-next'
import { useRouter } from 'vue-router'

const props = defineProps<{ ticker?: string }>()
const router = useRouter()

const chartContainer = ref<HTMLDivElement>()
let chart: IChartApi | null = null
let candleSeries: ISeriesApi<'Candlestick'> | null = null
let volumeSeries: ISeriesApi<'Histogram'> | null = null

const loading = ref(true)
const error = ref('')
const period = ref(localStorage.getItem('chart_period') || '3mo')
const dateFrom = ref(localStorage.getItem('chart_from') || '')
const dateTo = ref(localStorage.getItem('chart_to') || '')
const tickerInput = ref(props.ticker || localStorage.getItem('chart_ticker') || '')
const availableTickers = ref<any[]>([])
const runs = ref<Run[]>([])
const showBuy = ref(localStorage.getItem('chart_show_buy') !== 'false')
const showSell = ref(localStorage.getItem('chart_show_sell') !== 'false')
const showHold = ref(localStorage.getItem('chart_show_hold') === 'true')

watch(period, (v) => localStorage.setItem('chart_period', v))
watch(dateFrom, (v) => localStorage.setItem('chart_from', v))
watch(dateTo, (v) => localStorage.setItem('chart_to', v))
watch(tickerInput, (v) => localStorage.setItem('chart_ticker', v))
watch(showBuy, (v) => localStorage.setItem('chart_show_buy', String(v)))
watch(showSell, (v) => localStorage.setItem('chart_show_sell', String(v)))
watch(showHold, (v) => localStorage.setItem('chart_show_hold', String(v)))


const periods = [
  { label: '1M', value: '1mo' },
  { label: '3M', value: '3mo' },
  { label: '6M', value: '6mo' },
  { label: '1Y', value: '1y' },
  { label: '2Y', value: '2y' },
  { label: '5Y', value: '5y' },
]

onMounted(async () => {
  await loadTickers()
  if (tickerInput.value) {
    await loadChart()
  }
})

async function loadTickers() {
  try {
    availableTickers.value = await fetchTickers()
    
    if (!tickerInput.value && availableTickers.value.length > 0) {
      tickerInput.value = availableTickers.value[0].ticker
      router.replace({ name: 'chart', params: { ticker: tickerInput.value } })
    } else if (tickerInput.value && !availableTickers.value.find(t => t.ticker === tickerInput.value)) {
      // If the current ticker isn't in the list, add a placeholder
      availableTickers.value.push({ ticker: tickerInput.value, name: tickerInput.value })
      availableTickers.value.sort((a, b) => a.ticker.localeCompare(b.ticker))
    }
  } catch (e) {
    console.error("Failed to load tickers", e)
  }
}

onBeforeUnmount(() => {
  if (chart) {
    chart.remove()
    chart = null
  }
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

async function loadChart() {
  if (!chartContainer.value) return
  loading.value = true
  error.value = ''

  try {
    // Use custom dates if both are valid, otherwise use preset period
    const dateRegex = /^\d{4}-\d{1,2}-\d{1,2}$/
    const useDates = dateRegex.test(dateFrom.value) && dateRegex.test(dateTo.value)
    
    console.log(`Loading Chart: ${tickerInput.value} | UseDates: ${useDates} (${dateFrom.value} to ${dateTo.value}) | Period: ${period.value}`)

    const [ohlc, allRuns] = await Promise.all([
      fetchOHLC(
        tickerInput.value, 
        period.value, 
        '1d', 
        useDates ? dateFrom.value : undefined, 
        useDates ? dateTo.value : undefined
      ),
      fetchRuns(tickerInput.value),
    ])

    runs.value = allRuns.filter(r => r.status === 'completed')

    // Destroy previous chart
    if (chart) {
      chart.remove()
      chart = null
    }

    await nextTick()

    // Create chart
    chart = createChart(chartContainer.value, {
      layout: {
        background: { type: ColorType.Solid, color: '#1a1f2e' },
        textColor: '#94a3b8',
        fontFamily: "'Inter', sans-serif",
        fontSize: 12,
      },
      grid: {
        vertLines: { color: '#1e293b' },
        horzLines: { color: '#1e293b' },
      },
      crosshair: {
        mode: 0,
        vertLine: { color: '#6366f1', width: 1, style: 2, labelBackgroundColor: '#6366f1' },
        horzLine: { color: '#6366f1', width: 1, style: 2, labelBackgroundColor: '#6366f1' },
      },
      rightPriceScale: {
        borderColor: '#1e293b',
      },
      timeScale: {
        borderColor: '#1e293b',
        timeVisible: true,
        fixLeftEdge: true,
        fixRightEdge: true,
      },
      autoSize: true,
    })

    // Candlestick series
    candleSeries = chart.addSeries(CandlestickSeries, {
      upColor: '#22c55e',
      downColor: '#ef4444',
      borderDownColor: '#ef4444',
      borderUpColor: '#22c55e',
      wickDownColor: '#ef4444',
      wickUpColor: '#22c55e',
    })
    candleSeries.setData(ohlc.candles as any)

    // Volume series
    volumeSeries = chart.addSeries(HistogramSeries, {
      priceFormat: { type: 'volume' },
      priceScaleId: 'volume',
    })

    chart.priceScale('volume').applyOptions({
      scaleMargins: { top: 0.8, bottom: 0 },
    })

    const coloredVolumes = ohlc.volumes.map((v: VolumeItem, i: number) => ({
      ...v,
      color: i > 0 && ohlc.candles[i]?.close >= ohlc.candles[i]?.open
        ? 'rgba(34, 197, 94, 0.3)'
        : 'rgba(239, 68, 68, 0.3)',
    }))
    volumeSeries.setData(coloredVolumes as any)

    // Add markers for agent decisions
    if (runs.value.length > 0 && candleSeries) {
      // Create a Set of all available times in the candle series
      const validTimes = new Set(ohlc.candles.map(c => c.time))
      
      const markers = runs.value
        .filter(r => r.rating)
        // Filter by user toggles
        .filter(r => {
          const rating = r.rating?.toLowerCase() || ''
          if (rating.includes('buy') || rating.includes('overweight')) return showBuy.value
          if (rating.includes('sell') || rating.includes('underweight')) return showSell.value
          if (rating.includes('hold')) return showHold.value
          return true
        })
        // Ensure the trade_date actually exists in the chart data!
        .filter(r => validTimes.has(r.trade_date))
        .map(r => ({
          time: r.trade_date,
          position: (r.rating === 'Buy' || r.rating === 'Overweight') ? 'belowBar' as const : 'aboveBar' as const,
          color: (r.rating === 'Buy' || r.rating === 'Overweight') ? '#22c55e'
               : (r.rating === 'Sell' || r.rating === 'Underweight') ? '#ef4444'
               : '#f59e0b',
          shape: (r.rating === 'Buy' || r.rating === 'Overweight') ? 'arrowUp' as const
               : (r.rating === 'Sell' || r.rating === 'Underweight') ? 'arrowDown' as const
               : 'circle' as const,
          text: r.rating || '',
        }))
        .sort((a, b) => a.time.localeCompare(b.time))


      if (markers.length > 0) {
        createSeriesMarkers(candleSeries, markers as any)
      }
    }

    chart.timeScale().fitContent()
  } catch (e: any) {
    error.value = e.message || 'Failed to load chart data'
    console.error("Chart Error:", e)
  } finally {
    loading.value = false
  }
}

function changeTicker() {
  const t = tickerInput.value.trim().toUpperCase()
  if (t) {
    tickerInput.value = t
    router.replace({ name: 'chart', params: { ticker: t } })
    loadChart()
  }
}

// Watchers for automatic updates
watch([period, showBuy, showSell, showHold], () => loadChart())

// Auto-refresh when dates match the YYYY-MM-DD pattern (forgiving of single digits)
watch([dateFrom, dateTo], ([f, t]) => {
  const dateRegex = /^\d{4}-\d{1,2}-\d{1,2}$/
  if ((!f && !t) || (dateRegex.test(f) && dateRegex.test(t))) {
    loadChart()
  }
})

</script>

<template>
  <div class="p-4 md:p-8 max-w-7xl mx-auto">
    <!-- Header -->
    <div class="flex flex-col md:flex-row md:items-center md:justify-between gap-4 mb-6">
      <div class="flex items-center gap-3">
        <button @click="router.push('/')" class="p-2 rounded-lg hover:bg-[var(--color-bg-elevated)] text-[var(--color-text-muted)] transition-colors">
          <ArrowLeft :size="18" />
        </button>
        <div>
          <h1 class="text-2xl md:text-3xl font-bold">{{ tickerInput }}</h1>
          <p class="text-sm text-[var(--color-text-muted)]">Interactive price chart</p>
        </div>
      </div>

      <!-- Controls -->
      <div class="flex items-center gap-3 flex-wrap">
        <!-- Ticker Selector -->
        <div class="flex items-center gap-2">
          <select
            v-model="tickerInput"
            @change="changeTicker"
            class="w-64 px-3 py-2 rounded-lg bg-[var(--color-bg-elevated)] border border-[var(--color-border-default)] text-sm text-[var(--color-text-primary)] focus:outline-none focus:border-[var(--color-accent-primary)] appearance-none cursor-pointer"
          >
            <option v-for="t in availableTickers" :key="t.ticker" :value="t.ticker">
              {{ t.ticker }} — {{ t.name }}
            </option>
          </select>
        </div>

        <!-- Period Selector -->
        <div class="flex flex-col gap-1">
          <span class="text-[10px] uppercase font-black text-[var(--color-text-muted)] ml-1">Range Preset</span>
          <div class="flex rounded-lg border border-[var(--color-border-default)] overflow-hidden">
            <button
              v-for="p in periods"
              :key="p.value"
              @click="period = p.value; dateFrom = ''; dateTo = ''"
              class="px-3 py-2 text-xs font-medium transition-colors"
              :class="period === p.value && !dateFrom && !dateTo
                ? 'bg-[var(--color-accent-primary)] text-white'
                : 'bg-[var(--color-bg-elevated)] text-[var(--color-text-muted)] hover:text-[var(--color-text-primary)]'"
            >
              {{ p.label }}
            </button>
          </div>
        </div>

        <!-- Custom Date Range -->
        <div class="flex items-center gap-4 bg-[var(--color-bg-elevated)] p-2 rounded-xl border border-[var(--color-border-default)]">
          <div class="flex flex-col gap-0.5">
            <span class="text-[10px] uppercase font-black text-[var(--color-text-muted)] ml-1">Start Date</span>
            <input v-model="dateFrom" @blur="dateFrom = padDate(dateFrom)" type="text" placeholder="YYYY-MM-DD" class="bg-transparent border-none text-xs font-bold focus:ring-0 w-24 p-0" />
          </div>
          <div class="w-px h-8 bg-[var(--color-border-default)]"></div>
          <div class="flex flex-col gap-0.5">
            <span class="text-[10px] uppercase font-black text-[var(--color-text-muted)] ml-1">End Date</span>
            <input v-model="dateTo" @blur="dateTo = padDate(dateTo)" type="text" placeholder="YYYY-MM-DD" class="bg-transparent border-none text-xs font-bold focus:ring-0 w-24 p-0" />
          </div>
        </div>
      </div>
    </div>

    <!-- Chart -->
    <div class="relative rounded-xl bg-[var(--color-bg-card)] border border-[var(--color-border-default)] overflow-hidden">
      <!-- Active Filter Badge -->
      <div v-if="dateFrom && dateTo" class="absolute top-4 right-4 z-10 px-3 py-1 bg-[var(--color-accent-primary)] text-white text-[10px] font-black uppercase rounded-full shadow-lg flex items-center gap-2">
        <Clock :size="12" />
        Custom Range: {{ dateFrom }} to {{ dateTo }}
      </div>

      <div v-if="loading" class="h-[400px] md:h-[600px] flex items-center justify-center">
        <RefreshCw :size="24" class="animate-spin text-[var(--color-text-muted)]" />
      </div>
      <div v-else-if="error" class="h-[400px] md:h-[600px] flex items-center justify-center text-[var(--color-signal-sell)]">
        {{ error }}
      </div>
      <div v-show="!loading && !error" ref="chartContainer" class="h-[400px] md:h-[600px]"></div>
    </div>

    <!-- Agent Decision Legend & Toggles -->
    <div v-if="runs.length > 0" class="mt-4 flex flex-wrap gap-6 text-xs font-medium">
      <button 
        @click="showBuy = !showBuy"
        class="flex items-center gap-2 transition-opacity"
        :class="showBuy ? 'opacity-100' : 'opacity-40'"
      >
        <span class="w-3 h-3 rounded-full bg-[var(--color-signal-buy)]"></span>
        <span :class="showBuy ? 'text-[var(--color-text-primary)]' : 'text-[var(--color-text-muted)]'">Buy / Overweight</span>
      </button>

      <button 
        @click="showSell = !showSell"
        class="flex items-center gap-2 transition-opacity"
        :class="showSell ? 'opacity-100' : 'opacity-40'"
      >
        <span class="w-3 h-3 rounded-full bg-[var(--color-signal-sell)]"></span>
        <span :class="showSell ? 'text-[var(--color-text-primary)]' : 'text-[var(--color-text-muted)]'">Sell / Underweight</span>
      </button>

      <button 
        @click="showHold = !showHold"
        class="flex items-center gap-2 transition-opacity"
        :class="showHold ? 'opacity-100' : 'opacity-40'"
      >
        <span class="w-3 h-3 rounded-full bg-[var(--color-signal-hold)]"></span>
        <span :class="showHold ? 'text-[var(--color-text-primary)]' : 'text-[var(--color-text-muted)]'">Hold</span>
      </button>
    </div>

  </div>
</template>
