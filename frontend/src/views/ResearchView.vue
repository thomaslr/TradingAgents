<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { fetchMetrics, type AnalysisMetrics } from '../api/client'
import { Beaker, Zap, Cpu, BarChart3, RefreshCw, Layers } from 'lucide-vue-next'

const metrics = ref<AnalysisMetrics[]>([])
const loading = ref(true)
const selectedModel = ref('ALL')

onMounted(async () => {
  await loadMetrics()
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

// Stats
const avgTps = computed(() => {
  if (metrics.value.length === 0) return 0
  const total = metrics.value.reduce((acc, m) => acc + m.avg_tps, 0)
  return total / metrics.value.length
})

const totalTokens = computed(() => {
  return metrics.value.reduce((acc, m) => acc + m.input_tokens + m.output_tokens, 0)
})

const filteredMetrics = computed(() => {
  if (selectedModel.value === 'ALL') return metrics.value
  return metrics.value.filter(m => m.quick_model === selectedModel.value || m.deep_model === selectedModel.value)
})

const uniqueModels = computed(() => {
  const models = new Set<string>()
  metrics.value.forEach(m => {
    models.add(m.quick_model)
    models.add(m.deep_model)
  })
  return Array.from(models).sort()
})

function formatTime(sec: number) {
  if (sec < 60) return `${sec.toFixed(1)}s`
  const m = Math.floor(sec / 60)
  const s = Math.round(sec % 60)
  return `${m}m ${s}s`
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
    <div class="grid grid-cols-1 md:grid-cols-3 gap-8 mb-12">
      <div class="bg-[var(--color-bg-card)] border border-[var(--color-border-default)] rounded-2xl p-8 shadow-xl relative overflow-hidden group">
        <Zap class="absolute -right-4 -bottom-4 opacity-5 group-hover:scale-125 transition-transform duration-500" :size="120" />
        <p class="text-xs font-black text-[var(--color-text-muted)] uppercase tracking-widest mb-2">Average Throughput</p>
        <h3 class="text-5xl font-black tracking-tighter flex items-end gap-2">
          {{ avgTps.toFixed(1) }}
          <span class="text-xl text-[var(--color-text-muted)] mb-2 uppercase font-black tracking-widest">tps</span>
        </h3>
      </div>
      
      <div class="bg-[var(--color-bg-card)] border border-[var(--color-border-default)] rounded-2xl p-8 shadow-xl relative overflow-hidden group">
        <Cpu class="absolute -right-4 -bottom-4 opacity-5 group-hover:scale-125 transition-transform duration-500" :size="120" />
        <p class="text-xs font-black text-[var(--color-text-muted)] uppercase tracking-widest mb-2">Total Intelligence Processed</p>
        <h3 class="text-5xl font-black tracking-tighter flex items-end gap-2">
          {{ (totalTokens / 1000).toFixed(1) }}k
          <span class="text-xl text-[var(--color-text-muted)] mb-2 uppercase font-black tracking-widest">tokens</span>
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
    </div>

    <!-- Filters -->
    <div class="flex items-center gap-4 mb-8">
      <div class="flex items-center gap-3 px-4 py-2 bg-[var(--color-bg-card)] border border-[var(--color-border-default)] rounded-xl">
        <Layers :size="16" class="opacity-40" />
        <select v-model="selectedModel" class="bg-transparent border-none text-xs font-black uppercase tracking-widest focus:outline-none">
          <option value="ALL">All Models</option>
          <option v-for="m in uniqueModels" :key="m" :value="m">{{ m }}</option>
        </select>
      </div>
    </div>

    <!-- Metrics Table -->
    <div class="bg-[var(--color-bg-card)] border border-[var(--color-border-default)] rounded-2xl overflow-hidden shadow-2xl">
      <div class="overflow-x-auto">
        <table class="w-full text-sm text-left border-collapse">
          <thead>
            <tr class="bg-[var(--color-bg-elevated)]/50 border-b border-[var(--color-border-default)] text-[10px] font-black uppercase tracking-[0.2em] text-[var(--color-text-muted)]">
              <th class="px-8 py-5">Target</th>
              <th class="px-8 py-5">Configurations</th>
              <th class="px-8 py-5">Processing Latency (Analysts)</th>
              <th class="px-8 py-5">Reasoning (Debate)</th>
              <th class="px-8 py-5">Throughput</th>
              <th class="px-8 py-5 text-right">Total Time</th>
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
                    <div class="text-[9px] text-[var(--color-text-muted)] font-mono uppercase">{{ m.trade_date }}</div>
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
                <div class="flex items-center gap-4">
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
              </td>
              <td class="px-8 py-5">
                <div class="flex flex-col">
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
              </td>
              <td class="px-8 py-5">
                <div class="flex flex-col">
                   <div class="flex items-baseline gap-1">
                      <span class="text-xl font-black text-white">{{ m.avg_tps.toFixed(1) }}</span>
                      <span class="text-[8px] font-black opacity-30 uppercase tracking-widest">tps</span>
                   </div>
                   <div class="text-[9px] font-bold text-[var(--color-text-muted)] tracking-widest">
                    {{ (m.input_tokens + m.output_tokens).toLocaleString() }} TOKENS
                   </div>
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
