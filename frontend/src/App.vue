<script setup lang="ts">
import { RouterView, RouterLink, useRoute } from 'vue-router'
import { LayoutDashboard, CandlestickChart, FileText, CalendarClock, Trophy } from 'lucide-vue-next'

import { computed } from 'vue'

const route = useRoute()
const currentRoute = computed(() => route.name)

const navItems = [
  { name: 'dashboard', label: 'Dashboard', icon: LayoutDashboard, to: '/' },
  { name: 'analysis', label: 'Analysis', icon: CalendarClock, to: '/analysis' },
  { name: 'chart', label: 'Charts', icon: CandlestickChart, to: '/chart/SPY' },
  { name: 'report', label: 'Reports', icon: FileText, to: '/report/SPY/2026-05-06' },
  { name: 'performance', label: 'Performance', icon: Trophy, to: '/performance' },
]

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
      </div>
    </aside>

    <!-- Main Content Area -->
    <main class="flex-1 md:ml-64 pt-14 md:pt-0 pb-20 md:pb-0">
      <RouterView />
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
