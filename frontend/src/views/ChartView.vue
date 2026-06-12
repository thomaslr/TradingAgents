<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount, watch, nextTick } from 'vue'
import { createChart, type IChartApi, type ISeriesApi, ColorType, CandlestickSeries, HistogramSeries, createSeriesMarkers, LineSeries, LineStyle, PriceScaleMode } from 'lightweight-charts'
import { fetchOHLC, fetchRuns, fetchTickers, fetchPerformanceData, type Run, type VolumeItem, type SimulationConfig, type PerformanceEntry, type MemoryEntry } from '../api/client'
import { ArrowLeft, RefreshCw, Clock } from 'lucide-vue-next'
import { useRouter } from 'vue-router'
import { activeTicker, setActiveTicker, configs, enabledConfigs, toggleConfig, loadConfigs } from '../store'

const props = defineProps<{ ticker?: string }>()
const router = useRouter()

const chartContainer = ref<HTMLDivElement>()
let chart: IChartApi | null = null
let candleSeries: ISeriesApi<'Candlestick'> | null = null
let volumeSeries: ISeriesApi<'Histogram'> | null = null

function safeConfigColor(c: SimulationConfig): string {
  const color = c.color || '#10b981'
  const lower = color.toLowerCase().trim()
  if (lower === '#ffffff' || lower === '#fff' || lower === 'white' || lower === 'rgb(255,255,255)' || lower === 'rgba(255,255,255,1)') {
    return '#10b981'
  }
  return color
}

const loading = ref(true)
const error = ref('')
const period = ref(localStorage.getItem('chart_period') || '3mo')
const dateFrom = ref(localStorage.getItem('chart_from') || '')
const dateTo = ref(localStorage.getItem('chart_to') || '')
if (props.ticker) {
  setActiveTicker(props.ticker)
}

const tickerInput = ref(activeTicker.value)

watch(activeTicker, (v) => {
  if (v) {
    tickerInput.value = v
    if (v !== props.ticker) {
      router.replace({ name: 'chart', params: { ticker: v } })
    }
  }
})

watch(() => props.ticker, (newTicker) => {
  if (newTicker && newTicker !== activeTicker.value) {
    setActiveTicker(newTicker)
  }
})

watch(activeTicker, () => {
  loadChart()
})
const availableTickers = ref<any[]>([])
const runs = ref<Run[]>([])
const showBuy = ref(true)
const showSell = ref(true)
const showHold = ref(false)

watch(period, (v) => localStorage.setItem('chart_period', v))
watch(dateFrom, (v) => localStorage.setItem('chart_from', v))
watch(dateTo, (v) => localStorage.setItem('chart_to', v))

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

watch(enabledConfigs, () => {
  loadChart()
}, { deep: true })

onMounted(async () => {
  await Promise.all([loadTickers(), loadConfigs()])
  if (tickerInput.value) {
    await loadChart()
  }
})

async function loadTickers() {
  try {
    availableTickers.value = await fetchTickers()
    
    if (!tickerInput.value && availableTickers.value.length > 0) {
      const defaultTicker = availableTickers.value[0].ticker
      setActiveTicker(defaultTicker)
      router.replace({ name: 'chart', params: { ticker: defaultTicker } })
    } else if (tickerInput.value) {
      setActiveTicker(tickerInput.value)
      if (!availableTickers.value.find(t => t.ticker === tickerInput.value)) {
        // If the current ticker isn't in the list, add a placeholder
        availableTickers.value.push({ ticker: tickerInput.value, name: tickerInput.value })
        availableTickers.value.sort((a, b) => a.ticker.localeCompare(b.ticker))
      }
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

// Strategy return overlay toggles & helpers
const showStrategyA = ref(localStorage.getItem('chart_show_strat_a') === 'true')
const showStrategyB = ref(localStorage.getItem('chart_show_strat_b') === 'true')
const showStrategyC = ref(localStorage.getItem('chart_show_strat_c') === 'true')

watch(showStrategyA, (v) => {
  localStorage.setItem('chart_show_strat_a', String(v))
  loadChart()
})
watch(showStrategyB, (v) => {
  localStorage.setItem('chart_show_strat_b', String(v))
  loadChart()
})
watch(showStrategyC, (v) => {
  localStorage.setItem('chart_show_strat_c', String(v))
  loadChart()
})

const benchmarkType = ref<'SPY' | 'ASSET'>((localStorage.getItem('perf_benchmark') as any) || 'ASSET')
const showCosts = ref(false)
const commissionPerTrade = ref(0.001)

function parsePct(val: string | null): number {
  if (!val) return 0
  const parsed = parseFloat(val.replace('%', ''))
  return isNaN(parsed) ? 0 : parsed / 100
}

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

function computeConfigReturns(configEntries: MemoryEntry[], ohlcCandles: any[] = []) {
  const weekdayEntries = configEntries.filter(e => !isWeekend(e.date))
  if (weekdayEntries.length === 0) {
    return { stratAPoints: [], stratBPoints: [], stratCPoints: [], benchPoints: [] }
  }

  const activeTickers = Array.from(new Set(weekdayEntries.map(e => e.ticker)))
  const tickerCount = activeTickers.length || 1
  const slotsPerTicker = 5
  const totalSlots = slotsPerTicker * tickerCount

  const dateGroups = new Map<string, MemoryEntry[]>()
  weekdayEntries.forEach(e => {
    if (!dateGroups.has(e.date)) dateGroups.set(e.date, [])
    dateGroups.get(e.date)!.push(e)
  })

  const runDates = Array.from(new Set(weekdayEntries.map(e => e.date)))
    .filter(d => !isWeekend(d))
    .sort()

  if (runDates.length === 0) {
    return { stratAPoints: [], stratBPoints: [], stratCPoints: [], benchPoints: [] }
  }

  const firstRunDate = runDates[0]
  const chartStartDate = ohlcCandles.length > 0 ? ohlcCandles[0].time : firstRunDate
  const startDate = chartStartDate < firstRunDate ? chartStartDate : firstRunDate

  const lastRunDate = runDates[runDates.length - 1]
  const endDate = getEndDateWithBuffer(lastRunDate, 5)
  const chartEndDate = ohlcCandles.length > 0 ? ohlcCandles[ohlcCandles.length - 1].time : endDate
  const endLimit = chartEndDate > endDate ? chartEndDate : endDate

  const datasetDates = getWeekdaysBetween(startDate, endLimit)

  let stratAValue = 100
  let stratBValue = 100
  let stratCValue = 100
  let benchValue = 100
  const stratAPoints: { time: string; value: number }[] = []
  const stratBPoints: { time: string; value: number }[] = []
  const stratCPoints: { time: string; value: number }[] = []
  const benchPoints: { time: string; value: number }[] = []

  let stratATrades: ActiveTrade[] = []
  let benchTrades: ActiveTrade[] = []

  const tickerWeightsB = new Map<string, number>()
  const tickerWeightsC = new Map<string, number>()
  activeTickers.forEach(t => {
    tickerWeightsB.set(t, 0.0)
    tickerWeightsC.set(t, 0.0)
  })

  datasetDates.forEach((date, idx) => {
    stratATrades = stratATrades.filter(t => idx < t.endIdx)
    benchTrades = benchTrades.filter(t => idx < t.endIdx)

    const dayEntries = dateGroups.get(date) || []
    let stratBTradeCostsToday = 0
    let stratCTradeCostsToday = 0

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

      // Strat A (5-Day Horizon) uses Portfolio Manager rating
      const pmRating = (e.rating || '').toLowerCase()
      const isPMLong = pmRating.includes('buy') || pmRating.includes('overweight')

      if (isPMLong) {
        let dailyStratRet = dailyBenchRet
        if (showCosts.value) {
          const cost = commissionPerTrade.value
          dailyStratRet -= (cost / 5)
        }
        stratATrades.push({
          startIdx: idx,
          endIdx: idx + 5,
          dailyReturn: dailyStratRet,
          ticker: e.ticker
        })
      }

      // Strat B (Portfolio Manager Dynamic) weight updates
      const prevPMWeight = tickerWeightsB.get(e.ticker) ?? 0.0
      const newPMWeight = getTargetWeight(e.rating, prevPMWeight)
      if (newPMWeight !== prevPMWeight) {
        tickerWeightsB.set(e.ticker, newPMWeight)
        if (showCosts.value) {
          const cost = commissionPerTrade.value
          const costForTicker = cost * Math.abs(newPMWeight - prevPMWeight) / tickerCount
          stratBTradeCostsToday += costForTicker
        }
      }

      // Strat C (Trader Dynamic) weight updates
      const prevTraderWeight = tickerWeightsC.get(e.ticker) ?? 0.0
      const newTraderWeight = getTargetWeight(e.decision || '', prevTraderWeight)
      if (newTraderWeight !== prevTraderWeight) {
        tickerWeightsC.set(e.ticker, newTraderWeight)
        if (showCosts.value) {
          const cost = commissionPerTrade.value
          const costForTicker = cost * Math.abs(newTraderWeight - prevTraderWeight) / tickerCount
          stratCTradeCostsToday += costForTicker
        }
      }
    })

    const benchDailyRet = benchTrades.reduce((sum, t) => sum + t.dailyReturn, 0) / totalSlots
    const stratADailyRet = stratATrades.reduce((sum, t) => sum + t.dailyReturn, 0) / totalSlots

    let stratBDailyRetSum = 0
    activeTickers.forEach(T => {
      const weight = tickerWeightsB.get(T) ?? 0.0
      const activeBenchTradesForTicker = benchTrades.filter(t => t.ticker === T)
      const sumActiveBenchReturns = activeBenchTradesForTicker.reduce((sum, t) => sum + t.dailyReturn, 0)
      const tickerDailyBenchmarkReturn = sumActiveBenchReturns / 5
      stratBDailyRetSum += weight * tickerDailyBenchmarkReturn
    })
    let stratBDailyRet = stratBDailyRetSum / tickerCount
    if (showCosts.value) {
      stratBDailyRet -= stratBTradeCostsToday
    }

    let stratCDailyRetSum = 0
    activeTickers.forEach(T => {
      const weight = tickerWeightsC.get(T) ?? 0.0
      const activeBenchTradesForTicker = benchTrades.filter(t => t.ticker === T)
      const sumActiveBenchReturns = activeBenchTradesForTicker.reduce((sum, t) => sum + t.dailyReturn, 0)
      const tickerDailyBenchmarkReturn = sumActiveBenchReturns / 5
      stratCDailyRetSum += weight * tickerDailyBenchmarkReturn
    })
    let stratCDailyRet = stratCDailyRetSum / tickerCount
    if (showCosts.value) {
      stratCDailyRet -= stratCTradeCostsToday
    }

    benchValue = benchValue * (1 + benchDailyRet)
    stratAValue = stratAValue * (1 + stratADailyRet)
    stratBValue = stratBValue * (1 + stratBDailyRet)
    stratCValue = stratCValue * (1 + stratCDailyRet)

    stratAPoints.push({ time: date, value: stratAValue })
    stratBPoints.push({ time: date, value: stratBValue })
    stratCPoints.push({ time: date, value: stratCValue })
    benchPoints.push({ time: date, value: benchValue })
  })

  return { stratAPoints, stratBPoints, stratCPoints, benchPoints }
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

    const [ohlc, allRuns, perfEntries] = await Promise.all([
      fetchOHLC(
        tickerInput.value, 
        period.value, 
        '1d', 
        useDates ? dateFrom.value : undefined, 
        useDates ? dateTo.value : undefined
      ),
      fetchRuns(tickerInput.value),
      fetchPerformanceData({ ticker: tickerInput.value })
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
      leftPriceScale: {
        visible: true,
        borderColor: '#1e293b',
        mode: PriceScaleMode.Percentage,
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

    // Percentage helper series on the left scale
    const percentSeries = chart.addSeries(LineSeries, {
      priceScaleId: 'left',
      color: 'transparent',
      lastValueVisible: false,
      priceLineVisible: false,
    })
    percentSeries.setData(ohlc.candles.map(c => ({ time: c.time, value: c.close })) as any)

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
        // Match each run to its simulation configuration
        .map(r => {
          const matchedConfig = configs.value.find(c => 
            c.provider === r.provider &&
            c.quick_model === r.quick_model &&
            c.deep_model === r.deep_model &&
            c.depth === r.depth
          )
          return { run: r, config: matchedConfig }
        })
        // Filter by enabledConfigs: only show signals from active model configurations
        .filter(({ config }) => config && enabledConfigs.value.has(config.config_id))
        // Filter by user toggles (Buy, Sell, Hold)
        .filter(({ run }) => {
          const rating = run.rating?.toLowerCase() || ''
          if (rating.includes('buy') || rating.includes('overweight')) return showBuy.value
          if (rating.includes('sell') || rating.includes('underweight')) return showSell.value
          if (rating.includes('hold')) return showHold.value
          return true
        })
        // Ensure the trade_date actually exists in the chart data!
        .filter(({ run }) => validTimes.has(run.trade_date))
        .map(({ run, config }) => {
          const rating = run.rating || ''
          const isBuy = rating === 'Buy' || rating === 'Overweight'
          const isSell = rating === 'Sell' || rating === 'Underweight'
          
          return {
            time: run.trade_date,
            position: isBuy ? 'belowBar' as const : isSell ? 'aboveBar' as const : 'inBar' as const,
            color: safeConfigColor(config!),
            shape: isBuy ? 'arrowUp' as const : isSell ? 'arrowDown' as const : 'circle' as const,
            text: rating,
          }
        })
        .sort((a, b) => a.time.localeCompare(b.time))

      // Update series markers (clear previous markers if empty)
      createSeriesMarkers(candleSeries, markers as any)
    }

    // Add Strategy Overlay Curves
    if (perfEntries && perfEntries.length > 0 && (showStrategyA.value || showStrategyB.value || showStrategyC.value)) {
      // Group performance entries by config_id
      const entriesByConfig = new Map<string, PerformanceEntry[]>()
      perfEntries.forEach(e => {
        if (!entriesByConfig.has(e.config_id)) {
          entriesByConfig.set(e.config_id, [])
        }
        entriesByConfig.get(e.config_id)!.push(e)
      })

      // Map to quickly find stock price on a date
      const priceMap = new Map(ohlc.candles.map(c => [c.time, c.close]))

      const activeStrategySeriesList: {
        series: any;
        rawPoints: { time: string; value: number }[];
      }[] = []

      // For each enabled configuration
      configs.value.forEach(config => {
        if (!enabledConfigs.value.has(config.config_id)) return

        const configEntries = entriesByConfig.get(config.config_id) || []
        if (configEntries.length === 0) return

        // Adapt to MemoryEntry shape expected by computeConfigReturns
        const adaptedEntries: MemoryEntry[] = configEntries.map(e => ({
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
          config_id: e.config_id
        })).sort((a, b) => a.date.localeCompare(b.date))

        const { stratAPoints, stratBPoints, stratCPoints } = computeConfigReturns(adaptedEntries, ohlc.candles)

        // Draw Strategy A (Horizon)
        if (showStrategyA.value && stratAPoints.length > 0) {
          const series = chart!.addSeries(LineSeries, {
            color: safeConfigColor(config),
            lineWidth: 3,
          })
          activeStrategySeriesList.push({
            series,
            rawPoints: stratAPoints
          })
        }

        // Draw Strategy B (Portfolio Manager)
        if (showStrategyB.value && stratBPoints.length > 0) {
          const series = chart!.addSeries(LineSeries, {
            color: safeConfigColor(config),
            lineWidth: 3,
            lineStyle: LineStyle.Dotted,
          })
          activeStrategySeriesList.push({
            series,
            rawPoints: stratBPoints
          })
        }

        // Draw Strategy C (Trading Agent)
        if (showStrategyC.value && stratCPoints.length > 0) {
          const series = chart!.addSeries(LineSeries, {
            color: safeConfigColor(config),
            lineWidth: 3,
            lineStyle: LineStyle.Dashed,
          })
          activeStrategySeriesList.push({
            series,
            rawPoints: stratCPoints
          })
        }
      })

      // Function to dynamically update normalization as visible range shifts (zoom/scroll)
      function updateNormalization() {
        if (!chart || activeStrategySeriesList.length === 0) return
        const range = chart.timeScale().getVisibleRange()
        if (!range) return

        const firstVisibleCandle = ohlc.candles.find(c => c.time >= range.from) || ohlc.candles[0]
        if (!firstVisibleCandle) return

        const chartStartTime = firstVisibleCandle.time
        const startPrice = firstVisibleCandle.close

        activeStrategySeriesList.forEach(({ series, rawPoints }) => {
          const startPoint = rawPoints.find(p => p.time === chartStartTime) || rawPoints.find(p => p.time >= chartStartTime) || rawPoints[0]
          const startStratValue = startPoint ? startPoint.value : 100

          const normalizedData = rawPoints
            .filter(p => priceMap.has(p.time) && p.time >= chartStartTime)
            .map(p => ({
              time: p.time,
              value: p.value * (startPrice / startStratValue)
            }))
          series.setData(normalizedData as any)
        })
      }

      // Perform initial alignment
      updateNormalization()

      // Subscribe to visible range changes (covers mouse wheel zoom and dragging)
      chart.timeScale().subscribeVisibleTimeRangeChange(updateNormalization)
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
    setActiveTicker(t)
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

      <div class="w-px h-6 bg-[var(--color-border-default)] self-center"></div>

      <button 
        @click="showStrategyA = !showStrategyA"
        class="flex items-center gap-2 transition-opacity"
        :class="showStrategyA ? 'opacity-100' : 'opacity-40'"
      >
        <span class="font-bold text-xs text-emerald-400">──</span>
        <span :class="showStrategyA ? 'text-[var(--color-text-primary)] font-bold' : 'text-[var(--color-text-muted)]'">5-Day Horizon (Solid)</span>
      </button>

      <button 
        @click="showStrategyB = !showStrategyB"
        class="flex items-center gap-2 transition-opacity"
        :class="showStrategyB ? 'opacity-100' : 'opacity-40'"
      >
        <span class="font-bold text-xs text-emerald-400">┈┈</span>
        <span :class="showStrategyB ? 'text-[var(--color-text-primary)] font-bold' : 'text-[var(--color-text-muted)]'">Portfolio Manager (Dotted)</span>
      </button>

      <button 
        @click="showStrategyC = !showStrategyC"
        class="flex items-center gap-2 transition-opacity"
        :class="showStrategyC ? 'opacity-100' : 'opacity-40'"
      >
        <span class="font-bold text-xs text-emerald-400">╌╌</span>
        <span :class="showStrategyC ? 'text-[var(--color-text-primary)] font-bold' : 'text-[var(--color-text-muted)]'">Trading Agent (Dashed)</span>
      </button>

      <!-- Config Toggles -->
      <template v-if="configs.length > 1">
        <div class="w-px h-6 bg-[var(--color-border-default)] self-center"></div>
        <button
          v-for="c in configs"
          :key="c.config_id"
          @click="toggleConfig(c.config_id)"
          class="flex items-center gap-2 transition-opacity"
          :class="enabledConfigs.has(c.config_id) ? 'opacity-100' : 'opacity-40'"
        >
          <span class="w-3 h-3 rounded-full" :style="{ backgroundColor: safeConfigColor(c) }"></span>
          <span :class="enabledConfigs.has(c.config_id) ? 'text-[var(--color-text-primary)]' : 'text-[var(--color-text-muted)]'">{{ c.label }}</span>
        </button>
      </template>
    </div>

  </div>
</template>
