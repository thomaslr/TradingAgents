<script setup lang="ts">
import { ref, onMounted, onUnmounted, watch } from 'vue'
import { 
  fetchSchedules, 
  addSchedule, 
  deleteSchedule, 
  startAnalysis, 
  stopAnalysis,
  fetchAnalysisStatus,
  fetchConfig, 
  fetchOllamaModels,
  type ScheduleJob 
} from '../api/client'
import { Play, Square, Clock, Trash2, CheckCircle, RefreshCw, AlertCircle } from 'lucide-vue-next'

interface QueuedJob {
  id: string
  tickers: string[]
  dateFrom: string
  dateTo: string
  provider: string
  quickModel: string
  deepModel: string
  depth: number
  force: boolean
}

const schedules = ref<ScheduleJob[]>([])
const researchQueue = ref<QueuedJob[]>(JSON.parse(localStorage.getItem('trading_queue') || '[]'))
const isQueueRunning = ref(localStorage.getItem('trading_queue_running') === 'true')
const ollamaModels = ref<string[]>([])
const loading = ref(false)
const fetchingModels = ref(false)
const isStopping = ref(false)
const error = ref('')
const successMessage = ref('')
const isRunning = ref(false)
const currentJobParams = ref<string>('')
const activeConfig = ref<any>(null)
let statusPolling: any = null

// Form State
const tickersInput = ref(localStorage.getItem('trading_tickers') || '')
const provider = ref(localStorage.getItem('trading_provider') || 'openai')
const quickModel = ref(localStorage.getItem('trading_quick_model') || '')
const deepModel = ref(localStorage.getItem('trading_deep_model') || '')
const executionType = ref<'now' | 'schedule'>((localStorage.getItem('trading_execution') as any) || 'now')
const intervalMinutes = ref(Number(localStorage.getItem('trading_interval')) || 1440)

// Expanded Options
const dateFrom = ref(localStorage.getItem('trading_from') || '')
const dateTo = ref(localStorage.getItem('trading_to') || '')
const force = ref(localStorage.getItem('trading_force') === 'true')
const depth = ref(Number(localStorage.getItem('trading_depth')) || 1)

// Persist Form State to localStorage
watch(tickersInput, (v) => localStorage.setItem('trading_tickers', v))
watch(provider, (v) => localStorage.setItem('trading_provider', v))
watch(quickModel, (v) => localStorage.setItem('trading_quick_model', v))
watch(deepModel, (v) => localStorage.setItem('trading_deep_model', v))
watch(executionType, (v) => localStorage.setItem('trading_execution', v))
watch(intervalMinutes, (v) => localStorage.setItem('trading_interval', String(v)))
watch(dateFrom, (v) => localStorage.setItem('trading_from', v))
watch(dateTo, (v) => localStorage.setItem('trading_to', v))
watch(force, (v) => localStorage.setItem('trading_force', String(v)))
watch(depth, (v) => localStorage.setItem('trading_depth', String(v)))
watch(researchQueue, (v) => localStorage.setItem('trading_queue', JSON.stringify(v)), { deep: true })
watch(isQueueRunning, (v) => localStorage.setItem('trading_queue_running', String(v)))

onMounted(async () => {
  await loadDefaultConfig()
  loadSchedules()
  checkStatus()
  // Start polling for status
  statusPolling = setInterval(checkStatus, 3000)
})

onUnmounted(() => {
  if (statusPolling) clearInterval(statusPolling)
})

async function checkStatus() {
  try {
    const status = await fetchAnalysisStatus()
    isRunning.value = status.running
    if (status.running && status.job) {
      activeConfig.value = status.job.config
      const tickers = status.job.tickers.join(', ')
      const current = status.job.current_ticker 
        ? `Analyzing: ${status.job.current_ticker} (${status.job.current_date})` 
        : `Initializing...`
        
      currentJobParams.value = `${current} | Batch: ${tickers}`
      successMessage.value = `Analysis in progress...`
    } else {
      activeConfig.value = null
      if (isRunning.value === false && isStopping.value === true) {
        isStopping.value = false
        successMessage.value = 'Analysis stopped.'
        isQueueRunning.value = false // Stop queue if manually stopped
      }
      
      // Auto-advance queue if active
      if (!status.running && isQueueRunning.value && researchQueue.value.length > 0) {
        runNextInQueue()
      } else if (!status.running && isQueueRunning.value && researchQueue.value.length === 0) {
        isQueueRunning.value = false
        successMessage.value = 'Research Stack Complete.'
      } else if (!status.running && successMessage.value.includes('in progress')) {
        successMessage.value = 'Analysis complete.'
      }
    }
  } catch (e) {
    console.error('Failed to fetch status:', e)
  }
}

// Watch for provider change to fetch Ollama models
watch(provider, (newProvider) => {
  if (newProvider === 'ollama') {
    loadOllamaModels()
  }
})

async function loadDefaultConfig() {
  try {
    const config = await fetchConfig()
    if (config.llm_provider) provider.value = config.llm_provider
    if (config.quick_think_llm) quickModel.value = config.quick_think_llm
    if (config.deep_think_llm) deepModel.value = config.deep_think_llm
    
    // If provider was ollama in .env, fetch models now
    if (provider.value === 'ollama') {
      loadOllamaModels()
    }
  } catch (e: any) {
    console.error('Failed to load default config:', e)
  }
}

async function loadOllamaModels() {
  fetchingModels.value = true
  try {
    const models = await fetchOllamaModels()
    ollamaModels.value = models
  } catch (e: any) {
    console.error('Failed to fetch Ollama models:', e)
  } finally {
    fetchingModels.value = false
  }
}

async function loadSchedules() {
  loading.value = true
  try {
    schedules.value = await fetchSchedules()
  } catch (e: any) {
    console.error(e)
  } finally {
    loading.value = false
  }
}

async function handleStop() {
  isStopping.value = true
  try {
    await stopAnalysis()
    successMessage.value = 'Stopping... (Finishing current agent thought)'
  } catch (e: any) {
    error.value = e.message || 'Failed to stop analysis'
    isStopping.value = false
  }
}

async function handleSubmit() {
  if (!tickersInput.value.trim()) {
    error.value = 'Please enter at least one ticker'
    return
  }
  
  error.value = ''
  successMessage.value = ''
  loading.value = true
  
  const tickers = tickersInput.value.split(',').map(t => t.trim().toUpperCase()).filter(t => t)
  const config = {
    llm_provider: provider.value,
    quick_think_llm: quickModel.value,
    deep_think_llm: deepModel.value,
    max_debate_rounds: depth.value
  }

  try {
    if (executionType.value === 'now') {
      let dates: string[] = []
      if (dateFrom.value && dateTo.value) {
        dates = [dateFrom.value]
        if (dateTo.value !== dateFrom.value) {
            dates = [dateFrom.value, dateTo.value]
        }
      } else {
        dates = [new Date().toISOString().split('T')[0]]
      }

      await startAnalysis({
        tickers,
        dates,
        force: force.value,
        skip_completed: !force.value,
        llm_provider: config.llm_provider,
        quick_think_llm: config.quick_think_llm,
        deep_think_llm: config.deep_think_llm,
        max_debate_rounds: config.max_debate_rounds
      })
      const dateMsg = dates.length > 1 ? `${dates[0]} to ${dates[dates.length-1]}` : dates[0]
      currentJobParams.value = `Tickers: ${tickers.join(', ')} | Dates: ${dateMsg} | Depth: ${depth.value}`
      successMessage.value = `Analysis started.`
      isRunning.value = true
    } else {
      await addSchedule(tickers, config, intervalMinutes.value)
      successMessage.value = `Scheduled analysis created.`
      await loadSchedules()
    }
  } catch (e: any) {
    error.value = e.message || 'Failed to submit'
  } finally {
    loading.value = false
  }
}

function addToQueue() {
  if (!tickersInput.value.trim()) {
    error.value = 'Please enter at least one ticker'
    return
  }
  
  const tickers = tickersInput.value.split(',').map(t => t.trim().toUpperCase()).filter(t => t)
  researchQueue.value.push({
    id: Math.random().toString(36).substring(7),
    tickers,
    dateFrom: dateFrom.value,
    dateTo: dateTo.value,
    provider: provider.value,
    quickModel: quickModel.value,
    deepModel: deepModel.value,
    depth: depth.value,
    force: force.value
  })
  successMessage.value = 'Run added to Research Queue.'
  error.value = ''
}

function removeFromQueue(index: number) {
  researchQueue.value.splice(index, 1)
}

async function runQueue() {
  if (researchQueue.value.length === 0) return
  isQueueRunning.value = true
  await runNextInQueue()
}

async function runNextInQueue() {
  if (researchQueue.value.length === 0) {
    isQueueRunning.value = false
    return
  }
  
  const job = researchQueue.value[0]
  loading.value = true
  
  try {
    let dates: string[] = []
    if (job.dateFrom && job.dateTo) {
      dates = [job.dateFrom, job.dateTo]
    } else {
      dates = [new Date().toISOString().split('T')[0]]
    }

    await startAnalysis({
      tickers: job.tickers,
      dates,
      force: job.force,
      skip_completed: !job.force,
      llm_provider: job.provider,
      quick_think_llm: job.quickModel,
      deep_think_llm: job.deepModel,
      max_debate_rounds: job.depth
    })
    
    // Remove from queue AFTER starting successfully
    researchQueue.value.shift()
    isRunning.value = true
  } catch (e: any) {
    error.value = `Queue Error: ${e.message}`
    isQueueRunning.value = false
  } finally {
    loading.value = false
  }
}

function sweepDepth() {
  if (!tickersInput.value.trim()) {
    error.value = 'Please enter a ticker first'
    return
  }
  const tickers = tickersInput.value.split(',').map(t => t.trim().toUpperCase()).filter(t => t)
  for (let i = 1; i <= 5; i++) {
    researchQueue.value.push({
      id: Math.random().toString(36).substring(7),
      tickers,
      dateFrom: dateFrom.value,
      dateTo: dateTo.value,
      provider: provider.value,
      quickModel: quickModel.value,
      deepModel: deepModel.value,
      depth: i,
      force: force.value
    })
  }
  successMessage.value = 'Created depth sweep (1-5) in queue.'
}

async function handleDeleteSchedule(id: string) {
  if (!confirm('Are you sure you want to delete this schedule?')) return
  try {
    await deleteSchedule(id)
    await loadSchedules()
  } catch (e: any) {
    alert(e.message || 'Failed to delete schedule')
  }
}

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

function formatDate(dateStr: string | null): string {
  if (!dateStr) return '—'
  const d = new Date(dateStr)
  return d.toLocaleString()
}
</script>

<template>
  <div class="p-4 md:p-8 max-w-5xl mx-auto space-y-8 text-[var(--color-text-primary)]">
    <div>
      <h1 class="text-2xl md:text-3xl font-bold">New Analysis</h1>
      <p class="text-sm text-[var(--color-text-muted)] mt-1">Configure and run or schedule analysis jobs</p>
    </div>

    <!-- Feedback messages -->
    <div v-if="error" class="p-4 bg-[var(--color-signal-sell)] bg-opacity-10 border border-[var(--color-signal-sell)] border-opacity-30 rounded-lg text-[var(--color-signal-sell)] flex items-center gap-2 shadow-lg">
      <AlertCircle :size="20" />
      {{ error }}
    </div>

    <!-- Enhanced Status Bar -->
    <div v-if="successMessage" 
      class="relative overflow-hidden flex items-center gap-4 p-5 rounded-xl border border-opacity-20 transition-all duration-500 shadow-2xl"
      :class="isRunning ? 'bg-[var(--color-signal-buy)] bg-opacity-5 border-[var(--color-signal-buy)]' : 'bg-blue-500 bg-opacity-5 border-blue-500'"
    >
      <!-- Animated Scanning Overlay -->
      <div v-if="isRunning" class="absolute inset-0 bg-gradient-to-r from-transparent via-[var(--color-signal-buy)] to-transparent opacity-5 scan-anim"></div>
      
      <div class="z-10 flex items-center justify-center w-12 h-12 rounded-full bg-opacity-10" :class="isRunning ? 'bg-[var(--color-signal-buy)] text-[var(--color-signal-buy)]' : 'bg-blue-500 text-blue-400'">
        <RefreshCw v-if="isRunning" :size="24" class="animate-spin" />
        <CheckCircle v-else :size="24" />
      </div>

      <div class="flex-1 z-10">
        <div class="flex items-center justify-between mb-1">
          <span class="font-black text-xs uppercase tracking-[0.2em]" :class="isRunning ? 'text-[var(--color-signal-buy)]' : 'text-blue-400'">
            {{ isRunning ? 'SYSTEM ACTIVE' : 'SYSTEM STATUS' }}
          </span>
          <span v-if="isRunning" class="text-[10px] font-mono opacity-50">RESEARCH RUN IN PROGRESS</span>
        </div>
        <div class="text-white font-bold text-lg mb-1">{{ successMessage }}</div>
        
        <div v-if="isRunning" class="flex flex-wrap gap-2 mt-2">
          <div class="text-white text-[10px] font-black opacity-80 bg-black bg-opacity-30 px-3 py-1.5 rounded-md flex items-center gap-2">
            <span class="opacity-40">TARGET</span>
            {{ currentJobParams }}
          </div>
          <div v-if="activeConfig" class="text-white text-[10px] font-black opacity-80 bg-[var(--color-accent-primary)] bg-opacity-20 px-3 py-1.5 rounded-md flex items-center gap-2 border border-[var(--color-accent-primary)]/20">
            <span class="opacity-40 text-white">MODEL</span>
            {{ activeConfig.deep_model }}
          </div>
          <div v-if="activeConfig" class="text-white text-[10px] font-black opacity-80 bg-[var(--color-accent-primary)] bg-opacity-20 px-3 py-1.5 rounded-md flex items-center gap-2 border border-[var(--color-accent-primary)]/20">
            <span class="opacity-40 text-white">DEBATE DEPTH</span>
            {{ activeConfig.debate_depth }}
          </div>
        </div>
      </div>
      
      <div v-if="isQueueRunning" class="z-10 px-4 py-2 bg-black/40 rounded-lg border border-white/10 flex flex-col items-center">
        <span class="text-[8px] font-black opacity-40 uppercase">Queue</span>
        <span class="text-xs font-black text-[var(--color-accent-primary)]">{{ researchQueue.length }} LEFT</span>
      </div>
    </div>

    <div class="grid grid-cols-1 lg:grid-cols-12 gap-8 items-start">
      <!-- Left Column: Config -->
      <div class="lg:col-span-7 space-y-8">
        <!-- Configuration Form -->
        <div class="bg-[var(--color-bg-card)] border border-[var(--color-border-default)] rounded-2xl p-8 shadow-2xl relative overflow-hidden h-full">
          <!-- Decorative background glow -->
          <div class="absolute -top-24 -right-24 w-48 h-48 bg-[var(--color-accent-primary)] opacity-5 blur-[100px] rounded-full"></div>
          
          <form @submit.prevent="handleSubmit" class="space-y-8 relative z-10">
            
            <!-- Tickers -->
            <div class="space-y-3">
              <label class="flex items-center gap-2 text-sm font-bold uppercase tracking-wider text-[var(--color-text-secondary)]">
                <Play :size="16" class="text-[var(--color-accent-primary)]" />
                Target Tickers
              </label>
              <input 
                v-model="tickersInput"
                type="text" 
                placeholder="e.g. AAPL, MSFT, TSLA" 
                class="w-full px-6 py-4 bg-[var(--color-bg-elevated)] border border-[var(--color-border-default)] rounded-xl focus:outline-none focus:border-[var(--color-accent-primary)] focus:ring-2 focus:ring-[var(--color-accent-primary)]/20 transition-all text-xl font-mono"
                required
                :disabled="isRunning"
              />
            </div>

            <!-- Models -->
            <div class="grid grid-cols-1 md:grid-cols-3 gap-6">
              <div class="space-y-3">
                <label class="text-xs font-bold uppercase tracking-wider text-[var(--color-text-secondary)]">Provider</label>
                <select v-model="provider" :disabled="isRunning" class="w-full px-4 py-3 bg-[var(--color-bg-elevated)] border border-[var(--color-border-default)] rounded-xl focus:outline-none focus:border-[var(--color-accent-primary)] transition-all">
                  <option value="openai">OpenAI</option>
                  <option value="anthropic">Anthropic</option>
                  <option value="google">Google</option>
                  <option value="ollama">Ollama</option>
                </select>
              </div>
              
              <div class="space-y-3">
                <label class="text-xs font-bold uppercase tracking-wider text-[var(--color-text-secondary)]">Quick Model</label>
                <div v-if="provider === 'ollama'" class="relative">
                  <select v-model="quickModel" :disabled="isRunning" class="w-full px-4 py-3 bg-[var(--color-bg-elevated)] border border-[var(--color-border-default)] rounded-xl focus:outline-none focus:border-[var(--color-accent-primary)] appearance-none transition-all">
                    <option v-for="m in ollamaModels" :key="m" :value="m">{{ m }}</option>
                    <option v-if="ollamaModels.length === 0" disabled>No models found</option>
                  </select>
                  <div v-if="fetchingModels" class="absolute right-3 top-3">
                    <RefreshCw :size="18" class="animate-spin text-[var(--color-text-muted)]" />
                  </div>
                </div>
                <input v-else v-model="quickModel" :disabled="isRunning" type="text" class="w-full px-4 py-3 bg-[var(--color-bg-elevated)] border border-[var(--color-border-default)] rounded-xl focus:outline-none focus:border-[var(--color-accent-primary)]" />
              </div>

              <div class="space-y-3">
                <label class="text-xs font-bold uppercase tracking-wider text-[var(--color-text-secondary)]">Deep Model</label>
                <div v-if="provider === 'ollama'" class="relative">
                  <select v-model="deepModel" :disabled="isRunning" class="w-full px-4 py-3 bg-[var(--color-bg-elevated)] border border-[var(--color-border-default)] rounded-xl focus:outline-none focus:border-[var(--color-accent-primary)] appearance-none transition-all">
                    <option v-for="m in ollamaModels" :key="m" :value="m">{{ m }}</option>
                    <option v-if="ollamaModels.length === 0" disabled>No models found</option>
                  </select>
                  <div v-if="fetchingModels" class="absolute right-3 top-3">
                    <RefreshCw :size="18" class="animate-spin text-[var(--color-text-muted)]" />
                  </div>
                </div>
                <input v-else v-model="deepModel" :disabled="isRunning" type="text" class="w-full px-4 py-3 bg-[var(--color-bg-elevated)] border border-[var(--color-border-default)] rounded-xl focus:outline-none focus:border-[var(--color-accent-primary)]" />
              </div>
            </div>

            <!-- Advanced Options -->
            <div class="flex flex-col gap-10 pt-6 border-t border-[var(--color-border-default)]">
              <div v-if="executionType === 'now'" class="space-y-4">
                <label class="text-xs font-bold uppercase tracking-wider text-[var(--color-text-secondary)]">Analysis Timeframe</label>
                <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
                  <div class="space-y-2">
                    <span class="text-[10px] uppercase font-black opacity-40">Start Date</span>
                    <input v-model="dateFrom" @blur="dateFrom = padDate(dateFrom)" :disabled="isRunning" type="text" placeholder="YYYY-MM-DD" class="w-full px-4 py-3 bg-[var(--color-bg-elevated)] border border-[var(--color-border-default)] rounded-xl focus:outline-none focus:border-[var(--color-accent-primary)]" />
                  </div>
                  <div class="space-y-2">
                    <span class="text-[10px] uppercase font-black opacity-40">End Date</span>
                    <input v-model="dateTo" @blur="dateTo = padDate(dateTo)" :disabled="isRunning" type="text" placeholder="YYYY-MM-DD" class="w-full px-4 py-3 bg-[var(--color-bg-elevated)] border border-[var(--color-border-default)] rounded-xl focus:outline-none focus:border-[var(--color-accent-primary)]" />
                  </div>
                </div>
              </div>

              <div class="space-y-3">
                <label class="text-xs font-bold uppercase tracking-wider text-[var(--color-text-secondary)]">Debate Depth</label>
                <div class="flex items-center gap-6">
                  <input v-model.number="depth" :disabled="isRunning" type="range" min="1" max="5" class="flex-1 accent-[var(--color-accent-primary)]" />
                  <span class="w-10 h-10 flex items-center justify-center bg-[var(--color-bg-elevated)] rounded-lg font-bold border border-[var(--color-border-default)] text-lg">{{ depth }}</span>
                </div>
                <p class="text-[10px] text-[var(--color-text-muted)] italic">Higher depth increases reasoning rounds between Bull and Bear agents.</p>
              </div>
            </div>

            <!-- Execution Type -->
            <div class="pt-6 border-t border-[var(--color-border-default)]">
              <div class="flex flex-col md:flex-row justify-between gap-4">
                <div class="space-y-4">
                  <label class="text-xs font-bold uppercase tracking-wider text-[var(--color-text-secondary)] mb-4 block">Execution Strategy</label>
                  <div class="flex gap-8">
                    <label class="flex items-center gap-3 cursor-pointer group">
                      <input type="radio" v-model="executionType" value="now" :disabled="isRunning" class="w-5 h-5 accent-[var(--color-accent-primary)]" />
                      <div class="flex flex-col">
                        <span class="text-sm font-bold group-hover:text-[var(--color-accent-primary)] transition-colors">Run Once</span>
                      </div>
                    </label>
                    <label class="flex items-center gap-3 cursor-pointer group">
                      <input type="radio" v-model="executionType" value="schedule" :disabled="isRunning" class="w-5 h-5 accent-[var(--color-accent-primary)]" />
                      <div class="flex flex-col">
                        <span class="text-sm font-bold group-hover:text-[var(--color-accent-primary)] transition-colors">Schedule Recurring</span>
                      </div>
                    </label>
                  </div>
                </div>
                
                <div v-if="executionType === 'schedule'" class="animate-in fade-in slide-in-from-top-2">
                  <label class="text-xs font-bold uppercase tracking-wider text-[var(--color-text-secondary)] mb-3 block">Interval</label>
                  <select v-model="intervalMinutes" :disabled="isRunning" class="w-full md:w-48 px-4 py-3 bg-[var(--color-bg-elevated)] border border-[var(--color-border-default)] rounded-xl focus:outline-none focus:border-[var(--color-accent-primary)]">
                    <option :value="60">Hourly</option>
                    <option :value="1440">Daily</option>
                    <option :value="10080">Weekly</option>
                  </select>
                </div>
              </div>
            </div>

            <div class="pt-8 border-t border-[var(--color-border-default)] flex flex-wrap gap-4">
              <button
                v-if="!isRunning"
                type="submit"
                :disabled="loading"
                class="flex items-center justify-center gap-3 px-8 py-4 bg-[var(--color-accent-primary)] hover:bg-[var(--color-accent-hover)] text-white font-black uppercase tracking-widest rounded-xl transition-all transform hover:scale-[1.02] active:scale-[0.98] disabled:opacity-50 shadow-xl shadow-[var(--color-accent-primary)]/40"
              >
                <RefreshCw v-if="loading" :size="20" class="animate-spin" />
                <template v-else-if="executionType === 'now'">
                  <Play :size="20" /> Start Now
                </template>
                <template v-else>
                  <Clock :size="20" /> Save Schedule
                </template>
              </button>

              <button
                v-if="!isRunning && executionType === 'now'"
                type="button"
                @click="addToQueue"
                class="flex items-center justify-center gap-3 px-8 py-4 bg-[var(--color-bg-elevated)] hover:bg-opacity-80 border border-[var(--color-border-default)] text-white font-black uppercase tracking-widest rounded-xl transition-all transform hover:scale-[1.02] active:scale-[0.98]"
              >
                Add to Queue
              </button>

              <button
                v-if="isRunning"
                type="button"
                @click="handleStop"
                :disabled="isStopping"
                class="flex items-center justify-center gap-3 px-12 py-4 bg-[var(--color-signal-sell)] hover:bg-red-600 text-white font-black uppercase tracking-widest rounded-xl transition-all transform hover:scale-[1.02] active:scale-[0.98] disabled:opacity-70 shadow-xl shadow-red-500/40"
              >
                <RefreshCw v-if="isStopping" :size="20" class="animate-spin" />
                <Square v-else :size="20" /> Stop Current
              </button>
            </div>
          </form>
        </div>
      </div>

      <!-- Right Column: Research Queue -->
      <div class="lg:col-span-5 space-y-6">
        <div class="bg-[var(--color-bg-card)] border border-[var(--color-border-default)] rounded-2xl p-6 shadow-2xl relative overflow-hidden flex flex-col h-full min-h-[600px]">
          <div class="flex items-center justify-between mb-6">
            <h2 class="text-xl font-bold flex items-center gap-3">
              <RefreshCw :size="20" class="text-[var(--color-accent-primary)]" :class="{ 'animate-spin': isQueueRunning }" />
              Research Queue
            </h2>
            <div class="flex gap-2">
              <button @click="sweepDepth" :disabled="isRunning || !tickersInput" class="px-2 py-1 bg-black/40 text-[9px] font-black uppercase rounded border border-white/10 hover:bg-black/60 transition-colors">Sweep Depth</button>
              <button v-if="researchQueue.length > 0" @click="researchQueue = []" class="px-2 py-1 text-[9px] font-black uppercase text-[var(--color-signal-sell)] hover:bg-[var(--color-signal-sell)]/10 rounded transition-colors">Clear</button>
            </div>
          </div>

          <div v-if="researchQueue.length === 0" class="flex-1 flex flex-col items-center justify-center text-center p-8 border-2 border-dashed border-[var(--color-border-default)] rounded-xl opacity-40">
            <Clock :size="48" class="mb-4" />
            <p class="text-sm font-bold uppercase tracking-widest">Queue is Empty</p>
            <p class="text-xs mt-2 italic">Add runs with different criteria to test input effects on alpha.</p>
          </div>

          <div v-else class="flex-1 space-y-3 overflow-y-auto max-h-[500px] pr-2 custom-scrollbar">
            <div v-for="(job, index) in researchQueue" :key="job.id" class="p-4 bg-[var(--color-bg-elevated)] border border-[var(--color-border-default)] rounded-xl group relative hover:border-[var(--color-accent-primary)]/50 transition-all">
              <div class="flex justify-between items-start">
                <div class="space-y-1">
                  <div class="flex gap-1">
                    <span v-for="t in job.tickers" :key="t" class="text-[10px] font-black text-[var(--color-accent-primary)]">{{ t }}</span>
                  </div>
                  <div class="text-[10px] opacity-60 font-mono">{{ job.dateFrom || 'Today' }} → {{ job.dateTo || 'Today' }}</div>
                </div>
                <button @click="removeFromQueue(index)" class="opacity-0 group-hover:opacity-100 p-1 hover:text-[var(--color-signal-sell)] transition-all">
                  <Trash2 :size="14" />
                </button>
              </div>
              <div class="mt-3 flex flex-wrap gap-2">
                <span class="px-2 py-0.5 bg-black/40 text-[8px] font-black rounded border border-white/5">{{ job.quickModel }}</span>
                <span class="px-2 py-0.5 bg-black/40 text-[8px] font-black rounded border border-white/5">DEPTH {{ job.depth }}</span>
              </div>
            </div>
          </div>

          <div class="mt-6">
            <button
              @click="runQueue"
              :disabled="isRunning || researchQueue.length === 0"
              class="w-full py-4 bg-white text-black font-black uppercase tracking-widest rounded-xl hover:bg-opacity-90 disabled:opacity-30 transition-all flex items-center justify-center gap-3"
            >
              <Play :size="20" /> Run Research Stack
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- Active Schedules Table -->
    <div class="space-y-6">
      <h2 class="text-xl font-bold flex items-center gap-3">
        <Clock :size="24" class="text-[var(--color-accent-primary)]" />
        Automated Pipelines
      </h2>
      <div class="bg-[var(--color-bg-card)] border border-[var(--color-border-default)] rounded-2xl overflow-hidden shadow-xl">
        <div v-if="schedules.length === 0" class="p-16 text-center text-[var(--color-text-muted)] flex flex-col items-center gap-4">
          <Clock :size="64" class="opacity-10" />
          <p class="font-medium">No automated pipelines found. Configure one above to run analyses while you sleep.</p>
        </div>
        <div v-else class="overflow-x-auto">
          <table class="w-full text-sm">
            <thead>
              <tr class="bg-[var(--color-bg-elevated)]/50 border-b border-[var(--color-border-default)] text-left text-[var(--color-text-muted)] text-[10px] font-black uppercase tracking-[0.2em]">
                <th class="px-8 py-5">Assets</th>
                <th class="px-8 py-5">Recurrence</th>
                <th class="px-8 py-5">Intelligence</th>
                <th class="px-8 py-5">Next Sequence</th>
                <th class="px-8 py-5 text-right">Actions</th>
              </tr>
            </thead>
            <tbody class="divide-y divide-[var(--color-border-default)]">
              <tr v-for="job in schedules" :key="job.id" class="hover:bg-[var(--color-bg-elevated)]/30 transition-colors group">
                <td class="px-8 py-5">
                  <div class="flex flex-wrap gap-1.5">
                    <span v-for="t in job.tickers" :key="t" class="px-3 py-1 bg-[var(--color-bg-elevated)] border border-[var(--color-border-default)] rounded-md text-[10px] font-black text-[var(--color-accent-primary)]">
                      {{ t }}
                    </span>
                  </div>
                </td>
                <td class="px-8 py-5">
                  <span class="inline-flex items-center gap-1.5 px-3 py-1.5 bg-black/20 rounded-full text-[10px] font-bold border border-white/5">
                    <Clock :size="12" class="opacity-50" />
                    {{ job.interval_minutes >= 1440 ? `${job.interval_minutes / 1440} DAY(S)` : `${job.interval_minutes / 60} HOUR(S)` }}
                  </span>
                </td>
                <td class="px-8 py-5">
                  <span class="text-xs font-medium uppercase opacity-70">{{ job.config.llm_provider }}</span>
                </td>
                <td class="px-8 py-5 font-mono text-xs opacity-60">{{ formatDate(job.next_run) }}</td>
                <td class="px-8 py-5 text-right">
                  <button
                    @click="handleDeleteSchedule(job.id)"
                    class="p-2.5 text-[var(--color-text-muted)] hover:text-[var(--color-signal-sell)] rounded-xl hover:bg-[var(--color-signal-sell)]/10 transition-all opacity-0 group-hover:opacity-100"
                    title="Terminate Schedule"
                  >
                    <Trash2 :size="20" />
                  </button>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
/* Custom styling for select to hide default arrow when we provide our own or need custom layout */
select {
  background-image: url("data:image/svg+xml,%3csvg xmlns='http://www.w3.org/2000/svg' fill='none' viewBox='0 0 20 20'%3e%3cpath stroke='%236b7280' stroke-linecap='round' stroke-linejoin='round' stroke-width='1.5' d='M6 8l4 4 4-4'/%3e%3c/svg%3e");
  background-position: right 1rem center;
  background-repeat: no-repeat;
  background-size: 1.5em 1.5em;
  padding-right: 3rem;
}

.scan-anim {
  width: 200%;
  animation: scan 4s linear infinite;
}

@keyframes scan {
  from { transform: translateX(-100%); }
  to { transform: translateX(100%); }
}

input[type="date"]::-webkit-calendar-picker-indicator {
  filter: invert(1);
  opacity: 0.5;
  cursor: pointer;
}
</style>

