<script setup lang="ts">
import { ref, onMounted, watch } from 'vue'
import { useRouter } from 'vue-router'
import { fetchReportList, fetchReportContent, fetchRuns, type Run } from '../api/client'
import { marked } from 'marked'
import DOMPurify from 'dompurify'
import { ArrowLeft, FileText, RefreshCw, ChevronRight } from 'lucide-vue-next'

const props = defineProps<{ ticker: string; date: string }>()
const router = useRouter()

const files = ref<string[]>([])
const activeFile = ref('')
const content = ref('')
const loading = ref(true)
const contentLoading = ref(false)
const error = ref('')
const run = ref<Run | null>(null)
const sidebarOpen = ref(true)

onMounted(async () => {
  await loadReport()
})

async function loadReport() {
  loading.value = true
  error.value = ''
  try {
    const [fileList, allRuns] = await Promise.all([
      fetchReportList(props.ticker, props.date),
      fetchRuns(props.ticker),
    ])
    files.value = fileList
    run.value = allRuns.find(r => r.trade_date === props.date) || null

    // Auto-select the first file (usually final_trade_decision)
    if (fileList.length > 0) {
      const preferred = fileList.find(f => f.includes('final_trade_decision')) || fileList[0]
      await loadFile(preferred)
    }
  } catch (e: any) {
    error.value = e.message || 'Failed to load reports'
  } finally {
    loading.value = false
  }
}

async function loadFile(filename: string) {
  activeFile.value = filename
  contentLoading.value = true
  try {
    const raw = await fetchReportContent(props.ticker, props.date, filename)
    const html = await marked(raw)
    content.value = DOMPurify.sanitize(html)
  } catch (e: any) {
    content.value = `<p class="text-red-400">Failed to load file: ${e.message}</p>`
  } finally {
    contentLoading.value = false
  }
}

function getRatingBadge(rating: string | null) {
  if (!rating) return { label: '—', cls: 'bg-gray-700 text-gray-300' }
  switch (rating) {
    case 'Buy': return { label: 'BUY', cls: 'bg-green-500/20 text-green-400 border border-green-500/30' }
    case 'Overweight': return { label: 'OVERWEIGHT', cls: 'bg-blue-500/20 text-blue-400 border border-blue-500/30' }
    case 'Hold': return { label: 'HOLD', cls: 'bg-amber-500/20 text-amber-400 border border-amber-500/30' }
    case 'Underweight': return { label: 'UNDERWEIGHT', cls: 'bg-orange-500/20 text-orange-400 border border-orange-500/30' }
    case 'Sell': return { label: 'SELL', cls: 'bg-red-500/20 text-red-400 border border-red-500/30' }
    default: return { label: rating, cls: 'bg-gray-700 text-gray-300' }
  }
}

function cleanFilename(name: string): string {
  return name.replace('.md', '').replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())
}
</script>

<template>
  <div class="flex flex-col md:flex-row h-[calc(100vh-3.5rem)] md:h-screen overflow-hidden">
    <!-- Sidebar: File List -->
    <aside
      class="w-full md:w-72 flex-shrink-0 bg-[var(--color-bg-secondary)] border-b md:border-b-0 md:border-r border-[var(--color-border-default)] overflow-y-auto"
      :class="{ 'hidden md:flex md:flex-col': !sidebarOpen }"
    >
      <!-- Header -->
      <div class="p-4 border-b border-[var(--color-border-default)]">
        <div class="flex items-center gap-2 mb-3">
          <button @click="router.push('/')" class="p-1.5 rounded-md hover:bg-[var(--color-bg-elevated)] text-[var(--color-text-muted)] transition-colors">
            <ArrowLeft :size="16" />
          </button>
          <div>
            <h2 class="text-lg font-bold">{{ ticker }}</h2>
            <p class="text-xs text-[var(--color-text-muted)]">{{ date }}</p>
          </div>
        </div>

        <!-- Rating Badge -->
        <div v-if="run" class="flex items-center gap-2">
          <span class="px-2.5 py-1 rounded-md text-xs font-bold" :class="getRatingBadge(run.rating).cls">
            {{ getRatingBadge(run.rating).label }}
          </span>
          <span v-if="run.close_price" class="text-xs text-[var(--color-text-muted)] font-mono">
            ${{ run.close_price.toFixed(2) }}
          </span>
        </div>
      </div>

      <!-- File list -->
      <div class="p-2">
        <button
          v-for="file in files"
          :key="file"
          @click="loadFile(file); sidebarOpen = false"
          class="w-full flex items-center gap-2 px-3 py-2.5 rounded-lg text-sm text-left transition-colors"
          :class="activeFile === file
            ? 'bg-[var(--color-accent-glow)] text-[var(--color-accent-primary)]'
            : 'text-[var(--color-text-secondary)] hover:bg-[var(--color-bg-elevated)] hover:text-[var(--color-text-primary)]'"
        >
          <FileText :size="14" class="flex-shrink-0" />
          <span class="truncate">{{ cleanFilename(file) }}</span>
        </button>
      </div>
    </aside>

    <!-- Mobile toggle -->
    <button
      @click="sidebarOpen = !sidebarOpen"
      class="md:hidden flex items-center gap-2 px-4 py-3 bg-[var(--color-bg-card)] border-b border-[var(--color-border-default)] text-sm text-[var(--color-text-secondary)]"
    >
      <ChevronRight :size="14" :class="{ 'rotate-90': sidebarOpen }" class="transition-transform" />
      {{ activeFile ? cleanFilename(activeFile) : 'Select a report' }}
    </button>

    <!-- Content Area -->
    <main class="flex-1 overflow-y-auto">
      <div v-if="loading" class="flex items-center justify-center h-full">
        <RefreshCw :size="24" class="animate-spin text-[var(--color-text-muted)]" />
      </div>
      <div v-else-if="error" class="flex items-center justify-center h-full text-[var(--color-signal-sell)]">
        {{ error }}
      </div>
      <div v-else-if="contentLoading" class="flex items-center justify-center h-full">
        <RefreshCw :size="20" class="animate-spin text-[var(--color-text-muted)]" />
      </div>
      <div v-else class="p-4 md:p-8 max-w-4xl">
        <div class="markdown-body" v-html="content"></div>
      </div>
    </main>
  </div>
</template>
