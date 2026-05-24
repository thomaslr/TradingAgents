<script setup lang="ts">
import { ref, computed } from 'vue'
import { Filter, Search } from 'lucide-vue-next'
import { configs, enabledConfigs, toggleConfig, selectAllConfigs, clearAllConfigs } from '../store'
import type { SimulationConfig } from '../api/client'

defineProps<{
  marginClass?: string
}>()

const searchVal = ref('')

const filteredConfigs = computed(() => {
  if (!searchVal.value) return configs.value
  const q = searchVal.value.toLowerCase()
  return configs.value.filter(c => c.label.toLowerCase().includes(q))
})

const enabledCount = computed(() => enabledConfigs.value.size)
const totalCount = computed(() => configs.value.length)

function safeConfigColor(c: SimulationConfig): string {
  const color = c.color || '#10b981'
  const lower = color.toLowerCase().trim()
  if (
    lower === '#ffffff' ||
    lower === '#fff' ||
    lower === 'white' ||
    lower === 'rgb(255,255,255)' ||
    lower === 'rgba(255,255,255,1)'
  ) {
    return '#10b981'
  }
  return color
}
</script>

<template>
  <div
    v-if="totalCount > 0"
    :class="[
      'bg-white/5 p-4 rounded-xl border border-white/10 flex flex-col gap-3 shadow-lg',
      marginClass || 'mb-6'
    ]"
  >
    <div class="flex flex-col md:flex-row md:items-center justify-between gap-3 border-b border-white/5 pb-3">
      <div class="flex items-center gap-2">
        <Filter :size="14" class="text-[var(--color-accent-primary)] opacity-80" />
        <span class="text-xs uppercase font-black tracking-widest text-white">Isolate Simulation Configs</span>
        <span class="text-[10px] text-[var(--color-text-muted)] font-mono">({{ enabledCount }} / {{ totalCount }} active)</span>
      </div>

      <!-- Controls & Search Bar -->
      <div class="flex flex-wrap items-center gap-2">
        <!-- Small Search input -->
        <div class="relative w-44">
          <Search class="absolute left-2.5 top-1/2 -translate-y-1/2 text-white/40" :size="12" />
          <input
            v-model="searchVal"
            type="text"
            placeholder="Search configs..."
            class="w-full pl-7 pr-2.5 py-1 bg-white/5 border border-white/10 rounded-lg text-[10px] focus:outline-none focus:border-[var(--color-accent-primary)] text-white font-medium bg-[#0f172a]"
          />
        </div>

        <button
          @click="selectAllConfigs"
          class="px-2.5 py-1 rounded bg-white/5 hover:bg-white/10 border border-white/10 text-[9px] font-black uppercase tracking-wider text-white transition-colors cursor-pointer"
        >
          Select All
        </button>
        <button
          @click="clearAllConfigs"
          class="px-2.5 py-1 rounded bg-red-500/10 hover:bg-red-500/20 border border-red-500/20 text-[9px] font-black uppercase tracking-wider text-red-400 transition-colors cursor-pointer"
        >
          Clear All
        </button>
      </div>
    </div>

    <!-- Config Buttons list: capped height with premium scrolling -->
    <div class="max-h-24 overflow-y-auto pr-1 custom-scrollbar">
      <div class="flex flex-wrap gap-2 py-0.5">
        <button
          v-for="c in filteredConfigs"
          :key="c.config_id"
          @click="toggleConfig(c.config_id)"
          class="flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs font-bold border transition-all select-none cursor-pointer"
          :class="
            enabledConfigs.has(c.config_id)
              ? 'border-white/20 bg-white/10 text-white shadow-sm'
              : 'border-white/5 bg-white/[0.02] text-[var(--color-text-muted)] opacity-40'
          "
        >
          <div class="w-2.5 h-2.5 rounded-full" :style="{ backgroundColor: safeConfigColor(c) }"></div>
          <span>{{ c.label }}</span>
        </button>
        <div v-if="filteredConfigs.length === 0" class="text-[10px] text-[var(--color-text-muted)] italic py-2 pl-1">
          No configurations match your search criteria.
        </div>
      </div>
    </div>
  </div>
</template>
