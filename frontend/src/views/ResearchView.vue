<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { fetchMetrics, fetchCacheStats, clearAnalystCache, type AnalysisMetrics, type CacheStats } from '../api/client'
import { Beaker, Zap, Cpu, BarChart3, RefreshCw, Layers, ArrowUpDown, ArrowUp, ArrowDown } from 'lucide-vue-next'

const metrics = ref<AnalysisMetrics[]>([])
const loading = ref(true)
const selectedQuickModel = ref('ALL')
const selectedDeepModel = ref('ALL')

const sortKey = ref<string>('created_at')
const sortOrder = ref<'asc' | 'desc'>('desc')

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
    loadCacheStats()
  ])
})

async function loadMetrics() {
  loading.value = true
  try {
    metrics.value = await fetchMetrics(500)
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
  let result = metrics.value

  // Apply Quick Model Filter
  if (selectedQuickModel.value !== 'ALL') {
    result = result.filter(m => m.quick_model === selectedQuickModel.value)
  }

  // Apply Deep Model Filter
  if (selectedDeepModel.value !== 'ALL') {
    result = result.filter(m => m.deep_model === selectedDeepModel.value)
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

const uniqueQuickModels = computed(() => {
  const models = new Set<string>()
  metrics.value.forEach(m => {
    if (m.quick_model) models.add(m.quick_model)
  })
  return Array.from(models).sort()
})

const uniqueDeepModels = computed(() => {
  const models = new Set<string>()
  metrics.value.forEach(m => {
    if (m.deep_model) models.add(m.deep_model)
  })
  return Array.from(models).sort()
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

    <!-- Filters -->
    <div class="flex flex-wrap items-center gap-4 mb-8">
      <!-- Quick Model Filter -->
      <div class="flex items-center gap-3 px-4 py-2 bg-[var(--color-bg-card)] border border-[var(--color-border-default)] rounded-xl shadow-md hover:border-white/20 transition-colors">
        <Layers :size="16" class="opacity-40 text-[var(--color-accent-primary)]" />
        <span class="text-[9px] font-black uppercase tracking-widest text-[var(--color-text-muted)] border-r border-white/10 pr-2">Quick</span>
        <select v-model="selectedQuickModel" class="bg-transparent border-none text-xs font-black uppercase tracking-widest focus:outline-none cursor-pointer">
          <option value="ALL" class="bg-[#1a1f2e] text-white">All Quick Models</option>
          <option v-for="m in uniqueQuickModels" :key="m" :value="m" class="bg-[#1a1f2e] text-white">{{ m }}</option>
        </select>
      </div>

      <!-- Deep Model Filter -->
      <div class="flex items-center gap-3 px-4 py-2 bg-[var(--color-bg-card)] border border-[var(--color-border-default)] rounded-xl shadow-md hover:border-white/20 transition-colors">
        <Layers :size="16" class="opacity-40 text-blue-400" />
        <span class="text-[9px] font-black uppercase tracking-widest text-[var(--color-text-muted)] border-r border-white/10 pr-2">Deep</span>
        <select v-model="selectedDeepModel" class="bg-transparent border-none text-xs font-black uppercase tracking-widest focus:outline-none cursor-pointer">
          <option value="ALL" class="bg-[#1a1f2e] text-white">All Deep Models</option>
          <option v-for="m in uniqueDeepModels" :key="m" :value="m" class="bg-[#1a1f2e] text-white">{{ m }}</option>
        </select>
      </div>
    </div>

    <!-- Metrics Table -->
    <div class="bg-[var(--color-bg-card)] border border-[var(--color-border-default)] rounded-2xl overflow-hidden shadow-2xl">
      <div class="overflow-x-auto">
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
                <div class="flex flex-col gap-2">
                  <div class="flex items-center gap-2">
                    <span class="text-[8px] font-black uppercase text-amber-500/60 tracking-widest w-12">Quick</span>
                    <span class="text-[10px] font-bold text-white/80 bg-white/5 px-2 py-0.5 rounded border border-white/5">{{ m.quick_model }}</span>
                  </div>
                  <div class="flex items-center gap-2">
                    <span class="text-[8px] font-black uppercase text-blue-500/60 tracking-widest w-12">Deep</span>
                    <span class="text-[10px] font-bold text-white/80 bg-white/5 px-2 py-0.5 rounded border border-white/5">{{ m.deep_model }}</span>
                  </div>
                </div>
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
