import { createRouter, createWebHistory } from 'vue-router'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/',
      name: 'dashboard',
      component: () => import('../views/DashboardView.vue'),
      meta: { title: 'Dashboard' },
    },
    {
      path: '/chart/:ticker',
      name: 'chart',
      component: () => import('../views/ChartView.vue'),
      meta: { title: 'Chart' },
      props: true,
    },
    {
      path: '/report/:ticker/:date',
      name: 'report',
      component: () => import('../views/ReportView.vue'),
      meta: { title: 'Report' },
      props: true,
    },
  ],
})

// Update page title on navigation
router.afterEach((to) => {
  const base = 'TradingAgents'
  document.title = to.meta.title ? `${to.meta.title} — ${base}` : base
})

export default router
