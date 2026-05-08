<script setup lang="ts">
import { ref, onMounted, onUnmounted, computed } from 'vue'
import { useRouter } from 'vue-router'
import { fetchRuns, deleteRuns, deleteRun, type Run } from '../api/client'
import { TrendingUp, TrendingDown, Minus, Clock, CheckCircle, XCircle, Eye, Trash2, RefreshCw, Search, ArrowDown, ArrowUp } from 'lucide-vue-next'

const router = useRouter()
const runs = ref<Run[]>([])
const loading = ref(true)
const error = ref('')

// Search, Filter, Sort, Select State
const searchQuery = ref('')
const startDate = ref('')
const endDate = ref('')
const sortColumn = ref<keyof Run | 'completed_at'>('completed_at')
const sortDirection = ref<'asc' | 'desc'>('desc')
const selectedRuns = ref<Set<number>>(new Set())

let refreshInterval: ReturnType<typeof setInterval> | null = null

onMounted(async () => {
  await loadRuns()
  refreshInterval = setInterval(() => {
    loadRuns(true)
  }, 10000)

})

onUnmounted(() => {
  if (refreshInterval) clearInterval(refreshInterval)
})

async function loadRuns(silent = false) {
  if (!silent) loading.value = true
  error.value = ''
  try {
    const freshRuns = await fetchRuns()
    runs.value = freshRuns
    // Remove selected runs that no longer exist
    const currentRunIds = new Set(freshRuns.map(r => r.id))
    for (const id of selectedRuns.value) {
      if (!currentRunIds.has(id)) selectedRuns.value.delete(id)
    }
  } catch (e: any) {
    if (!silent) error.value = e.message || 'Failed to load runs'
  } finally {
    if (!silent) loading.value = false
  }
}

// Stats
const completedRuns = computed(() => runs.value.filter(r => r.status === 'completed'))
const buySignals = computed(() => completedRuns.value.filter(r => r.action === 'Buy' || r.rating === 'Buy' || r.rating === 'Overweight'))
const sellSignals = computed(() => completedRuns.value.filter(r => r.action === 'Sell' || r.rating === 'Sell' || r.rating === 'Underweight'))

// Computed Processed Runs
const processedRuns = computed(() => {
  let result = runs.value

  // Search filter
  if (searchQuery.value) {
    const q = searchQuery.value.toLowerCase()
    result = result.filter(r => 
      r.ticker.toLowerCase().includes(q) ||
      (r.rating && r.rating.toLowerCase().includes(q)) ||
      (r.action && r.action.toLowerCase().includes(q)) ||
      (r.provider && r.provider.toLowerCase().includes(q)) ||
      (r.status && r.status.toLowerCase().includes(q))
    )
  }

  // Date filters
  if (startDate.value) {
    result = result.filter(r => r.trade_date >= startDate.value)
  }
  if (endDate.value) {
    result = result.filter(r => r.trade_date <= endDate.value)
  }

  // Sort
  result = [...result].sort((a, b) => {
    let valA = a[sortColumn.value as keyof Run]
    let valB = b[sortColumn.value as keyof Run]
    
    // Handle nulls
    if (valA === null) valA = ''
    if (valB === null) valB = ''

    if (valA < valB) return sortDirection.value === 'asc' ? -1 : 1
    if (valA > valB) return sortDirection.value === 'asc' ? 1 : -1
    return 0
  })

  return result
})

const allSelected = computed(() => {
  return processedRuns.value.length > 0 && processedRuns.value.every(r => selectedRuns.value.has(r.id))
})

const isIndeterminate = computed(() => {
  return selectedRuns.value.size > 0 && selectedRuns.value.size < processedRuns.value.length
})

function toggleSelectAll() {
  if (allSelected.value) {
    selectedRuns.value.clear()
  } else {
    processedRuns.value.forEach(r => selectedRuns.value.add(r.id))
  }
}

function toggleSelect(id: number) {
  if (selectedRuns.value.has(id)) {
    selectedRuns.value.delete(id)
  } else {
    selectedRuns.value.add(id)
  }
}

function handleSort(column: keyof Run) {
  if (sortColumn.value === column) {
    sortDirection.value = sortDirection.value === 'asc' ? 'desc' : 'asc'
  } else {
    sortColumn.value = column
    sortDirection.value = 'asc' // default to asc on new column
  }
}

async function handleDeleteSelected() {
  if (selectedRuns.value.size === 0) return
  if (!confirm(`Are you sure you want to permanently delete ${selectedRuns.value.size} runs and their reports?`)) return
  
  loading.value = true
  try {
    await deleteRuns(Array.from(selectedRuns.value))
    selectedRuns.value.clear()
    await loadRuns()
  } catch (e: any) {
    alert(e.message || 'Failed to delete runs')
  } finally {
    loading.value = false
  }
}

async function handleDelete(run: Run) {
  if (!confirm(`Are you sure you want to permanently delete run for ${run.ticker}?`)) return
  loading.value = true
  try {
    await deleteRun(run.id)
    selectedRuns.value.delete(run.id)
    await loadRuns()
  } catch (e: any) {
    alert(e.message || 'Failed to delete run')
  } finally {
    loading.value = false
  }
}

function getRatingColor(rating: string | null): string {
  if (!rating) return 'text-[var(--color-text-muted)]'
  switch (rating) {
    case 'Buy': return 'text-[var(--color-signal-buy)]'
    case 'Overweight': return 'text-[var(--color-signal-overweight)]'
    case 'Hold': return 'text-[var(--color-signal-hold)]'
    case 'Underweight': return 'text-[var(--color-signal-underweight)]'
    case 'Sell': return 'text-[var(--color-signal-sell)]'
    default: return 'text-[var(--color-text-muted)]'
  }
}

function getStatusIcon(status: string) {
  switch (status) {
    case 'completed': return CheckCircle
    case 'running': return Clock
    case 'failed': return XCircle
    default: return Clock
  }
}

function getStatusColor(status: string): string {
  switch (status) {
    case 'completed': return 'text-[var(--color-signal-buy)]'
    case 'running': return 'text-[var(--color-signal-hold)]'
    case 'failed': return 'text-[var(--color-signal-sell)]'
    default: return 'text-[var(--color-text-muted)]'
  }
}

function viewReport(run: Run) {
  router.push({ name: 'report', params: { ticker: run.ticker, date: run.trade_date } })
}

function viewChart(run: Run) {
  router.push({ name: 'chart', params: { ticker: run.ticker } })
}

function formatDate(dateStr: string | null): string {
  if (!dateStr) return '—'
  const d = new Date(dateStr)
  return d.toLocaleString('en-SG', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })
}
</script>

<template>
  <div class="p-4 md:p-8 max-w-7xl mx-auto">
    <!-- Header -->
    <div class="mb-8">
      <h1 class="text-2xl md:text-3xl font-bold text-[var(--color-text-primary)]">Dashboard</h1>
      <p class="text-sm text-[var(--color-text-muted)] mt-1">AI-powered trading analysis overview</p>
    </div>

    <!-- Stats Cards -->
    <div class="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
      <!-- Total Analyses -->
      <div class="rounded-xl bg-[var(--color-bg-card)] border border-[var(--color-border-default)] p-4 md:p-5">
        <p class="text-xs text-[var(--color-text-muted)] uppercase tracking-wide">Total Analyses</p>
        <p class="text-2xl md:text-3xl font-bold mt-2">{{ completedRuns.length }}</p>
      </div>
      <!-- Buy Signals -->
      <div class="rounded-xl bg-[var(--color-bg-card)] border border-[var(--color-border-default)] p-4 md:p-5">
        <p class="text-xs text-[var(--color-text-muted)] uppercase tracking-wide">Buy Signals</p>
        <div class="flex items-center gap-2 mt-2">
          <TrendingUp :size="20" class="text-[var(--color-signal-buy)]" />
          <p class="text-2xl md:text-3xl font-bold text-[var(--color-signal-buy)]">{{ buySignals.length }}</p>
        </div>
      </div>
      <!-- Sell Signals -->
      <div class="rounded-xl bg-[var(--color-bg-card)] border border-[var(--color-border-default)] p-4 md:p-5">
        <p class="text-xs text-[var(--color-text-muted)] uppercase tracking-wide">Sell Signals</p>
        <div class="flex items-center gap-2 mt-2">
          <TrendingDown :size="20" class="text-[var(--color-signal-sell)]" />
          <p class="text-2xl md:text-3xl font-bold text-[var(--color-signal-sell)]">{{ sellSignals.length }}</p>
        </div>
      </div>
      <!-- Hold -->
      <div class="rounded-xl bg-[var(--color-bg-card)] border border-[var(--color-border-default)] p-4 md:p-5">
        <p class="text-xs text-[var(--color-text-muted)] uppercase tracking-wide">Hold</p>
        <div class="flex items-center gap-2 mt-2">
          <Minus :size="20" class="text-[var(--color-signal-hold)]" />
          <p class="text-2xl md:text-3xl font-bold text-[var(--color-signal-hold)]">{{ completedRuns.length - buySignals.length - sellSignals.length }}</p>
        </div>
      </div>
    </div>
    
    <!-- Filters and Actions -->
    <div class="flex flex-col md:flex-row md:items-center justify-between gap-4 mb-4">
      <div class="flex flex-col md:flex-row gap-3 flex-1">
        <div class="relative w-full md:w-64">
          <Search class="absolute left-3 top-1/2 -translate-y-1/2 text-[var(--color-text-muted)]" :size="16" />
          <input 
            v-model="searchQuery"
            type="text" 
            placeholder="Search ticker, status, rating..." 
            class="w-full pl-9 pr-4 py-2 bg-[var(--color-bg-card)] border border-[var(--color-border-default)] rounded-lg text-sm focus:outline-none focus:border-[var(--color-accent-primary)] transition-colors text-[var(--color-text-primary)]"
          />
        </div>
        <div class="flex items-center gap-2">
          <input 
            v-model="startDate"
            type="date" 
            class="px-3 py-2 bg-[var(--color-bg-card)] border border-[var(--color-border-default)] rounded-lg text-sm focus:outline-none focus:border-[var(--color-accent-primary)] transition-colors text-[var(--color-text-primary)]"
            title="Start Date"
          />
          <span class="text-[var(--color-text-muted)]">-</span>
          <input 
            v-model="endDate"
            type="date" 
            class="px-3 py-2 bg-[var(--color-bg-card)] border border-[var(--color-border-default)] rounded-lg text-sm focus:outline-none focus:border-[var(--color-accent-primary)] transition-colors text-[var(--color-text-primary)]"
            title="End Date"
          />
        </div>
      </div>
      <div class="flex items-center gap-2">
        <button
          v-if="selectedRuns.size > 0"
          @click="handleDeleteSelected"
          class="flex items-center gap-2 px-3 py-2 bg-[var(--color-signal-sell)] text-white bg-opacity-20 hover:bg-opacity-30 border border-[var(--color-signal-sell)] rounded-lg text-sm transition-colors"
        >
          <Trash2 :size="16" />
          Delete Selected ({{ selectedRuns.size }})
        </button>
      </div>
    </div>

    <!-- Recent Runs Table -->
    <div class="rounded-xl bg-[var(--color-bg-card)] border border-[var(--color-border-default)] overflow-hidden">
      <div class="flex items-center justify-between p-4 md:p-5 border-b border-[var(--color-border-default)]">
        <h2 class="text-lg font-semibold">Analyses Data</h2>
        <button
          @click="loadRuns(false)"
          class="p-2 rounded-lg hover:bg-[var(--color-bg-elevated)] text-[var(--color-text-muted)] hover:text-[var(--color-text-primary)] transition-colors"
          :class="{ 'animate-spin': loading }"
        >
          <RefreshCw :size="16" />
        </button>
      </div>

      <!-- Loading -->
      <div v-if="loading && runs.length === 0" class="p-12 text-center text-[var(--color-text-muted)]">
        <RefreshCw :size="24" class="animate-spin mx-auto mb-3" />
        <p>Loading analyses...</p>
      </div>

      <!-- Error -->
      <div v-else-if="error && runs.length === 0" class="p-12 text-center text-[var(--color-signal-sell)]">
        <XCircle :size="24" class="mx-auto mb-3" />
        <p>{{ error }}</p>
      </div>

      <!-- Empty -->
      <div v-else-if="processedRuns.length === 0" class="p-12 text-center text-[var(--color-text-muted)]">
        <p class="text-lg mb-2">No analyses found</p>
        <p class="text-sm">Try adjusting your filters or run a new analysis.</p>
      </div>

      <!-- Table (desktop) -->
      <div v-else class="hidden md:block overflow-x-auto">
        <table class="w-full text-sm">
          <thead>
            <tr class="text-[var(--color-text-muted)] text-xs uppercase tracking-wider select-none">
              <th class="px-5 py-3 text-left w-12">
                <input 
                  type="checkbox" 
                  :checked="allSelected"
                  :indeterminate.prop="isIndeterminate"
                  @change="toggleSelectAll"
                  class="rounded border-[var(--color-border-default)] bg-[var(--color-bg-elevated)] text-[var(--color-accent-primary)] focus:ring-[var(--color-accent-primary)] cursor-pointer"
                />
              </th>
              <th class="px-5 py-3 text-left cursor-pointer hover:text-[var(--color-text-primary)]" @click="handleSort('ticker')">
                <div class="flex items-center gap-1">Ticker <ArrowUp v-if="sortColumn === 'ticker' && sortDirection === 'asc'" :size="12"/><ArrowDown v-if="sortColumn === 'ticker' && sortDirection === 'desc'" :size="12"/></div>
              </th>
              <th class="px-5 py-3 text-left cursor-pointer hover:text-[var(--color-text-primary)]" @click="handleSort('trade_date')">
                <div class="flex items-center gap-1">Date <ArrowUp v-if="sortColumn === 'trade_date' && sortDirection === 'asc'" :size="12"/><ArrowDown v-if="sortColumn === 'trade_date' && sortDirection === 'desc'" :size="12"/></div>
              </th>
              <th class="px-5 py-3 text-left cursor-pointer hover:text-[var(--color-text-primary)]" @click="handleSort('rating')">
                <div class="flex items-center gap-1">Rating <ArrowUp v-if="sortColumn === 'rating' && sortDirection === 'asc'" :size="12"/><ArrowDown v-if="sortColumn === 'rating' && sortDirection === 'desc'" :size="12"/></div>
              </th>
              <th class="px-5 py-3 text-left cursor-pointer hover:text-[var(--color-text-primary)]" @click="handleSort('action')">
                <div class="flex items-center gap-1">Action <ArrowUp v-if="sortColumn === 'action' && sortDirection === 'asc'" :size="12"/><ArrowDown v-if="sortColumn === 'action' && sortDirection === 'desc'" :size="12"/></div>
              </th>
              <th class="px-5 py-3 text-right cursor-pointer hover:text-[var(--color-text-primary)]" @click="handleSort('close_price')">
                <div class="flex items-center justify-end gap-1">Close Price <ArrowUp v-if="sortColumn === 'close_price' && sortDirection === 'asc'" :size="12"/><ArrowDown v-if="sortColumn === 'close_price' && sortDirection === 'desc'" :size="12"/></div>
              </th>
              <th class="px-5 py-3 text-left cursor-pointer hover:text-[var(--color-text-primary)]" @click="handleSort('status')">
                <div class="flex items-center gap-1">Status <ArrowUp v-if="sortColumn === 'status' && sortDirection === 'asc'" :size="12"/><ArrowDown v-if="sortColumn === 'status' && sortDirection === 'desc'" :size="12"/></div>
              </th>
              <th class="px-5 py-3 text-left cursor-pointer hover:text-[var(--color-text-primary)]" @click="handleSort('completed_at')">
                <div class="flex items-center gap-1">Completed <ArrowUp v-if="sortColumn === 'completed_at' && sortDirection === 'asc'" :size="12"/><ArrowDown v-if="sortColumn === 'completed_at' && sortDirection === 'desc'" :size="12"/></div>
              </th>
              <th class="px-5 py-3 text-center">Actions</th>
            </tr>
          </thead>
          <tbody class="divide-y divide-[var(--color-border-default)]">
            <tr
              v-for="run in processedRuns"
              :key="run.id"
              class="hover:bg-[var(--color-bg-elevated)] transition-colors"
              :class="{ 'bg-[var(--color-bg-elevated)]': selectedRuns.has(run.id) }"
            >
              <td class="px-5 py-4">
                <input 
                  type="checkbox" 
                  :checked="selectedRuns.has(run.id)"
                  @change="toggleSelect(run.id)"
                  class="rounded border-[var(--color-border-default)] bg-[var(--color-bg-card)] text-[var(--color-accent-primary)] focus:ring-[var(--color-accent-primary)] cursor-pointer"
                />
              </td>
              <td class="px-5 py-4 font-semibold">{{ run.ticker }}</td>
              <td class="px-5 py-4 text-[var(--color-text-secondary)]">{{ run.trade_date }}</td>
              <td class="px-5 py-4 font-medium" :class="getRatingColor(run.rating)">
                {{ run.rating || '—' }}
              </td>
              <td class="px-5 py-4 font-medium" :class="getRatingColor(run.action)">
                {{ run.action || '—' }}
              </td>
              <td class="px-5 py-4 text-right font-mono">
                {{ run.close_price ? `$${run.close_price.toFixed(2)}` : '—' }}
              </td>
              <td class="px-5 py-4">
                <span class="flex items-center gap-1.5" :class="getStatusColor(run.status)">
                  <component :is="getStatusIcon(run.status)" :size="14" />
                  {{ run.status }}
                </span>
              </td>
              <td class="px-5 py-4 text-[var(--color-text-muted)]">{{ formatDate(run.completed_at) }}</td>
              <td class="px-5 py-4">
                <div class="flex items-center justify-center gap-1">
                  <button
                    @click="viewChart(run)"
                    class="p-1.5 rounded-md hover:bg-[var(--color-accent-glow)] text-[var(--color-text-muted)] hover:text-[var(--color-accent-primary)] transition-colors"
                    title="View chart"
                  >
                    <TrendingUp :size="14" />
                  </button>
                  <button
                    v-if="run.status === 'completed'"
                    @click="viewReport(run)"
                    class="p-1.5 rounded-md hover:bg-[var(--color-accent-glow)] text-[var(--color-text-muted)] hover:text-[var(--color-accent-primary)] transition-colors"
                    title="View report"
                  >
                    <Eye :size="14" />
                  </button>
                  <button
                    @click="handleDelete(run)"
                    class="p-1.5 rounded-md hover:bg-[var(--color-signal-sell)] hover:bg-opacity-10 text-[var(--color-text-muted)] hover:text-[var(--color-signal-sell)] transition-colors"
                    title="Delete run"
                  >
                    <Trash2 :size="14" />
                  </button>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <!-- Card List (mobile) -->
      <div v-if="processedRuns.length > 0" class="md:hidden divide-y divide-[var(--color-border-default)]">
        <div
          v-for="run in processedRuns"
          :key="run.id"
          class="p-4 active:bg-[var(--color-bg-elevated)] transition-colors"
          :class="{ 'bg-[var(--color-bg-elevated)]': selectedRuns.has(run.id) }"
        >
          <div class="flex items-center justify-between mb-2">
            <div class="flex items-center gap-3">
              <input 
                type="checkbox" 
                :checked="selectedRuns.has(run.id)"
                @change="toggleSelect(run.id)"
                class="rounded border-[var(--color-border-default)] bg-[var(--color-bg-card)] text-[var(--color-accent-primary)] focus:ring-[var(--color-accent-primary)]"
              />
              <span class="font-bold text-base cursor-pointer hover:underline" @click="run.status === 'completed' ? viewReport(run) : undefined">{{ run.ticker }}</span>
            </div>
            <div class="flex items-center gap-2">
              <span class="text-sm font-semibold" :class="getRatingColor(run.rating)">
                {{ run.rating || run.status }}
              </span>
              <button @click="handleDelete(run)" class="text-[var(--color-text-muted)] hover:text-[var(--color-signal-sell)] p-1"><Trash2 :size="14"/></button>
            </div>
          </div>
          <div class="flex items-center justify-between text-xs text-[var(--color-text-muted)] pl-7">
            <span>{{ run.trade_date }}</span>
            <span v-if="run.close_price" class="font-mono">${{ run.close_price.toFixed(2) }}</span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
