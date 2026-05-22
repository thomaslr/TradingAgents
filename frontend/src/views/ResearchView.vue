<script setup lang="ts">
import { ref, onMounted, computed, watch } from 'vue'
import { fetchMetrics, fetchCacheStats, clearAnalystCache, type AnalysisMetrics, type CacheStats, type SimulationConfig } from '../api/client'
import { Beaker, Zap, Cpu, BarChart3, RefreshCw, Layers, ArrowUpDown, ArrowUp, ArrowDown } from 'lucide-vue-next'
import { configs, enabledConfigs, loadConfigs, activeTicker } from '../store'
import ConfigFilterPanel from '../components/ConfigFilterPanel.vue'
import ConfigDisplay from '../components/ConfigDisplay.vue'

const metrics = ref<AnalysisMetrics[]>([])
const loading = ref(true)
const hoveredGroup = ref<any>(null)

const sortKey = ref<string>('created_at')
const sortOrder = ref<'asc' | 'desc'>('desc')

const isAnalyticsCollapsed = ref(localStorage.getItem('res_analytics_collapsed') === 'true')
const isTableCollapsed = ref(localStorage.getItem('res_table_collapsed') === 'true')

watch(isAnalyticsCollapsed, (v) => localStorage.setItem('res_analytics_collapsed', String(v)))
watch(isTableCollapsed, (v) => localStorage.setItem('res_table_collapsed', String(v)))

watch(activeTicker, () => {
  loadMetrics()
})

function safeConfigColor(c: SimulationConfig): string {
  const color = c.color || '#10b981'
  const lower = color.toLowerCase().trim()
  if (lower === '#ffffff' || lower === '#fff' || lower === 'white' || lower === 'rgb(255,255,255)' || lower === 'rgba(255,255,255,1)') {
    return '#10b981'
  }
  return color
}

// shootout aggregates
const shootoutStats = computed(() => {
  const groups = new Map<string, {
    quick_model: string;
    deep_model: string;
    depth: number;
    runs: AnalysisMetrics[];
  }>()

  filteredMetrics.value.forEach(m => {
    if (!m.quick_model || !m.deep_model) return
    const key = `${m.quick_model} | ${m.deep_model} | ${m.depth} Rounds`
    if (!groups.has(key)) {
      groups.set(key, {
        quick_model: m.quick_model,
        deep_model: m.deep_model,
        depth: Number(m.depth) || 0,
        runs: []
      })
    }
    groups.get(key)!.runs.push(m)
  })

  return Array.from(groups.entries()).map(([key, group], sIndex) => {
    const latencies = group.runs.map(r => r.total_sec).filter(t => t > 0)
    const tpsValues = group.runs.map(r => r.avg_tps).filter(t => t > 0)
    
    const count = group.runs.length
    const avgLatency = latencies.length ? latencies.reduce((a, b) => a + b, 0) / latencies.length : 0
    const avgTps = tpsValues.length ? tpsValues.reduce((a, b) => a + b, 0) / tpsValues.length : 0
    
    const minLatency = latencies.length ? Math.min(...latencies) : 0
    const maxLatency = latencies.length ? Math.max(...latencies) : 0
    const sortedLatencies = [...latencies].sort((a, b) => a - b)

    // Lookup the shared configuration color to align exactly across all views
    const matchedConfig = configs.value.find(c => 
      c.quick_model === group.quick_model &&
      c.deep_model === group.deep_model &&
      c.depth === group.depth
    )
    const color = matchedConfig ? safeConfigColor(matchedConfig) : `hsl(${(sIndex * 137.5) % 360}, 85%, 60%)`

    return {
      key,
      quick_model: group.quick_model,
      deep_model: group.deep_model,
      depth: group.depth,
      count,
      avgLatency,
      avgTps,
      minLatency,
      maxLatency,
      sortedLatencies,
      latencies,
      color
    }
  }).sort((a, b) => b.count - a.count)
})

const cdfData = computed(() => {
  if (shootoutStats.value.length === 0) return null

  const allLatencies = shootoutStats.value.flatMap(s => s.latencies)
  if (allLatencies.length === 0) return null

  const globalMin = 0
  const globalMax = Math.max(...allLatencies)
  
  const steps = 30
  const stepSize = globalMax / steps
  const xValues = Array.from({ length: steps + 1 }, (_, i) => i * stepSize)

  const series = shootoutStats.value.map((stat) => {
    const latencies = stat.sortedLatencies
    const points = xValues.map(x => {
      const completedCount = latencies.filter(l => l <= x).length
      const percentage = (completedCount / latencies.length) * 100
      return { x, y: percentage }
    })

    return {
      label: stat.key,
      color: stat.color,
      points,
      stat
    }
  })

  return {
    globalMin,
    globalMax,
    xValues,
    series
  }
})

function getSvgCoords(x: number, y: number, minX: number, maxX: number) {
  const padding = { top: 20, right: 30, bottom: 40, left: 50 }
  const width = 800
  const height = 240
  
  const plotWidth = width - padding.left - padding.right
  const plotHeight = height - padding.top - padding.bottom
  
  const rangeX = maxX - minX || 1
  const pctX = (x - minX) / rangeX
  const svgX = padding.left + pctX * plotWidth
  
  const pctY = y / 100
  const svgY = padding.top + (1 - pctY) * plotHeight
  
  return { x: svgX, y: svgY }
}

function getCdfPath(points: {x: number, y: number}[], minX: number, maxX: number): string {
  if (points.length === 0) return ''
  return points.map((p, i) => {
    const coords = getSvgCoords(p.x, p.y, minX, maxX)
    return `${i === 0 ? 'M' : 'L'} ${coords.x.toFixed(1)} ${coords.y.toFixed(1)}`
  }).join(' ')
}

function toggleSort(key: string) {
  if (sortKey.value === key) {
    sortOrder.value = sortOrder.value === 'asc' ? 'desc' : 'asc'
  } else {
    sortKey.value = key
    sortOrder.value = 'desc'
  }
}

const cacheStats = ref<CacheStats>({
  total_reports: 0,
  unique_tickers: 0,
  estimated_tokens_saved: 0,
  estimated_seconds_saved: 0
})
const purging = ref(false)

onMounted(async () => {
  await Promise.all([
    loadMetrics(),
    loadCacheStats(),
    loadConfigs()
  ])
})

async function loadMetrics() {
  loading.value = true
  try {
    metrics.value = await fetchMetrics(500, activeTicker.value)
  } catch (e) {
    console.error('Failed to load research metrics', e)
  } finally {
    loading.value = false
  }
}

async function loadCacheStats() {
  try {
    cacheStats.value = await fetchCacheStats()
  } catch (e) {
    console.error('Failed to load cache stats', e)
  }
}

async function purgeCache() {
  if (!confirm('Are you sure you want to clear the analyst report cache? This will delete all cached reports from the shared library.')) return
  purging.value = true
  try {
    await clearAnalystCache()
    await loadCacheStats()
  } catch (e) {
    console.error('Failed to purge cache', e)
  } finally {
    purging.value = false
  }
}

// Stats
const hasMetrics = computed(() => {
  return metrics.value.some(m => m.metrics_id !== null && m.metrics_id !== undefined)
})

const avgTps = computed(() => {
  const valid = metrics.value.filter(m => m.metrics_id !== null && m.metrics_id !== undefined && m.avg_tps > 0)
  if (valid.length === 0) return 0
  const total = valid.reduce((acc, m) => acc + m.avg_tps, 0)
  return total / valid.length
})

const totalTokens = computed(() => {
  const valid = metrics.value.filter(m => m.metrics_id !== null && m.metrics_id !== undefined)
  return valid.reduce((acc, m) => acc + m.input_tokens + m.output_tokens, 0)
})

const filteredMetrics = computed(() => {
  // Filter by active ticker first
  let result = metrics.value.filter(m => m.ticker === activeTicker.value)

  // Filter by enabled simulation configs
  if (configs.value.length > 0 && enabledConfigs.value.size > 0 && enabledConfigs.value.size < configs.value.length) {
    result = result.filter(m => {
      const matched = configs.value.find(c => 
        c.quick_model === m.quick_model &&
        c.deep_model === m.deep_model &&
        c.depth === Number(m.depth)
      )
      return matched && enabledConfigs.value.has(matched.config_id)
    })
  } else if (enabledConfigs.value.size === 0) {
    result = []
  }

  // Apply Sorting
  if (sortKey.value) {
    result = [...result].sort((a, b) => {
      let aVal = (a as any)[sortKey.value]
      let bVal = (b as any)[sortKey.value]

      if (aVal === null || aVal === undefined) return sortOrder.value === 'asc' ? 1 : -1
      if (bVal === null || bVal === undefined) return sortOrder.value === 'asc' ? -1 : 1

      if (typeof aVal === 'string') {
        return sortOrder.value === 'asc'
          ? aVal.localeCompare(bVal)
          : bVal.localeCompare(aVal)
      } else {
        return sortOrder.value === 'asc'
          ? (aVal > bVal ? 1 : -1)
          : (bVal > aVal ? 1 : -1)
      }
    })
  }

  return result
})



function formatTime(sec: number) {
  if (sec < 60) return `${sec.toFixed(1)}s`
  const m = Math.floor(sec / 60)
  const s = Math.round(sec % 60)
  return `${m}m ${s}s`
}

function formatRunDate(dateStr: string | null): string {
  if (!dateStr) return '—'
  let cleanStr = dateStr
  if (!cleanStr.endsWith('Z') && !cleanStr.includes('+')) {
    const hasOffset = /[-+]\d{2}:?\d{2}$/.test(cleanStr)
    if (!hasOffset) {
      cleanStr += 'Z'
    }
  }
  const d = new Date(cleanStr)
  if (isNaN(d.getTime())) return dateStr
  return d.toLocaleString('en-SG', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })
}
</script>

<template>
  <div class="min-h-screen bg-[var(--color-bg-default)] text-[var(--color-text-primary)] p-8">
    <!-- Header -->
    <div class="flex flex-col md:flex-row md:items-center justify-between gap-6 mb-12">
      <div class="space-y-2">
        <div class="flex items-center gap-3">
          <div class="p-3 bg-[var(--color-accent-primary)]/20 rounded-xl">
            <Beaker :size="32" class="text-[var(--color-accent-primary)]" />
          </div>
          <h1 class="text-4xl font-black tracking-tighter uppercase italic">Research Lab</h1>
        </div>
        <p class="text-[var(--color-text-muted)] font-medium max-w-2xl">
          Deep performance benchmarking for analyst models. Track latencies, token throughput, and segment efficiency across your entire research history.
        </p>
      </div>

      <button 
        @click="loadMetrics" 
        class="flex items-center gap-2 px-6 py-3 bg-[var(--color-bg-card)] border border-[var(--color-border-default)] rounded-xl font-bold uppercase text-xs tracking-widest hover:bg-[var(--color-bg-elevated)] transition-all"
      >
        <RefreshCw :size="16" :class="{ 'animate-spin': loading }" />
        Refresh Data
      </button>
    </div>

    <!-- Quick Stats -->
    <div class="grid grid-cols-1 md:grid-cols-4 gap-8 mb-12">
      <div class="bg-[var(--color-bg-card)] border border-[var(--color-border-default)] rounded-2xl p-8 shadow-xl relative overflow-hidden group">
        <Zap class="absolute -right-4 -bottom-4 opacity-5 group-hover:scale-125 transition-transform duration-500" :size="120" />
        <p class="text-xs font-black text-[var(--color-text-muted)] uppercase tracking-widest mb-2">Average Throughput</p>
        <h3 class="text-5xl font-black tracking-tighter flex items-end gap-2">
          <template v-if="hasMetrics">
            {{ avgTps.toFixed(1) }}
            <span class="text-xl text-[var(--color-text-muted)] mb-2 uppercase font-black tracking-widest">tps</span>
          </template>
          <template v-else>
            <span class="text-3xl text-[var(--color-text-muted)] font-bold font-mono">—</span>
          </template>
        </h3>
      </div>
      
      <div class="bg-[var(--color-bg-card)] border border-[var(--color-border-default)] rounded-2xl p-8 shadow-xl relative overflow-hidden group">
        <Cpu class="absolute -right-4 -bottom-4 opacity-5 group-hover:scale-125 transition-transform duration-500" :size="120" />
        <p class="text-xs font-black text-[var(--color-text-muted)] uppercase tracking-widest mb-2">Total Intelligence Processed</p>
        <h3 class="text-5xl font-black tracking-tighter flex items-end gap-2">
          <template v-if="hasMetrics">
            {{ (totalTokens / 1000).toFixed(1) }}k
            <span class="text-xl text-[var(--color-text-muted)] mb-2 uppercase font-black tracking-widest">tokens</span>
          </template>
          <template v-else>
            <span class="text-3xl text-[var(--color-text-muted)] font-bold font-mono">—</span>
          </template>
        </h3>
      </div>

      <div class="bg-[var(--color-bg-card)] border border-[var(--color-border-default)] rounded-2xl p-8 shadow-xl relative overflow-hidden group">
        <BarChart3 class="absolute -right-4 -bottom-4 opacity-5 group-hover:scale-125 transition-transform duration-500" :size="120" />
        <p class="text-xs font-black text-[var(--color-text-muted)] uppercase tracking-widest mb-2">Historical Benchmarks</p>
        <h3 class="text-5xl font-black tracking-tighter flex items-end gap-2">
          {{ metrics.length }}
          <span class="text-xl text-[var(--color-text-muted)] mb-2 uppercase font-black tracking-widest">runs</span>
        </h3>
      </div>

      <div class="bg-[var(--color-bg-card)] border border-[var(--color-border-default)] rounded-2xl p-8 shadow-xl relative overflow-hidden group flex flex-col justify-between">
        <Layers class="absolute -right-4 -bottom-4 opacity-5 group-hover:scale-125 transition-transform duration-500" :size="120" />
        <div>
          <p class="text-xs font-black text-[var(--color-text-muted)] uppercase tracking-widest mb-2">Analyst Report Cache</p>
          <h3 class="text-5xl font-black tracking-tighter flex items-end gap-2">
            {{ cacheStats.total_reports }}
            <span class="text-xl text-[var(--color-text-muted)] mb-2 uppercase font-black tracking-widest">reports</span>
          </h3>
          <p class="text-[10px] font-bold text-[var(--color-text-muted)] uppercase tracking-wider mt-2">
            Saved ~{{ (cacheStats.estimated_tokens_saved / 1000).toFixed(0) }}k tokens / {{ (cacheStats.estimated_seconds_saved / 60).toFixed(1) }}m compute
          </p>
        </div>
        <button 
          @click="purgeCache"
          :disabled="purging || cacheStats.total_reports === 0"
          class="mt-6 px-4 py-2 border border-red-500/20 disabled:border-[var(--color-border-default)] bg-red-500/10 hover:bg-red-500/25 disabled:bg-transparent text-red-400 disabled:text-[var(--color-text-muted)] rounded-xl font-bold uppercase text-[10px] tracking-widest transition-all text-center disabled:cursor-not-allowed"
        >
          {{ purging ? 'Clearing...' : 'Wipe cache library' }}
        </button>
      </div>
    </div>

    <!-- Simulation Configs Filter Panel -->
    <ConfigFilterPanel margin-class="mb-8" />

    <!-- Analytics Section (Collapsable) -->
    <div v-if="hasMetrics && cdfData" class="bg-[var(--color-bg-card)] border border-[var(--color-border-default)] rounded-2xl overflow-hidden shadow-2xl mb-8">
      <div 
        @click="isAnalyticsCollapsed = !isAnalyticsCollapsed" 
        class="flex items-center justify-between p-5 border-b border-[var(--color-border-default)] bg-[var(--color-bg-elevated)]/20 cursor-pointer select-none hover:bg-[var(--color-bg-elevated)]/30 transition-colors"
      >
        <div class="flex items-center gap-2.5">
          <Beaker :size="18" class="text-[var(--color-accent-primary)]" />
          <h2 class="text-sm font-bold uppercase tracking-wider">Performance Shootout Analytics</h2>
          <span v-if="isAnalyticsCollapsed" class="text-[9px] font-black tracking-widest text-[var(--color-text-muted)] bg-white/5 border border-white/5 px-2 py-0.5 rounded">Collapsed</span>
        </div>
        <div class="flex items-center gap-2">
          <span class="text-[10px] text-[var(--color-text-muted)] font-black uppercase tracking-widest">{{ isAnalyticsCollapsed ? 'Expand' : 'Collapse' }}</span>
          <ArrowDown :size="14" class="transition-transform duration-300" :class="{ '-rotate-180': !isAnalyticsCollapsed }" />
        </div>
      </div>
      
      <div v-show="!isAnalyticsCollapsed" class="p-6 md:p-8 grid grid-cols-1 lg:grid-cols-5 gap-8">
        <!-- CDF Chart Area -->
        <div class="lg:col-span-3 space-y-4">
          <div>
            <h3 class="text-xs font-black uppercase tracking-widest text-[var(--color-text-muted)] mb-1">Cumulative Distribution Function (CDF)</h3>
            <p class="text-[10px] text-[var(--color-text-muted)] leading-relaxed">
              Compares completed runs percentage against latency. Steeper curves to the left denote consistently faster configurations.
            </p>
          </div>
          
          <div class="relative bg-black/25 rounded-xl border border-white/5 p-4 overflow-hidden">
            <svg viewBox="0 0 800 240" class="w-full h-auto font-mono select-none">
              <defs>
                <filter id="glow-lines" x="-20%" y="-20%" width="140%" height="140%">
                  <feGaussianBlur stdDeviation="3" result="blur" />
                  <feMerge>
                    <feMergeNode in="blur" />
                    <feMergeNode in="SourceGraphic" />
                  </feMerge>
                </filter>
              </defs>

              <!-- Y-Axis Percentile Grid lines -->
              <line x1="50" y1="20" x2="770" y2="20" stroke="#334155" stroke-dasharray="4 4" stroke-width="1" />
              <text x="40" y="24" fill="#64748b" text-anchor="end" class="text-[9px] font-black">100%</text>

              <line x1="50" y1="65" x2="770" y2="65" stroke="#1e293b" stroke-dasharray="4 4" stroke-width="1" />
              <text x="40" y="69" fill="#64748b" text-anchor="end" class="text-[9px] font-black">75%</text>

              <line x1="50" y1="110" x2="770" y2="110" stroke="#1e293b" stroke-dasharray="4 4" stroke-width="1" />
              <text x="40" y="114" fill="#64748b" text-anchor="end" class="text-[9px] font-black">50%</text>

              <line x1="50" y1="155" x2="770" y2="155" stroke="#1e293b" stroke-dasharray="4 4" stroke-width="1" />
              <text x="40" y="159" fill="#64748b" text-anchor="end" class="text-[9px] font-black">25%</text>

              <line x1="50" y1="200" x2="770" y2="200" stroke="#334155" stroke-width="1.5" />
              <text x="40" y="204" fill="#64748b" text-anchor="end" class="text-[9px] font-black">0%</text>

              <!-- X-Axis Line -->
              <line x1="50" y1="20" x2="50" y2="200" stroke="#334155" stroke-width="1.5" />

              <!-- X-Axis Latency Markers -->
              <!-- 25% Marker -->
              <line :x1="50 + 720 * 0.25" y1="20" :x2="50 + 720 * 0.25" y2="200" stroke="#1e293b" stroke-dasharray="4 4" stroke-width="1" />
              <text :x="50 + 720 * 0.25" y="215" fill="#64748b" text-anchor="middle" class="text-[9px] font-black">
                {{ formatTime(cdfData.globalMax * 0.25) }}
              </text>

              <!-- 50% Marker -->
              <line :x1="50 + 720 * 0.5" y1="20" :x2="50 + 720 * 0.5" y2="200" stroke="#1e293b" stroke-dasharray="4 4" stroke-width="1" />
              <text :x="50 + 720 * 0.5" y="215" fill="#64748b" text-anchor="middle" class="text-[9px] font-black">
                {{ formatTime(cdfData.globalMax * 0.5) }}
              </text>

              <!-- 75% Marker -->
              <line :x1="50 + 720 * 0.75" y1="20" :x2="50 + 720 * 0.75" y2="200" stroke="#1e293b" stroke-dasharray="4 4" stroke-width="1" />
              <text :x="50 + 720 * 0.75" y="215" fill="#64748b" text-anchor="middle" class="text-[9px] font-black">
                {{ formatTime(cdfData.globalMax * 0.75) }}
              </text>

              <!-- 100% Marker -->
              <line x1="770" y1="20" x2="770" y2="200" stroke="#334155" stroke-dasharray="4 4" stroke-width="1" />
              <text x="770" y="215" fill="#64748b" text-anchor="middle" class="text-[9px] font-black">
                {{ formatTime(cdfData.globalMax) }}
              </text>

              <!-- Series CDF Lines -->
              <path 
                v-for="s in cdfData.series" 
                :key="s.label" 
                :d="getCdfPath(s.points, cdfData.globalMin, cdfData.globalMax)" 
                fill="none" 
                :stroke="s.color" 
                stroke-width="2.5" 
                stroke-linecap="round" 
                stroke-linejoin="round"
                filter="url(#glow-lines)"
                class="transition-all duration-300 pointer-events-none"
                :class="{ 'opacity-100': !hoveredGroup || hoveredGroup.key === s.label, 'opacity-25': hoveredGroup && hoveredGroup.key !== s.label }"
              />

              <!-- Hover hit-target line (invisible & thick for premium interaction) -->
              <path 
                v-for="s in cdfData.series" 
                :key="'hit-' + s.label" 
                :d="getCdfPath(s.points, cdfData.globalMin, cdfData.globalMax)" 
                fill="none" 
                stroke="transparent" 
                stroke-width="14" 
                stroke-linecap="round" 
                stroke-linejoin="round"
                class="cursor-pointer"
                @mouseenter="hoveredGroup = s.stat"
                @mouseleave="hoveredGroup = null"
              />
            </svg>

            <!-- Floating Tooltip Card -->
            <div 
              v-if="hoveredGroup" 
              class="absolute top-4 left-1/2 transform -translate-x-1/2 bg-[#0c101b]/95 border border-white/10 p-4 rounded-xl shadow-2xl z-20 w-80 space-y-3 backdrop-blur-md transition-all duration-200 pointer-events-none"
              :style="{ borderTop: `3px solid ${hoveredGroup.color}` }"
            >
              <div class="flex items-center justify-between border-b border-white/5 pb-2">
                <span class="text-[9px] font-black text-white uppercase tracking-widest">Simulation Config</span>
                <span class="text-[8px] font-black text-[var(--color-text-muted)] bg-white/5 px-2 py-0.5 rounded font-mono">{{ hoveredGroup.count }} runs</span>
              </div>
              
              <!-- Unified Configuration Layout -->
              <div class="space-y-1.5 text-left">
                <div class="flex items-center justify-between">
                  <span class="text-[8px] font-black text-amber-500/80 uppercase tracking-widest">Quick:</span>
                  <span class="text-[10px] font-mono font-bold text-white bg-white/5 px-1.5 py-0.5 rounded">{{ hoveredGroup.quick_model }}</span>
                </div>
                <div class="flex items-center justify-between">
                  <span class="text-[8px] font-black text-blue-400 uppercase tracking-widest">Deep:</span>
                  <span class="text-[10px] font-mono font-bold text-white bg-white/5 px-1.5 py-0.5 rounded">{{ hoveredGroup.deep_model }}</span>
                </div>
                <div class="flex items-center justify-between">
                  <span class="text-[8px] font-black text-purple-400 uppercase tracking-widest">Depth:</span>
                  <span class="text-[10px] font-mono font-bold text-purple-300 bg-purple-500/10 px-1.5 py-0.5 rounded border border-purple-500/20 font-mono">{{ hoveredGroup.depth }}r</span>
                </div>
              </div>
              
              <div class="grid grid-cols-3 gap-2 pt-2 border-t border-white/5 text-center">
                <div>
                  <div class="text-[7px] font-black text-[var(--color-text-muted)] uppercase tracking-wider">Avg Latency</div>
                  <div class="text-[10px] font-black text-white mt-0.5 font-mono">{{ formatTime(hoveredGroup.avgLatency) }}</div>
                </div>
                <div>
                  <div class="text-[7px] font-black text-[var(--color-text-muted)] uppercase tracking-wider">Avg TPS</div>
                  <div class="text-[10px] font-black text-emerald-400 mt-0.5 font-mono">{{ hoveredGroup.avgTps.toFixed(1) }}</div>
                </div>
                <div>
                  <div class="text-[7px] font-black text-[var(--color-text-muted)] uppercase tracking-wider">Spread</div>
                  <div class="text-[8px] font-black text-amber-500 mt-0.5 font-mono">{{ formatTime(hoveredGroup.minLatency) }} - {{ formatTime(hoveredGroup.maxLatency) }}</div>
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- Leaderboard / Details Area -->
        <div class="lg:col-span-2 space-y-4">
          <div>
            <h3 class="text-xs font-black uppercase tracking-widest text-[var(--color-text-muted)] mb-1">Configuration Benchmark Leaderboard</h3>
            <p class="text-[10px] text-[var(--color-text-muted)] leading-relaxed">
              Comparison of unique model combinations sorted by popularity (number of shootout runs).
            </p>
          </div>

          <div class="space-y-3 max-h-[220px] overflow-y-auto pr-2 custom-scrollbar">
            <div 
              v-for="stat in shootoutStats" 
              :key="stat.key"
              class="flex flex-col p-3 rounded-xl bg-white/5 border border-white/5 hover:border-white/10 transition-colors"
            >
              <!-- Configuration Labels -->
              <div class="flex items-center justify-between gap-2 mb-2">
                <div class="flex items-center gap-2 flex-wrap">
                  <span class="text-[8px] font-black text-amber-500/80 bg-amber-500/5 px-1.5 py-0.5 rounded border border-amber-500/10 font-mono">{{ stat.quick_model }}</span>
                  <span class="text-[8px] font-black text-blue-400/80 bg-blue-400/5 px-1.5 py-0.5 rounded border border-blue-400/10 font-mono">{{ stat.deep_model }}</span>
                  <span class="text-[8px] font-black text-purple-400/80 bg-purple-500/5 px-1.5 py-0.5 rounded border border-purple-500/10 font-mono">{{ stat.depth }}r</span>
                </div>
                <div class="flex items-center gap-1.5">
                  <div class="w-2 h-2 rounded-full" :style="{ backgroundColor: stat.color }"></div>
                  <span class="text-[8px] font-black text-[var(--color-text-muted)] uppercase tracking-wider font-mono">{{ stat.count }} runs</span>
                </div>
              </div>

              <!-- Metrics Row -->
              <div class="grid grid-cols-3 gap-2 text-center">
                <div class="bg-black/10 rounded-lg p-1.5 border border-white/5">
                  <div class="text-[7px] font-black text-[var(--color-text-muted)] uppercase tracking-wider">Avg Latency</div>
                  <div class="text-[10px] font-black text-white mt-0.5">{{ formatTime(stat.avgLatency) }}</div>
                </div>
                <div class="bg-black/10 rounded-lg p-1.5 border border-white/5">
                  <div class="text-[7px] font-black text-[var(--color-text-muted)] uppercase tracking-wider">Avg TPS</div>
                  <div class="text-[10px] font-black text-emerald-400 mt-0.5">{{ stat.avgTps.toFixed(1) }}</div>
                </div>
                <div class="bg-black/10 rounded-lg p-1.5 border border-white/5">
                  <div class="text-[7px] font-black text-[var(--color-text-muted)] uppercase tracking-wider">Spread</div>
                  <div class="text-[9px] font-black text-amber-500/80 mt-0.5">{{ formatTime(stat.minLatency) }} - {{ formatTime(stat.maxLatency) }}</div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Metrics Table Section (Collapsable) -->
    <div class="bg-[var(--color-bg-card)] border border-[var(--color-border-default)] rounded-2xl overflow-hidden shadow-2xl">
      <div 
        @click="isTableCollapsed = !isTableCollapsed" 
        class="flex items-center justify-between p-5 border-b border-[var(--color-border-default)] bg-[var(--color-bg-elevated)]/20 cursor-pointer select-none hover:bg-[var(--color-bg-elevated)]/30 transition-colors"
      >
        <div class="flex items-center gap-2.5">
          <BarChart3 :size="18" class="text-amber-500" />
          <h2 class="text-sm font-bold uppercase tracking-wider">Historical Shootout Table</h2>
          <span class="text-[9px] font-black text-[var(--color-text-muted)] bg-white/5 border border-white/5 px-2 py-0.5 rounded font-mono">{{ filteredMetrics.length }} runs listed</span>
        </div>
        <div class="flex items-center gap-2">
          <span class="text-[10px] text-[var(--color-text-muted)] font-black uppercase tracking-widest">{{ isTableCollapsed ? 'Expand' : 'Collapse' }}</span>
          <ArrowDown :size="14" class="transition-transform duration-300" :class="{ '-rotate-180': !isTableCollapsed }" />
        </div>
      </div>

      <div v-show="!isTableCollapsed" class="overflow-x-auto">
        <table class="w-full text-sm text-left border-collapse">
          <thead>
            <tr class="bg-[var(--color-bg-elevated)]/50 border-b border-[var(--color-border-default)] text-[10px] font-black uppercase tracking-[0.15em] text-[var(--color-text-muted)]">
              <th @click="toggleSort('ticker')" class="px-8 py-5 cursor-pointer select-none hover:text-white transition-colors group">
                <div class="flex items-center gap-1.5">
                  Target
                  <ArrowUpDown v-if="sortKey !== 'ticker'" :size="10" class="opacity-0 group-hover:opacity-40 transition-opacity" />
                  <ArrowUp v-else-if="sortOrder === 'asc'" :size="10" class="text-[var(--color-accent-primary)]" />
                  <ArrowDown v-else :size="10" class="text-[var(--color-accent-primary)]" />
                </div>
              </th>
              <th @click="toggleSort('depth')" class="px-8 py-5 cursor-pointer select-none hover:text-white transition-colors group">
                <div class="flex items-center gap-1.5">
                  Configurations (Depth)
                  <ArrowUpDown v-if="sortKey !== 'depth'" :size="10" class="opacity-0 group-hover:opacity-40 transition-opacity" />
                  <ArrowUp v-else-if="sortOrder === 'asc'" :size="10" class="text-amber-500" />
                  <ArrowDown v-else :size="10" class="text-amber-500" />
                </div>
              </th>
              <th @click="toggleSort('market_sec')" class="px-8 py-5 cursor-pointer select-none hover:text-white transition-colors group">
                <div class="flex items-center gap-1.5">
                  Processing Latency (Analysts)
                  <ArrowUpDown v-if="sortKey !== 'market_sec'" :size="10" class="opacity-0 group-hover:opacity-40 transition-opacity" />
                  <ArrowUp v-else-if="sortOrder === 'asc'" :size="10" class="text-[var(--color-accent-primary)]" />
                  <ArrowDown v-else :size="10" class="text-[var(--color-accent-primary)]" />
                </div>
              </th>
              <th @click="toggleSort('debate_sec')" class="px-8 py-5 cursor-pointer select-none hover:text-white transition-colors group">
                <div class="flex items-center gap-1.5">
                  Reasoning (Debate)
                  <ArrowUpDown v-if="sortKey !== 'debate_sec'" :size="10" class="opacity-0 group-hover:opacity-40 transition-opacity" />
                  <ArrowUp v-else-if="sortOrder === 'asc'" :size="10" class="text-amber-500" />
                  <ArrowDown v-else :size="10" class="text-amber-500" />
                </div>
              </th>
              <th @click="toggleSort('avg_tps')" class="px-8 py-5 cursor-pointer select-none hover:text-white transition-colors group">
                <div class="flex items-center gap-1.5">
                  Throughput
                  <ArrowUpDown v-if="sortKey !== 'avg_tps'" :size="10" class="opacity-0 group-hover:opacity-40 transition-opacity" />
                  <ArrowUp v-else-if="sortOrder === 'asc'" :size="10" class="text-white" />
                  <ArrowDown v-else :size="10" class="text-white" />
                </div>
              </th>
              <th @click="toggleSort('total_sec')" class="px-8 py-5 text-right cursor-pointer select-none hover:text-white transition-colors group">
                <div class="flex items-center justify-end gap-1.5">
                  Total Time
                  <ArrowUpDown v-if="sortKey !== 'total_sec'" :size="10" class="opacity-0 group-hover:opacity-40 transition-opacity" />
                  <ArrowUp v-else-if="sortOrder === 'asc'" :size="10" class="text-[var(--color-accent-primary)]" />
                  <ArrowDown v-else :size="10" class="text-[var(--color-accent-primary)]" />
                </div>
              </th>
            </tr>
          </thead>
          <tbody class="divide-y divide-[var(--color-border-default)]">
            <tr v-if="filteredMetrics.length === 0 && !loading">
              <td colspan="6" class="px-8 py-20 text-center italic text-[var(--color-text-muted)]">
                No research data found. Run an analysis to start collecting benchmarks.
              </td>
            </tr>
            <tr v-for="m in filteredMetrics" :key="m.id" class="hover:bg-[var(--color-bg-elevated)]/30 transition-colors group">
              <td class="px-8 py-5">
                <div class="flex items-center gap-3">
                  <div class="w-8 h-8 rounded-lg bg-[var(--color-accent-primary)]/10 flex items-center justify-center font-black text-[10px] text-[var(--color-accent-primary)]">
                    {{ m.ticker.substring(0,2) }}
                  </div>
                  <div>
                    <div class="font-black text-white tracking-widest uppercase">{{ m.ticker }}</div>
                    <div class="flex flex-col gap-0.5 mt-0.5">
                      <div class="text-[9px] text-[var(--color-text-muted)] font-mono uppercase">{{ m.trade_date }}</div>
                      <div class="text-[8px] text-[var(--color-accent-primary)]/80 bg-[var(--color-accent-primary)]/5 border border-[var(--color-accent-primary)]/10 px-1.5 py-0.5 rounded font-mono w-max">
                        {{ formatRunDate(m.created_at) }}
                      </div>
                    </div>
                  </div>
                </div>
              </td>
              <td class="px-8 py-5">
                <ConfigDisplay
                  :quick-model="m.quick_model"
                  :deep-model="m.deep_model"
                  :depth="m.depth"
                />
              </td>
              <td class="px-8 py-5">
                <div v-if="m.metrics_id !== null && m.metrics_id !== undefined" class="flex items-center gap-4">
                   <div class="flex flex-col">
                      <span class="text-[8px] uppercase font-black opacity-30">MKT</span>
                      <span class="text-[10px] font-bold">{{ formatTime(m.market_sec) }}</span>
                   </div>
                   <div class="flex flex-col border-l border-white/5 pl-4">
                      <span class="text-[8px] uppercase font-black opacity-30">NEWS</span>
                      <span class="text-[10px] font-bold">{{ formatTime(m.news_sec) }}</span>
                   </div>
                   <div class="flex flex-col border-l border-white/5 pl-4">
                      <span class="text-[8px] uppercase font-black opacity-30">SOC</span>
                      <span class="text-[10px] font-bold">{{ formatTime(m.social_sec) }}</span>
                   </div>
                   <div class="flex flex-col border-l border-white/5 pl-4">
                      <span class="text-[8px] uppercase font-black opacity-30">FUND</span>
                      <span class="text-[10px] font-bold">{{ formatTime(m.fund_sec) }}</span>
                   </div>
                </div>
                <div v-else class="text-[var(--color-text-muted)] text-xs font-mono pl-2">
                   —
                </div>
              </td>
              <td class="px-8 py-5">
                <div v-if="m.metrics_id !== null && m.metrics_id !== undefined" class="flex flex-col">
                  <div class="flex items-center gap-2 mb-1">
                    <div class="w-24 h-1.5 bg-white/5 rounded-full overflow-hidden">
                      <div class="h-full bg-amber-500 rounded-full" :style="{ width: Math.min(100, (m.debate_sec / m.total_sec) * 100) + '%' }"></div>
                    </div>
                    <span class="text-[10px] font-bold text-amber-500">{{ formatTime(m.debate_sec) }}</span>
                  </div>
                  <div class="flex justify-between items-center text-[9px] font-black uppercase tracking-widest">
                    <span class="opacity-30 italic">Decision: {{ formatTime(m.decision_sec) }}</span>
                    <span v-if="m.depth" class="bg-amber-500/10 text-amber-500/80 px-1.5 py-0.5 rounded border border-amber-500/10">{{ m.depth }} Rounds</span>
                  </div>
                </div>
                <div v-else class="flex flex-col">
                  <div class="text-[var(--color-text-muted)] text-xs font-mono">
                     —
                  </div>
                  <div class="text-[9px] text-[var(--color-text-muted)] opacity-50 mt-1 uppercase font-bold">
                    {{ m.depth }} Rounds
                  </div>
                </div>
              </td>
              <td class="px-8 py-5">
                <div v-if="m.metrics_id !== null && m.metrics_id !== undefined" class="flex flex-col">
                   <div class="flex items-baseline gap-1">
                      <span class="text-xl font-black text-white">{{ m.avg_tps.toFixed(1) }}</span>
                      <span class="text-[8px] font-black opacity-30 uppercase tracking-widest">tps</span>
                   </div>
                   <div class="text-[9px] font-bold text-[var(--color-text-muted)] tracking-widest">
                    {{ (m.input_tokens + m.output_tokens).toLocaleString() }} TOKENS
                   </div>
                </div>
                <div v-else class="text-[var(--color-text-muted)] text-xs font-mono">
                   —
                </div>
              </td>
              <td class="px-8 py-5 text-right">
                <div class="text-2xl font-black text-[var(--color-accent-primary)] italic tracking-tighter">
                  {{ formatTime(m.total_sec) }}
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </div>
</template>

<style scoped>
select option {
  background-color: #1a1f2e !important;
  color: #ffffff !important;
}
.custom-scrollbar::-webkit-scrollbar {
  width: 6px;
}
.custom-scrollbar::-webkit-scrollbar-track {
  background: transparent;
}
.custom-scrollbar::-webkit-scrollbar-thumb {
  background: var(--color-border-default);
  border-radius: 10px;
}
.custom-scrollbar::-webkit-scrollbar-thumb:hover {
  background: var(--color-accent-primary);
}
</style>
