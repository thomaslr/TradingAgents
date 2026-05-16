<script setup lang="ts">
import { ref, onMounted, onUnmounted, watch } from 'vue'
import { 
  fetchAnalysisStatus, 
  fetchConfig, 
  fetchOllamaModels,
  fetchResearchQueue,
  addToResearchQueue,
  removeFromResearchQueue,
  reorderResearchQueue,
  startResearchQueue,
  pauseResearchQueue,
  resumeResearchQueue,
  fetchSchedules,
  toggleSchedule,
  deleteSchedule,
  startAnalysis,
  stopAnalysis,
  yieldAnalysis,
  purgeAnalysis,
  addSchedule,
  type ScheduleJob 
} from '../api/client'
import { Play, Pause, Square, Clock, Trash2, CheckCircle, RefreshCw, AlertCircle, GripVertical, Settings2, Zap, ArrowUp, AlertTriangle } from 'lucide-vue-next'

// interface QueuedJob deleted

const schedules = ref<ScheduleJob[]>([])
const researchQueue = ref<any[]>([])
const isQueueRunning = ref(false)
const isQueuePaused = ref(false)
const queueTotal = ref(0)
const queueCurrent = ref(0)
const ollamaModels = ref<string[]>([])
const loading = ref(false)
const dragIndex = ref<number | null>(null)
const fetchingModels = ref(false)
const isStopping = ref(false)
const activeTab = ref<'research' | 'automation'>('research')
const error = ref('')
const successMessage = ref('')
const scheduledTime = ref('09:00')
const isRunning = ref(false)
const currentJobParams = ref<string>('')
const activeConfig = ref<any>(null)
const activeJobMessage = ref<string | null>(null)
const isProcessingQueue = ref(false)
let statusPolling: any = null
const launchWatchdog = ref(0)
const runningJob = ref<any>(null)
const showDeepIntel = ref(false)
const thoughtStreamText = ref('')

const pipelineSteps = [
  'Market Analyst',
  'Social Analyst',
  'News Analyst',
  'Fundamentals Analyst',
  'Debating',
  'Finalizing Decision'
]

// Token Tracking State
const lastInputTokens = ref(0)
const lastOutputTokens = ref(0)
const lastTokenUpdate = ref(Date.now())
const inputTokensPerSec = ref(0)
const outputTokensPerSec = ref(0)

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

onMounted(async () => {
  await loadDefaultConfig()
  loadSchedules()
  loadQueue()
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
    const wasRunning = isRunning.value
    isRunning.value = status.running
    isQueuePaused.value = !!status.is_paused
    
    // Always sync queue if there are changes
    if (status.queue_count !== undefined) {
       loadQueue()
    }

    if (!status.running) {
      // Clear stopping state and show final message if we just finished
      if (isStopping.value) {
        successMessage.value = 'Analysis stopped.'
      } else if (wasRunning) {
        successMessage.value = 'Analysis complete.'
      }
      isStopping.value = false
      isQueueRunning.value = false
      thoughtStreamText.value = ''
    }

    if (status.running && status.job) {
      runningJob.value = status.job
      isProcessingQueue.value = false // We've confirmed it's running
      activeConfig.value = status.job.config
      activeJobMessage.value = status.job.status_message
      const tickers = status.job.tickers.join(', ')
      const current = status.job.current_ticker 
        ? `Analyzing: ${status.job.current_ticker} (${status.job.current_date})` 
        : `Initializing...`
        
      currentJobParams.value = `${current} | Batch: ${tickers}`
      if (!isStopping.value) {
        successMessage.value = `Analysis in progress...`
      }
      
      // If backend has a job ID, we are likely in a queue run
      isQueueRunning.value = !!status.job.id

      // Extract the thought stream text if it contains the tool executing prefix
      const msg = status.job.sub_status || ''
      if (msg.includes('Executing:')) {
        thoughtStreamText.value = msg.substring(msg.indexOf('Executing:'))
      } else if (msg) {
        // Display high-level status as is (e.g., "Debating (Round 1)" or "Market Analyst")
        thoughtStreamText.value = msg
      }

      // Calculate Token Rates (every ~5s)
      const now = Date.now()
      const deltaMs = now - lastTokenUpdate.value
      if (deltaMs >= 5000) {
        const currentIn = status.job.input_tokens || 0
        const currentOut = status.job.output_tokens || 0
        
        // (Current - Last) / (ms / 1000)
        const secFactor = (deltaMs / 1000)
        inputTokensPerSec.value = Math.round((currentIn - lastInputTokens.value) / secFactor)
        outputTokensPerSec.value = Math.round((currentOut - lastOutputTokens.value) / secFactor)
        
        lastInputTokens.value = currentIn
        lastOutputTokens.value = currentOut
        lastTokenUpdate.value = now
      }
    } else {
      activeConfig.value = null
      
      if (!status.running) {
        if (isProcessingQueue.value) {
          launchWatchdog.value++
          if (launchWatchdog.value > 4) { // ~12 seconds
            error.value = status.last_error ? `Launch Failed: ${status.last_error}` : 'Launch Timeout: The backend did not start the job.'
            isProcessingQueue.value = false
            launchWatchdog.value = 0
          }
        } else {
          launchWatchdog.value = 0
        }

        if (status.last_error && isProcessingQueue.value) {
           error.value = `Launch Failed: ${status.last_error}`
           isProcessingQueue.value = false
        }
        
        if (isStopping.value === true) {
          isStopping.value = false
          successMessage.value = 'Analysis stopped.'
          isQueueRunning.value = false
        }
        
        // Auto-advance is now handled by the backend worker.
        // We just watch the status.
        if (successMessage.value.includes('in progress')) {
          successMessage.value = 'Analysis complete.'
        }
      }
    }
  } catch (e) {
    console.error('Failed to fetch status:', e)
  }
}

async function loadQueue() {
  try {
    const queue = await fetchResearchQueue()
    researchQueue.value = queue.map(j => ({
       id: j.id,
       tickers: j.tickers,
       dateFrom: j.dates[0],
       dateTo: j.dates[1],
       provider: j.provider,
       quickModel: j.quick_model,
       deepModel: j.deep_model,
       depth: j.depth,
       force: j.force,
       status: j.status
    }))
  } catch (e) {
    console.error('Failed to load queue:', e)
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

const handleYield = async () => {
  try {
    await yieldAnalysis()
    successMessage.value = "Yield requested. Job will move back to queue after current day."
    checkStatus()
  } catch (error) {
    console.error('Error yielding analysis:', error)
  }
}

const promoteToActive = async (jobId: string) => {
  try {
    // 1. Move this job to the top of the queue
    const otherIds = researchQueue.value.filter(j => j.id !== jobId).map(j => j.id)
    const newOrder = [jobId, ...otherIds]
    await reorderResearchQueue(newOrder)
    
    // 2. If a job is running, yield it
    if (isRunning.value) {
      await yieldAnalysis()
      successMessage.value = "Promoting job. Current analysis will yield after finishing its current day."
    } else {
      // Just signal to start if not running
      await startResearchQueue()
    }
    
    loadQueue()
    checkStatus()
  } catch (error) {
    console.error('Error promoting job:', error)
  }
}

const handleStop = async () => {
  if (isRunning.value) {
    isStopping.value = true
    successMessage.value = "Stopping... (Finishing current agent thought)"
    await stopAnalysis()
  }
}

const handlePurge = async () => {
  if (!confirm("NUCLEAR OPTION: This will stop the analysis, CLEAR the research queue, and WIPE all on-disk checkpoints. Use only if system is stuck. Proceed?")) return
  
  try {
    const res = await purgeAnalysis()
    successMessage.value = res.message
    loadQueue()
    checkStatus()
  } catch (error) {
    console.error('Error purging system:', error)
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
    if (activeTab.value === 'research') {
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
      await addSchedule(tickers, config, intervalMinutes.value, scheduledTime.value)
      successMessage.value = `Automated pipeline created.`
      await loadSchedules()
    }
  } catch (e: any) {
    error.value = e.message || 'Failed to submit'
  } finally {
    loading.value = false
  }
}

async function addToQueue() {
  if (!tickersInput.value.trim()) {
    error.value = 'Please enter at least one ticker'
    return
  }
  
  const tickers = tickersInput.value.split(',').map(t => t.trim().toUpperCase()).filter(t => t)
  const job = {
    id: Math.random().toString(36).substring(7),
    tickers,
    dateFrom: dateFrom.value,
    dateTo: dateTo.value,
    provider: provider.value,
    quickModel: quickModel.value,
    deepModel: deepModel.value,
    depth: depth.value,
    force: force.value
  }
  
  try {
    await addToResearchQueue(job)
    await loadQueue()
    successMessage.value = 'Run added to Research Queue.'
    error.value = ''
  } catch (e: any) {
    error.value = `Failed to add to queue: ${e.message}`
  }
}

async function removeFromQueue(jobId: string) {
  try {
    await removeFromResearchQueue(jobId)
    await loadQueue()
  } catch (e: any) {
    error.value = `Failed to remove: ${e.message}`
  }
}

async function runQueue() {
  try {
    if (isQueuePaused.value) {
      await resumeResearchQueue()
    } else {
      await startResearchQueue()
    }
    successMessage.value = 'Research Stack started.'
    isQueueRunning.value = true
  } catch (e: any) {
    error.value = `Failed to start stack: ${e.message}`
  }
}

async function handlePauseToggle() {
  try {
    if (isQueuePaused.value) {
      await resumeResearchQueue()
      successMessage.value = 'Research Stack resumed.'
    } else {
      await pauseResearchQueue()
      successMessage.value = 'Research Stack paused.'
    }
    // checkStatus will update the local isQueuePaused ref
  } catch (e: any) {
    error.value = `Pause toggle failed: ${e.message}`
  }
}

async function sweepDepth() {
  if (!tickersInput.value.trim()) {
    error.value = 'Please enter a ticker first'
    return
  }
  const tickers = tickersInput.value.split(',').map(t => t.trim().toUpperCase()).filter(t => t)
  for (let i = 1; i <= 5; i++) {
    const job = {
      id: Math.random().toString(36).substring(7),
      tickers,
      dateFrom: dateFrom.value,
      dateTo: dateTo.value,
      provider: provider.value,
      quickModel: quickModel.value,
      deepModel: deepModel.value,
      depth: i,
      force: force.value
    }
    await addToResearchQueue(job)
  }
  await loadQueue()
  successMessage.value = 'Created depth sweep (1-5) in queue.'
}

// ── Drag & Drop ──────────────────────────────────────────

function onDragStart(index: number) {
  dragIndex.value = index
}

function onDragOver(e: DragEvent) {
  e.preventDefault() // Allow drop
}

async function onDrop(index: number) {
  if (dragIndex.value === null) return
  
  const item = researchQueue.value.splice(dragIndex.value, 1)[0]
  researchQueue.value.splice(index, 0, item)
  dragIndex.value = null
  
  // Sync with server
  try {
    const ids = researchQueue.value.map(j => j.id)
    await reorderResearchQueue(ids)
  } catch (e: any) {
    error.value = `Failed to sync order: ${e.message}`
  }
}

// ── Schedules ─────────────────────────────────────────────

async function handleToggleSchedule(id: string) {
  try {
    await toggleSchedule(id)
    await loadSchedules()
    successMessage.value = 'Schedule updated.'
  } catch (e: any) {
    error.value = `Failed to toggle: ${e.message}`
  }
}

async function handleDeleteSchedule(id: string) {
  if (!confirm('Are you sure you want to delete this automated pipeline?')) return
  try {
    await deleteSchedule(id)
    await loadSchedules()
    successMessage.value = 'Schedule deleted.'
  } catch (e: any) {
    error.value = `Failed to delete: ${e.message}`
  }
}

function padDate(val: string): string {
  if (!val) return val
  
  // Safeguard: if user pastes a concatenated string or range (e.g. "2026-01-042026-02-05")
  if (val.length > 10) {
    const match = val.match(/\d{4}-\d{2}-\d{2}/)
    if (match) {
      val = match[0]
    } else {
      return ''
    }
  }

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
      <h1 class="text-3xl font-bold">Run and Schedule Analytics</h1>
    </div>

    <!-- Feedback messages -->
    <div v-if="error" class="p-4 bg-[var(--color-signal-sell)] bg-opacity-10 border border-[var(--color-signal-sell)] border-opacity-30 rounded-lg text-[var(--color-signal-sell)] flex items-center gap-2 shadow-lg">
      <AlertCircle :size="20" />
      {{ error }}
    </div>

    <!-- Enhanced Status Bar -->
    <div v-if="successMessage" 
      class="relative overflow-hidden flex items-center gap-4 p-5 rounded-xl border border-opacity-20 transition-all duration-500 shadow-2xl"
      :class="(isRunning || isQueueRunning) ? 'bg-[var(--color-signal-buy)] bg-opacity-5 border-[var(--color-signal-buy)]' : 'bg-blue-500 bg-opacity-5 border-blue-500'"
    >
      <!-- Animated Scanning Overlay -->
      <div v-if="isRunning || isQueueRunning" class="absolute inset-0 bg-gradient-to-r from-transparent via-[var(--color-signal-buy)] to-transparent opacity-5 scan-anim"></div>
      
      <div class="z-10 flex items-center justify-center w-12 h-12 rounded-full bg-opacity-10" :class="(isRunning || isQueueRunning) ? 'bg-[var(--color-signal-buy)] text-[var(--color-signal-buy)]' : 'bg-blue-500 text-blue-400'">
        <RefreshCw v-if="isRunning || isQueueRunning" :size="24" class="animate-spin" />
        <CheckCircle v-else :size="24" />
      </div>

      <div class="flex-1 z-10">
        <div class="flex items-center justify-between mb-1">
          <span class="font-black text-xs uppercase tracking-[0.2em]" :class="(isRunning || isQueueRunning) ? (isQueuePaused ? 'text-amber-400' : 'text-[var(--color-signal-buy)]') : 'text-blue-400'">
            {{ isQueuePaused ? 'SYSTEM PAUSED' : ((isRunning || isQueueRunning) ? 'SYSTEM ACTIVE' : 'SYSTEM STATUS') }}
          </span>
        </div>
        <div class="flex items-center gap-4 mb-2">
          <div class="text-white font-black text-xl">{{ successMessage }}</div>
          <div v-if="isRunning" class="text-white text-[10px] font-black bg-black/60 px-3 py-1.5 rounded-md flex items-center gap-2 border border-white/10 shadow-lg">
            <span class="text-yellow-400">TARGET</span>
            {{ currentJobParams }}
          </div>
        </div>
        
        <div v-if="isRunning" class="flex flex-col gap-3 mt-2">
          <div class="flex flex-wrap items-center gap-2">
            <div v-if="isQueueRunning && queueTotal > 0" class="text-white text-[10px] font-black bg-black/40 px-3 py-1.5 rounded-md flex items-center gap-2 border border-white/10">
              <span class="text-yellow-400">STACK PROGRESS</span>
              Job {{ queueCurrent }} of {{ queueTotal }}
            </div>
            
            <!-- Metadata Pills (Fallback to form state if backend hasn't reported yet) -->
            <div class="text-white text-[10px] font-black bg-black/40 px-3 py-1.5 rounded-md flex items-center gap-2 border border-white/10">
              <span class="text-yellow-400">ANALYST</span>
              {{ activeConfig?.quick_model || quickModel }}
            </div>
            <div class="text-white text-[10px] font-black bg-black/40 px-3 py-1.5 rounded-md flex items-center gap-2 border border-white/10">
              <span class="text-yellow-400">JUDGE</span>
              {{ activeConfig?.deep_model || deepModel }}
            </div>
            <div class="text-white text-[10px] font-black bg-black/40 px-3 py-1.5 rounded-md flex items-center gap-2 border border-white/10">
              <span class="text-yellow-400">DEPTH</span>
              {{ activeConfig?.debate_depth || depth }}
            </div>

            <!-- Tokens Rate Pill -->
            <div v-if="inputTokensPerSec > 0 || outputTokensPerSec > 0" class="text-white text-[10px] font-black bg-black/40 px-3 py-1.5 rounded-md flex items-center gap-2 border border-white/10">
              <span class="text-yellow-400">THROUGHPUT</span>
              <span class="text-blue-400">{{ inputTokensPerSec }}ᵢ</span> / <span class="text-cyan-400">{{ outputTokensPerSec }}ₒ</span> <small class="text-white/40 ml-1">tps</small>
            </div>
          </div>

          <!-- Deep Intel Toggle (Moved to Left) -->
          <div class="flex">
            <button 
              @click="showDeepIntel = !showDeepIntel"
              type="button"
              class="group flex items-center gap-2 px-4 py-1.5 bg-black/40 hover:bg-black/60 text-white/60 hover:text-white rounded-full transition-all border border-white/5"
            >
              <div :class="showDeepIntel ? 'rotate-180' : ''" class="transition-transform duration-300">
                <Settings2 :size="12" />
              </div>
              <span class="text-[9px] font-black uppercase tracking-widest">{{ showDeepIntel ? 'Hide Deep Intel' : 'Show Deep Intel' }}</span>
            </button>
          </div>
        </div>

        <!-- Network / WOL Status -->
        <div v-if="activeJobMessage" class="w-full mt-3 p-3 bg-amber-500/10 border border-amber-500/20 rounded-xl text-amber-500 text-[10px] font-bold flex items-center gap-3 animate-pulse z-10 shadow-lg">
          <div class="w-2 h-2 rounded-full bg-amber-500"></div>
          <span class="uppercase tracking-widest">{{ activeJobMessage }}</span>
        </div>
      </div>
      
      <div v-if="isRunning || isQueueRunning" class="z-10 flex flex-col items-end gap-3 min-w-[140px]">
        <!-- Queue Status Pill (Only if queue is actually active) -->
        <div v-if="isQueueRunning" class="px-6 py-2 bg-black/80 rounded-xl border border-white/20 flex flex-col items-center shadow-2xl backdrop-blur-md w-full">
          <span class="text-[9px] font-black text-yellow-400 uppercase tracking-tighter opacity-70">QUEUE</span>
          <span class="text-lg font-black text-white leading-tight">{{ researchQueue.length }} LEFT</span>
        </div>

        <!-- Action Buttons (Yield/Stop) -->
        <div class="flex gap-2 w-full justify-end">
          <button 
            v-if="isQueueRunning"
            @click="handleYield"
            class="flex-1 flex items-center justify-center gap-2 px-3 py-2 bg-black/60 hover:bg-black/80 text-yellow-400 border border-yellow-400/30 rounded-lg transition-all font-black text-[10px] uppercase tracking-wider"
            title="Finish current day and move to queue"
          >
            <Clock :size="12" />
            YIELD
          </button>
          <button 
            @click="handleStop"
            class="flex-1 flex items-center justify-center gap-2 px-3 py-2 bg-red-600/60 hover:bg-red-600 text-white border border-red-400/30 rounded-lg transition-all font-black text-[10px] uppercase tracking-wider"
            title="Stop analysis immediately"
          >
            <Square :size="10" fill="currentColor" />
            STOP
          </button>
        </div>

      </div>

      <div v-if="isRunning" class="absolute bottom-4 right-8 opacity-[0.03] pointer-events-none text-[80px] font-black select-none z-0 overflow-hidden whitespace-nowrap uppercase tracking-tighter">
        {{ runningJob?.sub_status || 'RESEARCH' }}
      </div>
    </div>

    <!-- Deep Intel Section (Separate Full-Width Card Below) -->
    <transition
      enter-active-class="transition duration-500 ease-out"
      enter-from-class="transform -translate-y-4 opacity-0"
      enter-to-class="transform translate-y-0 opacity-100"
      leave-active-class="transition duration-300 ease-in"
      leave-from-class="transform translate-y-0 opacity-100"
      leave-to-class="transform -translate-y-4 opacity-0"
    >
      <div v-if="isRunning && showDeepIntel" class="p-8 bg-black/40 backdrop-blur-xl rounded-2xl border border-white/10 shadow-2xl overflow-hidden">
        <div class="flex flex-col gap-8">
          <!-- Pipeline Timeline -->
          <div class="flex justify-between items-start gap-2 relative px-4">
            <div class="absolute top-2.5 left-10 right-10 h-[1px] bg-white/10 z-0"></div>
            
            <div v-for="step in pipelineSteps" :key="step" class="z-10 flex flex-col items-center gap-3 flex-1">
              <div 
                class="w-6 h-6 rounded-full flex items-center justify-center border-2 transition-all duration-700"
                :class="[
                  runningJob?.sub_status?.includes(step) ? 'bg-yellow-400 border-yellow-400 shadow-[0_0_20px_rgba(250,204,21,0.6)] scale-110' : 
                  (pipelineSteps.indexOf(step) < pipelineSteps.findIndex(s => runningJob?.sub_status?.includes(s)) ? 'bg-green-500 border-green-500' : 'bg-black border-white/20')
                ]"
              >
                <CheckCircle v-if="pipelineSteps.indexOf(step) < pipelineSteps.findIndex(s => runningJob?.sub_status?.includes(s))" :size="12" class="text-white" />
                <div v-else-if="runningJob?.sub_status?.includes(step)" class="w-2 h-2 bg-black rounded-full animate-ping"></div>
              </div>
              <span 
                class="text-[10px] font-black uppercase tracking-widest text-center transition-colors duration-500"
                :class="runningJob?.sub_status?.includes(step) ? 'text-yellow-400' : 'text-white/40'"
              >
                {{ step }}
              </span>
            </div>
          </div>

          <!-- Detailed Status & Reasoning Stream -->
          <div class="p-6 bg-black/40 rounded-xl border border-white/5 flex flex-col gap-4 shadow-inner">
            <div class="flex items-center justify-between">
              <div class="flex items-center gap-3 text-[11px] font-black uppercase tracking-[0.2em] text-white/80">
                <div class="w-2 h-2 rounded-full bg-yellow-400 animate-pulse shadow-[0_0_8px_rgba(250,204,21,0.8)]"></div>
                Internal Thought Stream
              </div>
              <div v-if="runningJob?.sub_status?.includes('Debating')" class="px-3 py-1 bg-yellow-400/10 text-yellow-400 text-[10px] font-black rounded-full border border-yellow-400/20">
                {{ runningJob.sub_status }}
              </div>
            </div>
            
            <div class="font-mono text-[13px] text-white/80 leading-relaxed italic bg-black/20 p-4 rounded-lg border border-white/5">
              <span v-if="runningJob?.sub_status" class="text-yellow-400 font-bold mr-2">[{{ runningJob.sub_status }}]:</span>
              {{ thoughtStreamText || 'Searching for latest market signals and weighing analyst consensus...' }}
            </div>

            <!-- Emergency Purge Action -->
            <div class="mt-4 pt-6 border-t border-red-500/10 flex justify-between items-center">
              <div class="text-[10px] text-red-400/70 font-bold flex items-center gap-3 bg-red-400/5 px-4 py-2 rounded-lg border border-red-400/10">
                <AlertTriangle :size="14" />
                <span class="uppercase tracking-widest">System stuck? Break the loop with Nuclear Reset</span>
              </div>
              <button 
                @click="handlePurge"
                class="px-6 py-2 bg-red-600/10 hover:bg-red-600 text-red-500 hover:text-white border border-red-500/20 rounded-xl transition-all font-black text-[10px] uppercase tracking-widest shadow-lg"
              >
                Nuclear Reset
              </button>
            </div>
          </div>
        </div>
      </div>
    </transition>

    <div class="grid grid-cols-1 lg:grid-cols-12 gap-8 items-start">
      <!-- Left Column: Config -->
      <div class="lg:col-span-7 space-y-8">
        <!-- Configuration Form -->
        <div class="bg-[var(--color-bg-card)] border border-[var(--color-border-default)] rounded-2xl p-8 shadow-2xl relative overflow-hidden h-full">
          <!-- Decorative background glow -->
          <div class="absolute -top-24 -right-24 w-48 h-48 bg-[var(--color-accent-primary)] opacity-5 blur-[100px] rounded-full"></div>
          
          <!-- Tab Switcher -->
          <div class="flex p-1 bg-[var(--color-bg-elevated)] rounded-xl border border-[var(--color-border-default)] mb-8 relative z-10">
            <button 
              @click="activeTab = 'research'"
              type="button"
              class="flex-1 flex items-center justify-center gap-2 py-2.5 text-xs font-black uppercase tracking-widest rounded-lg transition-all"
              :class="activeTab === 'research' ? 'bg-white text-black shadow-lg' : 'text-[var(--color-text-muted)] hover:text-white'"
            >
              <Zap :size="14" />
              Research
            </button>
            <button 
              @click="activeTab = 'automation'"
              type="button"
              class="flex-1 flex items-center justify-center gap-2 py-2.5 text-xs font-black uppercase tracking-widest rounded-lg transition-all"
              :class="activeTab === 'automation' ? 'bg-white text-black shadow-lg' : 'text-[var(--color-text-muted)] hover:text-white'"
            >
              <Clock :size="14" />
              Scheduling
            </button>
          </div>

          <form @submit.prevent="handleSubmit" class="space-y-8 relative z-10">
            
            <!-- Tickers -->
            <div class="space-y-3">
              <label class="flex items-center gap-2 text-sm font-bold uppercase tracking-wider text-[var(--color-text-secondary)]">
                <Settings2 :size="16" class="text-[var(--color-accent-primary)]" />
                Target Tickers
              </label>
              <input 
                v-model="tickersInput"
                type="text" 
                placeholder="e.g. AAPL, MSFT, TSLA" 
                class="w-full px-6 py-4 bg-[var(--color-bg-elevated)] border border-[var(--color-border-default)] rounded-xl focus:outline-none focus:border-[var(--color-accent-primary)] focus:ring-2 focus:ring-[var(--color-accent-primary)]/20 transition-all text-xl font-mono"
                required
                :disabled="isProcessingQueue"
              />
            </div>

            <!-- Models -->
            <div class="grid grid-cols-1 md:grid-cols-3 gap-6">
              <div class="space-y-3">
                <label class="text-xs font-bold uppercase tracking-wider text-[var(--color-text-secondary)]">Provider</label>
                <select v-model="provider" :disabled="isProcessingQueue" class="w-full px-4 py-3 bg-[var(--color-bg-elevated)] border border-[var(--color-border-default)] rounded-xl focus:outline-none focus:border-[var(--color-accent-primary)] transition-all">
                  <option value="openai">OpenAI</option>
                  <option value="anthropic">Anthropic</option>
                  <option value="google">Google</option>
                  <option value="ollama">Ollama</option>
                </select>
              </div>
              
              <div class="space-y-3">
                <label class="text-xs font-bold uppercase tracking-wider text-[var(--color-text-secondary)]">Quick Model</label>
                <div v-if="provider === 'ollama'" class="relative">
                  <select v-model="quickModel" :disabled="isProcessingQueue" class="w-full px-4 py-3 bg-[var(--color-bg-elevated)] border border-[var(--color-border-default)] rounded-xl focus:outline-none focus:border-[var(--color-accent-primary)] appearance-none transition-all">
                    <option v-for="m in ollamaModels" :key="m" :value="m">{{ m }}</option>
                    <option v-if="ollamaModels.length === 0" disabled>No models found</option>
                  </select>
                  <div v-if="fetchingModels" class="absolute right-3 top-3">
                    <RefreshCw :size="18" class="animate-spin text-[var(--color-text-muted)]" />
                  </div>
                </div>
                <input v-else v-model="quickModel" :disabled="isProcessingQueue" type="text" class="w-full px-4 py-3 bg-[var(--color-bg-elevated)] border border-[var(--color-border-default)] rounded-xl focus:outline-none focus:border-[var(--color-accent-primary)]" />
              </div>

              <div class="space-y-3">
                <label class="text-xs font-bold uppercase tracking-wider text-[var(--color-text-secondary)]">Deep Model</label>
                <div v-if="provider === 'ollama'" class="relative">
                  <select v-model="deepModel" :disabled="isProcessingQueue" class="w-full px-4 py-3 bg-[var(--color-bg-elevated)] border border-[var(--color-border-default)] rounded-xl focus:outline-none focus:border-[var(--color-accent-primary)] appearance-none transition-all">
                    <option v-for="m in ollamaModels" :key="m" :value="m">{{ m }}</option>
                    <option v-if="ollamaModels.length === 0" disabled>No models found</option>
                  </select>
                  <div v-if="fetchingModels" class="absolute right-3 top-3">
                    <RefreshCw :size="18" class="animate-spin text-[var(--color-text-muted)]" />
                  </div>
                </div>
                <input v-else v-model="deepModel" :disabled="isProcessingQueue" type="text" class="w-full px-4 py-3 bg-[var(--color-bg-elevated)] border border-[var(--color-border-default)] rounded-xl focus:outline-none focus:border-[var(--color-accent-primary)]" />
              </div>
            </div>

            <!-- Contextual Fields -->
            <div class="flex flex-col gap-10 pt-6 border-t border-[var(--color-border-default)]">
              <!-- Research Tab Fields -->
              <div v-if="activeTab === 'research'" class="space-y-4 animate-in fade-in slide-in-from-top-2 duration-300">
                <label class="text-xs font-bold uppercase tracking-wider text-[var(--color-text-secondary)]">Analysis Timeframe</label>
                <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
                  <div class="space-y-2">
                    <span class="text-[10px] uppercase font-black opacity-40">Start Date</span>
                    <input v-model="dateFrom" @blur="dateFrom = padDate(dateFrom)" :disabled="isProcessingQueue" type="text" placeholder="YYYY-MM-DD" class="w-full px-4 py-3 bg-[var(--color-bg-elevated)] border border-[var(--color-border-default)] rounded-xl focus:outline-none focus:border-[var(--color-accent-primary)]" />
                  </div>
                  <div class="space-y-2">
                    <span class="text-[10px] uppercase font-black opacity-40">End Date</span>
                    <input v-model="dateTo" @blur="dateTo = padDate(dateTo)" :disabled="isProcessingQueue" type="text" placeholder="YYYY-MM-DD" class="w-full px-4 py-3 bg-[var(--color-bg-elevated)] border border-[var(--color-border-default)] rounded-xl focus:outline-none focus:border-[var(--color-accent-primary)]" />
                  </div>
                </div>
              </div>

              <!-- Automation Tab Fields -->
              <div v-if="activeTab === 'automation'" class="space-y-8 animate-in fade-in slide-in-from-top-2 duration-300">
                <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
                  <div class="space-y-3">
                    <label class="text-xs font-bold uppercase tracking-wider text-[var(--color-text-secondary)]">Recurrence</label>
                    <select v-model="intervalMinutes" :disabled="isProcessingQueue" class="w-full px-4 py-3 bg-[var(--color-bg-elevated)] border border-[var(--color-border-default)] rounded-xl focus:outline-none focus:border-[var(--color-accent-primary)]">
                      <option :value="1440">Daily</option>
                      <option :value="10080">Weekly</option>
                      <option :value="43200">Monthly</option>
                    </select>
                  </div>
                  <div class="space-y-3">
                    <label class="text-xs font-bold uppercase tracking-wider text-[var(--color-text-secondary)]">Execution Time (UTC)</label>
                    <div class="relative">
                      <input 
                        v-model="scheduledTime" 
                        type="text" 
                        placeholder="HH:MM" 
                        class="w-full px-4 py-3 bg-[var(--color-bg-elevated)] border border-[var(--color-border-default)] rounded-xl focus:outline-none focus:border-[var(--color-accent-primary)] font-mono"
                      />
                      <Clock class="absolute right-4 top-3.5 opacity-20" :size="16" />
                    </div>
                  </div>
                </div>
              </div>

              <div class="space-y-3">
                <label class="text-xs font-bold uppercase tracking-wider text-[var(--color-text-secondary)]">Debate Depth</label>
                <div class="flex items-center gap-6">
                  <input v-model.number="depth" :disabled="isProcessingQueue" type="range" min="1" max="5" class="flex-1 accent-[var(--color-accent-primary)]" />
                  <span class="w-10 h-10 flex items-center justify-center bg-[var(--color-bg-elevated)] rounded-lg font-bold border border-[var(--color-border-default)] text-lg">{{ depth }}</span>
                </div>
                <p class="text-[10px] text-[var(--color-text-muted)] italic">Higher depth increases reasoning rounds between Bull and Bear agents.</p>
              </div>
            </div>

            <!-- Action Buttons -->
            <div class="pt-8 border-t border-[var(--color-border-default)] flex flex-wrap gap-4">
              <template v-if="activeTab === 'research'">
                <button
                  v-if="!isRunning"
                  type="submit"
                  :disabled="loading"
                  class="flex items-center justify-center gap-3 px-8 py-4 bg-[var(--color-accent-primary)] hover:bg-[var(--color-accent-hover)] text-white font-black uppercase tracking-widest rounded-xl transition-all transform hover:scale-[1.02] active:scale-[0.98] disabled:opacity-50 shadow-xl shadow-[var(--color-accent-primary)]/40"
                >
                  <RefreshCw v-if="loading" :size="20" class="animate-spin" />
                  <Play v-else :size="20" /> Start Now
                </button>

                <button
                  type="button"
                  @click="addToQueue"
                  class="flex items-center justify-center gap-3 px-8 py-4 bg-[var(--color-bg-elevated)] hover:bg-opacity-80 border border-[var(--color-border-default)] text-white font-black uppercase tracking-widest rounded-xl transition-all transform hover:scale-[1.02] active:scale-[0.98]"
                >
                  Add to Queue
                </button>
              </template>

              <template v-else>
                <button
                  type="submit"
                  :disabled="loading"
                  class="flex items-center justify-center gap-3 px-8 py-4 bg-[var(--color-accent-primary)] hover:bg-[var(--color-accent-hover)] text-white font-black uppercase tracking-widest rounded-xl transition-all transform hover:scale-[1.02] active:scale-[0.98] disabled:opacity-50 shadow-xl shadow-[var(--color-accent-primary)]/40"
                >
                  <Clock :size="20" /> Create Pipeline
                </button>
              </template>

            </div>
          </form>
        </div>
      </div>

      <!-- Right Column: Research Queue -->
      <div class="lg:col-span-5 space-y-6">
        <div class="bg-[var(--color-bg-card)] border border-[var(--color-border-default)] rounded-2xl p-6 shadow-2xl relative overflow-hidden flex flex-col h-full min-h-[600px]">
          <div class="flex items-center justify-between mb-6">
            <h2 class="text-xl font-bold flex items-center gap-3">
              <RefreshCw v-if="isQueueRunning && !isQueuePaused" :size="20" class="text-[var(--color-accent-primary)] animate-spin" />
              <Pause v-else-if="isQueuePaused" :size="20" class="text-amber-400" />
              <RefreshCw v-else :size="20" class="text-[var(--color-accent-primary)]" />
              Research Queue
            </h2>
            <div class="flex gap-2 items-center">
              <button 
                v-if="isQueueRunning || researchQueue.length > 0" 
                @click="handlePauseToggle" 
                class="px-2 py-1 bg-amber-500/10 text-[9px] font-black uppercase rounded border border-amber-500/20 text-amber-500 hover:bg-amber-500/20 transition-colors flex items-center gap-1"
              >
                <Pause v-if="!isQueuePaused" :size="10" />
                <Play v-else :size="10" />
                {{ isQueuePaused ? 'Resume' : 'Pause Stack' }}
              </button>
              <button @click="sweepDepth" :disabled="isProcessingQueue || !tickersInput" class="px-2 py-1 bg-black/40 text-[9px] font-black uppercase rounded border border-white/10 hover:bg-black/60 transition-colors">Sweep Depth</button>
            </div>
          </div>

          <div v-if="researchQueue.length === 0" class="flex-1 flex flex-col items-center justify-center text-center p-8 border-2 border-dashed border-[var(--color-border-default)] rounded-xl opacity-40">
            <Clock :size="48" class="mb-4" />
            <p class="text-sm font-bold uppercase tracking-widest">Queue is Empty</p>
            <p class="text-xs mt-2 italic">Add runs with different criteria to test input effects on alpha.</p>
          </div>

          <div v-else class="flex-1 space-y-3 overflow-y-auto max-h-[500px] pr-2 custom-scrollbar">
            <div 
              v-for="(job, index) in researchQueue" 
              :key="job.id" 
              draggable="true"
              @dragstart="onDragStart(index)"
              @dragover="onDragOver"
              @drop="onDrop(index)"
              class="p-4 bg-[var(--color-bg-elevated)] rounded-xl group relative transition-all cursor-grab active:cursor-grabbing"
              :class="[
                dragIndex === index ? 'opacity-50 border-dashed border-[var(--color-border-default)]' : 'border',
                job.id === runningJob?.id ? 'border-[var(--color-signal-buy)] shadow-[0_0_10px_rgba(34,197,94,0.2)]' : 'border-[var(--color-border-default)] hover:border-[var(--color-accent-primary)]/50'
              ]"
            >
              <div class="flex justify-between items-start">
                <div class="flex items-center gap-3">
                  <div class="opacity-30 group-hover:opacity-100 transition-opacity">
                    <GripVertical :size="16" />
                  </div>
                  <div class="space-y-1">
                    <div class="flex gap-1">
                      <span v-for="t in job.tickers" :key="t" class="text-[11px] font-black text-white bg-blue-500/20 px-1.5 py-0.5 rounded">{{ t }}</span>
                    </div>
                    <div class="text-[10px] text-white font-mono font-bold">{{ job.dateFrom || 'Today' }} → {{ job.dateTo || 'Today' }}</div>
                  </div>
                </div>
                <!-- Job Actions -->
                <div v-if="job.id !== runningJob?.id" class="flex items-center gap-2">
                  <button 
                    @click="promoteToActive(job.id)"
                    class="p-2 hover:bg-white/10 rounded-lg transition-colors group/btn"
                    title="Promote to Active"
                  >
                    <ArrowUp :size="18" class="text-green-400 group-hover/btn:scale-110 transition-transform" />
                  </button>
                  <button 
                    @click="removeFromQueue(job.id)"
                    class="p-2 hover:bg-white/10 rounded-lg transition-colors group/btn"
                    title="Remove from Queue"
                  >
                    <Trash2 :size="18" class="text-red-400 group-hover/btn:scale-110 transition-transform" />
                  </button>
                </div>
              </div>
              <div class="mt-4 flex flex-wrap gap-2">
                <span class="px-2.5 py-1 bg-black/60 text-[9px] font-black rounded-lg border border-white/10 flex items-center gap-2">
                  <span class="text-yellow-400 uppercase tracking-wider text-[8px]">ANALYST</span>
                  <span class="text-white">{{ job.quickModel }}</span>
                </span>
                <span class="px-2.5 py-1 bg-black/60 text-[9px] font-black rounded-lg border border-white/10 flex items-center gap-2">
                  <span class="text-yellow-400 uppercase tracking-wider text-[8px]">JUDGE</span>
                  <span class="text-white">{{ job.deepModel }}</span>
                </span>
                <span class="px-2.5 py-1 bg-blue-500/30 text-blue-200 text-[9px] font-black rounded-lg border border-blue-500/30 tracking-widest">
                  DEPTH {{ job.depth }}
                </span>
              </div>
            </div>
          </div>

          <div class="mt-6">
            <button
              @click="runQueue"
              :disabled="isRunning || researchQueue.length === 0"
              class="w-full py-4 bg-white text-black font-black uppercase tracking-widest rounded-xl hover:bg-opacity-90 disabled:opacity-30 transition-all flex items-center justify-center gap-3"
            >
              <Play :size="20" /> {{ isQueueRunning ? 'Stack Processing...' : 'Run Research Stack' }}
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
                <th class="px-8 py-5">Status</th>
                <th class="px-8 py-5">Next Sequence</th>
                <th class="px-8 py-5 text-right">Actions</th>
              </tr>
            </thead>
            <tbody class="divide-y divide-[var(--color-border-default)]">
              <tr v-for="s in schedules" :key="s.id" class="hover:bg-[var(--color-bg-elevated)]/30 transition-colors group">
                <td class="px-8 py-5">
                  <div class="flex flex-wrap gap-1.5">
                    <span v-for="t in s.tickers" :key="t" class="px-3 py-1 bg-[var(--color-bg-elevated)] border border-[var(--color-border-default)] rounded-md text-[10px] font-black text-[var(--color-accent-primary)]">
                      {{ t }}
                    </span>
                  </div>
                </td>
                <td class="px-8 py-5">
                  <div class="flex flex-col gap-1">
                    <span class="inline-flex items-center gap-1.5 px-3 py-1.5 bg-black/20 rounded-full text-[10px] font-bold border border-white/5 w-fit">
                      <Clock :size="12" class="opacity-50" />
                      {{ s.interval_minutes >= 1440 ? `${s.interval_minutes / 1440} DAY(S)` : `${s.interval_minutes / 60} HOUR(S)` }}
                    </span>
                    <span v-if="s.scheduled_time" class="text-[10px] font-mono opacity-50 ml-3">@ {{ s.scheduled_time }} UTC</span>
                  </div>
                </td>
                <td class="px-8 py-5">
                  <span class="text-xs font-medium uppercase opacity-70">{{ s.config.llm_provider }}</span>
                </td>
                <td class="px-8 py-5 font-mono text-[10px]">
                  <div class="flex flex-col">
                    <span :class="s.paused ? 'text-amber-400 opacity-50' : 'text-[var(--color-signal-buy)]'">{{ s.paused ? 'PAUSED' : 'ACTIVE' }}</span>
                    <span class="opacity-50 text-[9px]">{{ s.interval_minutes }} min interval</span>
                  </div>
                </td>
                <td class="px-8 py-5 font-mono text-xs opacity-60">{{ formatDate(s.next_run) }}</td>
                <td class="px-8 py-5 text-right">
                  <div class="flex justify-end gap-3">
                    <button 
                      @click="handleToggleSchedule(s.id)" 
                      class="p-2 text-[var(--color-text-muted)] hover:text-[var(--color-accent-primary)] rounded-xl hover:bg-[var(--color-accent-primary)]/10 transition-all opacity-0 group-hover:opacity-100"
                      :title="s.paused ? 'Resume Pipeline' : 'Pause Pipeline'"
                    >
                      <Play v-if="s.paused" :size="20" />
                      <Pause v-else :size="20" />
                    </button>
                    <button
                      @click="handleDeleteSchedule(s.id)"
                      class="p-2 text-[var(--color-text-muted)] hover:text-[var(--color-signal-sell)] rounded-xl hover:bg-[var(--color-signal-sell)]/10 transition-all opacity-0 group-hover:opacity-100"
                      title="Terminate Pipeline"
                    >
                      <Trash2 :size="20" />
                    </button>
                  </div>
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

