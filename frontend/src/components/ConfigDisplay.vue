<script setup lang="ts">
import { computed } from 'vue'

const props = withDefaults(
  defineProps<{
    quickModel?: string
    deepModel?: string
    depth?: string | number
    compact?: boolean
  }>(),
  {
    quickModel: '',
    deepModel: '',
    depth: '',
    compact: false,
  }
)

const hasModelInfo = computed(() => {
  return props.quickModel || props.deepModel
})
</script>

<template>
  <div v-if="hasModelInfo">
    <!-- Compact layout (typically for mobile view or tight layouts) -->
    <div v-if="compact" class="flex flex-col gap-1 text-[10px]">
      <div class="flex items-center gap-1.5">
        <span class="text-[8px] font-black uppercase text-amber-500/70 tracking-widest">Q:</span>
        <span class="text-[9px] font-bold text-white/80 bg-white/5 px-1.5 py-0.2 rounded border border-white/5 font-mono">{{ quickModel || '—' }}</span>
      </div>
      <div class="flex items-center gap-1.5">
        <span class="text-[8px] font-black uppercase text-blue-400/70 tracking-widest">D:</span>
        <span class="text-[9px] font-bold text-white/80 bg-white/5 px-1.5 py-0.2 rounded border border-white/5 font-mono">{{ deepModel || '—' }}</span>
        <span v-if="depth !== undefined && depth !== null && depth !== ''" class="text-[8px] text-purple-400/80 bg-purple-500/10 border border-purple-500/10 px-1 py-0.2 rounded font-mono ml-1">{{ depth }} Rnd</span>
      </div>
    </div>

    <!-- Full layout (typically for desktop table cells or panels) -->
    <div v-else class="flex flex-col gap-1.5 py-1">
      <div class="flex items-center gap-2">
        <span class="text-[8px] font-black uppercase text-amber-500/70 tracking-widest w-10">Quick</span>
        <span class="text-[10px] font-bold text-white/90 bg-white/5 px-2 py-0.5 rounded border border-white/5 font-mono">{{ quickModel || '—' }}</span>
      </div>
      <div class="flex items-center gap-2">
        <span class="text-[8px] font-black uppercase text-blue-400/70 tracking-widest w-10">Deep</span>
        <span class="text-[10px] font-bold text-white/90 bg-white/5 px-2 py-0.5 rounded border border-white/5 font-mono">{{ deepModel || '—' }}</span>
      </div>
      <div class="flex items-center gap-2" v-if="depth !== undefined && depth !== null && depth !== ''">
        <span class="text-[8px] font-black uppercase text-purple-400/70 tracking-widest w-10">Depth</span>
        <span class="text-[9px] font-bold text-purple-400/90 bg-purple-500/10 px-2 py-0.5 rounded border border-purple-500/10 font-mono">{{ depth }} Rounds</span>
      </div>
    </div>
  </div>
  <div v-else class="text-[var(--color-text-muted)] text-xs font-mono">—</div>
</template>
