<script setup lang="ts">
import { RouterView, RouterLink, useRoute } from 'vue-router'
import { LayoutDashboard, CandlestickChart, FileText, CalendarClock, Trophy, Beaker, Settings2 } from 'lucide-vue-next'
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'
import { 
  selectedTickers, 
  activeTicker, 
  allTickersSelected,
  activeDate, 
  provider, 
  quickModel, 
  deepModel, 
  depth, 
  addTicker, 
  setActiveTicker, 
  configs, 
  loadConfigs 
} from './store'

const route = useRoute()
const currentRoute = computed(() => route.name)

// @ts-ignore
const buildTime = typeof __BUILD_TIMESTAMP__ !== 'undefined' ? new Date(__BUILD_TIMESTAMP__).toLocaleString() : 'Dev Build'

const navItems = computed(() => [
  { name: 'dashboard', label: 'Dashboard', icon: LayoutDashboard, to: '/' },
  { name: 'analysis', label: 'Analysis', icon: CalendarClock, to: '/analysis' },
  { name: 'chart', label: 'Charts', icon: CandlestickChart, to: `/chart/${activeTicker.value}` },
  { name: 'report', label: 'Reports', icon: FileText, to: `/report/${activeTicker.value}/${activeDate.value}` },
  { name: 'performance', label: 'Performance', icon: Trophy, to: '/performance' },
  { name: 'research', label: 'Research Lab', icon: Beaker, to: '/research' },
])

const newTickerInput = ref('')
const showConfigDropdown = ref(false)
const configContainer = ref<HTMLElement | null>(null)

onMounted(async () => {
  await loadConfigs()
  document.addEventListener('click', handleDocumentClick)
})

onBeforeUnmount(() => {
  document.removeEventListener('click', handleDocumentClick)
})

function submitNewTicker() {
  const ticker = newTickerInput.value.trim().toUpperCase()
  if (ticker) {
    addTicker(ticker)
    setActiveTicker(ticker)
    newTickerInput.value = ''
  }
}

const isAllTickersDisabled = computed(() => {
  return currentRoute.value === 'chart' || currentRoute.value === 'report'
})

function changeToAllTickers() {
  if (!isAllTickersDisabled.value) {
    allTickersSelected.value = true
  }
}

function changeActiveTicker(ticker: string) {
  allTickersSelected.value = false
  setActiveTicker(ticker)
}

function stepDate(days: number) {
  const d = new Date(activeDate.value)
  if (isNaN(d.getTime())) return
  d.setDate(d.getDate() + days)
  const yyyy = d.getFullYear()
  const mm = String(d.getMonth() + 1).padStart(2, '0')
  const dd = String(d.getDate()).padStart(2, '0')
  activeDate.value = `${yyyy}-${mm}-${dd}`
}

function blurDate() {
  activeDate.value = padDate(activeDate.value)
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

function handleDocumentClick(e: MouseEvent) {
  if (showConfigDropdown.value && configContainer.value && !configContainer.value.contains(e.target as Node)) {
    showConfigDropdown.value = false
  }
}

function isConfigMatching(c: any) {
  return provider.value === c.provider &&
         quickModel.value === c.quick_model &&
         deepModel.value === c.deep_model &&
         depth.value === c.depth
}

const currentConfigLabel = computed(() => {
  const matched = configs.value.find(isConfigMatching)
  if (matched) return matched.label
  return 'Custom'
})

function applyPreset(c: any) {
  provider.value = c.provider
  quickModel.value = c.quick_model
  deepModel.value = c.deep_model
  depth.value = c.depth
  showConfigDropdown.value = false
}

function truncateModel(name: string) {
  if (!name) return ''
  const parts = name.split('/')
  const last = parts[parts.length - 1]
  if (last.length > 15) return last.substring(0, 12) + '...'
  return last
}
</script>

<template>
  <!-- Mobile Top Bar -->
  <header class="md:hidden fixed top-0 left-0 right-0 z-50 glass px-4 py-3 flex items-center justify-between">
    <h1 class="text-lg font-bold bg-gradient-to-r from-[var(--color-accent-primary)] to-[var(--color-accent-secondary)] bg-clip-text text-transparent">
      TradingAgents
    </h1>
    <div class="flex items-center gap-2">
      <span class="w-2 h-2 rounded-full bg-[var(--color-signal-buy)] animate-pulse"></span>
      <span class="text-xs text-[var(--color-text-muted)]">Online</span>
    </div>
  </header>

  <div class="flex min-h-screen">
    <!-- Desktop Sidebar -->
    <aside class="hidden md:flex flex-col w-64 border-r border-[var(--color-border-default)] bg-[var(--color-bg-secondary)] fixed top-0 left-0 bottom-0 z-40">
      <!-- Logo -->
      <div class="p-6 border-b border-[var(--color-border-default)]">
        <h1 class="text-xl font-bold bg-gradient-to-r from-[var(--color-accent-primary)] to-[var(--color-accent-secondary)] bg-clip-text text-transparent">
          TradingAgents
        </h1>
        <p class="text-xs text-[var(--color-text-muted)] mt-1">AI Trading Analysis</p>
      </div>

      <!-- Navigation -->
      <nav class="flex-1 p-4 space-y-1">
        <RouterLink
          v-for="item in navItems"
          :key="item.name"
          :to="item.to"
          class="flex items-center gap-3 px-4 py-3 rounded-lg text-sm font-medium transition-all duration-200"
          :class="currentRoute === item.name
            ? 'bg-[var(--color-accent-glow)] text-[var(--color-accent-primary)] border border-[var(--color-accent-primary)]/20'
            : 'text-[var(--color-text-secondary)] hover:text-[var(--color-text-primary)] hover:bg-[var(--color-bg-elevated)]'"
        >
          <component :is="item.icon" :size="18" />
          {{ item.label }}
        </RouterLink>
      </nav>

      <!-- Status Footer -->
      <div class="p-4 border-t border-[var(--color-border-default)]">
        <div class="flex items-center gap-2 text-xs text-[var(--color-text-muted)]">
          <span class="w-2 h-2 rounded-full bg-[var(--color-signal-buy)] animate-pulse"></span>
          System Online
        </div>
        <div class="mt-3 text-[9px] text-[var(--color-text-muted)] opacity-50 uppercase tracking-widest font-mono" title="Frontend Build Time">
          Build: {{ buildTime }}
        </div>
      </div>
    </aside>

    <!-- Main Content Area -->
    <main class="flex-1 md:ml-64 pt-14 md:pt-0 pb-20 md:pb-0 flex flex-col min-h-screen">
      <!-- Sticky Global Control Bar -->
      <div class="sticky top-[3.5rem] md:top-0 z-30 glass border-b border-[var(--color-border-default)] px-4 md:px-8 py-3 flex flex-wrap items-center justify-between gap-4 bg-[var(--color-bg-primary)]/80 backdrop-blur-md">
        <!-- Left: Ticker Pills -->
        <div class="flex items-center gap-3 flex-wrap">
          <span class="text-xs font-black uppercase text-[var(--color-text-muted)] tracking-wider">Tickers:</span>
          <div class="flex flex-wrap gap-1.5 items-center">
            <button
              @click="changeToAllTickers"
              :disabled="isAllTickersDisabled"
              class="px-2.5 py-1 rounded text-xs font-bold transition-all border select-none animate-none"
              :class="[
                allTickersSelected && !isAllTickersDisabled
                  ? 'bg-[var(--color-accent-primary)] text-white border-[var(--color-accent-primary)] shadow-sm shadow-[var(--color-accent-primary)]/20'
                  : 'bg-[var(--color-bg-card)] text-[var(--color-text-secondary)] border-[var(--color-border-default)] hover:text-[var(--color-text-primary)] hover:border-[var(--color-text-muted)]',
                isAllTickersDisabled ? 'opacity-30 cursor-not-allowed' : 'cursor-pointer'
              ]"
              title="View all tickers aggregated"
            >
              All
            </button>
            <button
              v-for="ticker in selectedTickers"
              :key="ticker"
              @click="changeActiveTicker(ticker)"
              class="px-2.5 py-1 rounded text-xs font-bold transition-all border cursor-pointer select-none"
              :class="activeTicker === ticker && (!allTickersSelected || isAllTickersDisabled)
                ? 'bg-[var(--color-accent-primary)] text-white border-[var(--color-accent-primary)] shadow-sm shadow-[var(--color-accent-primary)]/20'
                : 'bg-[var(--color-bg-card)] text-[var(--color-text-secondary)] border-[var(--color-border-default)] hover:text-[var(--color-text-primary)] hover:border-[var(--color-text-muted)]'"
            >
              {{ ticker }}
            </button>
            <form @submit.prevent="submitNewTicker" class="flex items-center">
              <input
                v-model="newTickerInput"
                type="text"
                placeholder="+ Add"
                class="w-16 px-2 py-1 bg-[var(--color-bg-elevated)] border border-[var(--color-border-default)] rounded text-xs font-bold uppercase text-[var(--color-text-primary)] focus:outline-none focus:border-[var(--color-accent-primary)] text-center placeholder:text-[var(--color-text-muted)] placeholder:normal-case font-mono"
              />
            </form>
          </div>
        </div>

        <!-- Center: Date Slider -->
        <div class="flex items-center gap-3">
          <span class="text-xs font-black uppercase text-[var(--color-text-muted)] tracking-wider">Trade Date:</span>
          <div class="flex items-center bg-[var(--color-bg-card)] border border-[var(--color-border-default)] rounded-lg overflow-hidden p-0.5">
            <button
              @click="stepDate(-1)"
              type="button"
              class="px-2.5 py-1 hover:bg-[var(--color-bg-elevated)] text-[var(--color-text-secondary)] hover:text-white transition-colors text-xs font-bold cursor-pointer"
              title="Previous day"
            >
              &lt;
            </button>
            <input
              v-model="activeDate"
              type="text"
              placeholder="YYYY-MM-DD"
              @blur="blurDate"
              class="bg-transparent border-none text-center font-mono text-xs font-bold focus:ring-0 w-24 p-0 text-[var(--color-text-primary)] focus:outline-none"
            />
            <button
              @click="stepDate(1)"
              type="button"
              class="px-2.5 py-1 hover:bg-[var(--color-bg-elevated)] text-[var(--color-text-secondary)] hover:text-white transition-colors text-xs font-bold cursor-pointer"
              title="Next day"
            >
              &gt;
            </button>
          </div>
        </div>

        <!-- Right: Config Selector -->
        <div class="relative" ref="configContainer">
          <button
            @click="showConfigDropdown = !showConfigDropdown"
            type="button"
            class="flex items-center gap-2 px-3 py-1.5 bg-[var(--color-bg-card)] hover:bg-[var(--color-bg-elevated)] border border-[var(--color-border-default)] rounded-lg text-xs font-bold text-[var(--color-text-primary)] transition-all cursor-pointer"
          >
            <Settings2 :size="12" class="text-[var(--color-accent-primary)]" />
            <span>Config: {{ currentConfigLabel }}</span>
          </button>

          <!-- Dropdown container -->
          <div
            v-if="showConfigDropdown"
            class="absolute right-0 mt-2 w-80 bg-[var(--color-bg-card)] border border-[var(--color-border-default)] rounded-xl shadow-2xl p-4 z-50 text-xs text-[var(--color-text-primary)] space-y-4"
          >
            <div class="flex items-center justify-between border-b border-[var(--color-border-default)] pb-2 mb-2">
              <span class="font-black uppercase tracking-wider text-[var(--color-text-muted)] text-[10px]">Select Simulation Config</span>
              <button @click="showConfigDropdown = false" class="text-[var(--color-text-muted)] hover:text-white cursor-pointer">✕</button>
            </div>

            <!-- Presets list -->
            <div class="space-y-1.5 max-h-40 overflow-y-auto pr-1">
              <button
                v-for="c in configs"
                :key="c.config_id"
                @click="applyPreset(c)"
                type="button"
                class="w-full text-left p-2 rounded-lg bg-[var(--color-bg-elevated)] hover:bg-[var(--color-bg-primary)] border border-transparent transition-all flex items-center justify-between cursor-pointer animate-none"
                :class="{ 'border-[var(--color-accent-primary)]': isConfigMatching(c) }"
              >
                <div>
                  <p class="font-bold text-white">{{ c.label }}</p>
                  <p class="text-[10px] text-[var(--color-text-muted)] mt-0.5 font-mono">
                    {{ c.provider }} | Q: {{ truncateModel(c.quick_model) }} | D: {{ truncateModel(c.deep_model) }} (d:{{ c.depth }})
                  </p>
                </div>
                <span v-if="isConfigMatching(c)" class="text-[var(--color-accent-primary)] font-bold">✓</span>
              </button>
            </div>

            <!-- Custom config inputs -->
            <div class="border-t border-[var(--color-border-default)] pt-3 space-y-3">
              <p class="font-black uppercase tracking-wider text-[var(--color-text-muted)] text-[10px]">Custom Settings</p>
              <div class="grid grid-cols-2 gap-2">
                <div>
                  <label class="text-[9px] uppercase font-black text-[var(--color-text-muted)]">Provider</label>
                  <select v-model="provider" class="w-full mt-0.5 px-2 py-1.5 bg-[var(--color-bg-elevated)] border border-[var(--color-border-default)] rounded text-xs text-[var(--color-text-primary)] focus:outline-none">
                    <option value="openai">OpenAI</option>
                    <option value="anthropic">Anthropic</option>
                    <option value="google">Google</option>
                    <option value="ollama">Ollama</option>
                  </select>
                </div>
                <div>
                  <label class="text-[9px] uppercase font-black text-[var(--color-text-muted)]">Debate Depth</label>
                  <select v-model.number="depth" class="w-full mt-0.5 px-2 py-1.5 bg-[var(--color-bg-elevated)] border border-[var(--color-border-default)] rounded text-xs text-[var(--color-text-primary)] focus:outline-none">
                    <option :value="1">1</option>
                    <option :value="2">2</option>
                    <option :value="3">3</option>
                    <option :value="4">4</option>
                    <option :value="5">5</option>
                  </select>
                </div>
              </div>
              <div>
                <label class="text-[9px] uppercase font-black text-[var(--color-text-muted)]">Quick Model</label>
                <input v-model="quickModel" type="text" class="w-full mt-0.5 px-2 py-1.5 bg-[var(--color-bg-elevated)] border border-[var(--color-border-default)] rounded text-xs text-[var(--color-text-primary)] focus:outline-none" />
              </div>
              <div>
                <label class="text-[9px] uppercase font-black text-[var(--color-text-muted)]">Deep Model</label>
                <input v-model="deepModel" type="text" class="w-full mt-0.5 px-2 py-1.5 bg-[var(--color-bg-elevated)] border border-[var(--color-border-default)] rounded text-xs text-[var(--color-text-primary)] focus:outline-none" />
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Main content body -->
      <div class="flex-1">
        <RouterView />
      </div>
    </main>

    <!-- Mobile Bottom Navigation -->
    <nav class="md:hidden fixed bottom-0 left-0 right-0 z-50 glass flex items-center justify-around py-2">
      <RouterLink
        v-for="item in navItems"
        :key="item.name"
        :to="item.to"
        class="flex flex-col items-center gap-1 px-4 py-2 rounded-lg transition-colors"
        :class="currentRoute === item.name
          ? 'text-[var(--color-accent-primary)]'
          : 'text-[var(--color-text-muted)]'"
      >
        <component :is="item.icon" :size="20" />
        <span class="text-[10px] font-medium">{{ item.label }}</span>
      </RouterLink>
    </nav>
  </div>
</template>
