<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useRouter } from 'vue-router'
import { fetchRuns, type Run } from '../api/client'
import { TrendingUp, TrendingDown, Minus, Clock, CheckCircle, XCircle, Eye, Trash2, RefreshCw } from 'lucide-vue-next'

const router = useRouter()
const runs = ref<Run[]>([])
const loading = ref(true)
const error = ref('')

onMounted(async () => {
  await loadRuns()
})

async function loadRuns() {
  loading.value = true
  error.value = ''
  try {
    runs.value = await fetchRuns()
  } catch (e: any) {
    error.value = e.message || 'Failed to load runs'
  } finally {
    loading.value = false
  }
}

// Stats
const completedRuns = computed(() => runs.value.filter(r => r.status === 'completed'))
const buySignals = computed(() => completedRuns.value.filter(r => r.action === 'Buy' || r.rating === 'Buy' || r.rating === 'Overweight'))
const sellSignals = computed(() => completedRuns.value.filter(r => r.action === 'Sell' || r.rating === 'Sell' || r.rating === 'Underweight'))

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

    <!-- Recent Runs Table -->
    <div class="rounded-xl bg-[var(--color-bg-card)] border border-[var(--color-border-default)] overflow-hidden">
      <div class="flex items-center justify-between p-4 md:p-5 border-b border-[var(--color-border-default)]">
        <h2 class="text-lg font-semibold">Recent Analyses</h2>
        <button
          @click="loadRuns"
          class="p-2 rounded-lg hover:bg-[var(--color-bg-elevated)] text-[var(--color-text-muted)] hover:text-[var(--color-text-primary)] transition-colors"
          :class="{ 'animate-spin': loading }"
        >
          <RefreshCw :size="16" />
        </button>
      </div>

      <!-- Loading -->
      <div v-if="loading" class="p-12 text-center text-[var(--color-text-muted)]">
        <RefreshCw :size="24" class="animate-spin mx-auto mb-3" />
        <p>Loading analyses...</p>
      </div>

      <!-- Error -->
      <div v-else-if="error" class="p-12 text-center text-[var(--color-signal-sell)]">
        <XCircle :size="24" class="mx-auto mb-3" />
        <p>{{ error }}</p>
      </div>

      <!-- Empty -->
      <div v-else-if="runs.length === 0" class="p-12 text-center text-[var(--color-text-muted)]">
        <p class="text-lg mb-2">No analyses yet</p>
        <p class="text-sm">Run your first analysis from the CLI to see results here.</p>
      </div>

      <!-- Table (desktop) -->
      <div v-else class="hidden md:block overflow-x-auto">
        <table class="w-full text-sm">
          <thead>
            <tr class="text-[var(--color-text-muted)] text-xs uppercase tracking-wider">
              <th class="px-5 py-3 text-left">Ticker</th>
              <th class="px-5 py-3 text-left">Date</th>
              <th class="px-5 py-3 text-left">Rating</th>
              <th class="px-5 py-3 text-left">Action</th>
              <th class="px-5 py-3 text-right">Close Price</th>
              <th class="px-5 py-3 text-left">Status</th>
              <th class="px-5 py-3 text-left">Completed</th>
              <th class="px-5 py-3 text-center">Actions</th>
            </tr>
          </thead>
          <tbody class="divide-y divide-[var(--color-border-default)]">
            <tr
              v-for="run in runs"
              :key="run.id"
              class="hover:bg-[var(--color-bg-elevated)] transition-colors"
            >
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
                <div class="flex items-center justify-center gap-2">
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
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <!-- Card List (mobile) -->
      <div v-if="runs.length > 0" class="md:hidden divide-y divide-[var(--color-border-default)]">
        <div
          v-for="run in runs"
          :key="run.id"
          class="p-4 active:bg-[var(--color-bg-elevated)] transition-colors"
          @click="run.status === 'completed' ? viewReport(run) : undefined"
        >
          <div class="flex items-center justify-between mb-2">
            <span class="font-bold text-base">{{ run.ticker }}</span>
            <span class="text-sm font-semibold" :class="getRatingColor(run.rating)">
              {{ run.rating || run.status }}
            </span>
          </div>
          <div class="flex items-center justify-between text-xs text-[var(--color-text-muted)]">
            <span>{{ run.trade_date }}</span>
            <span v-if="run.close_price" class="font-mono">${{ run.close_price.toFixed(2) }}</span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
