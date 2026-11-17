import { createRouter, createWebHistory } from 'vue-router'

import { getStoredUserRole } from '@/auth/session'

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    {
      path: '/',
      redirect: '/cola-de-trabajo',
    },
    {
      path: '/cola-de-trabajo',
      name: 'work-queue',
      component: () => import('@/views/WorkQueuePage.vue'),
    },
    {
      path: '/mis-tickets',
      name: 'my-tickets',
      component: () => import('@/views/MyTicketsPage.vue'),
    },
    {
      path: '/tickets/new',
      name: 'ticket-create',
      component: () => import('@/views/TicketCreatePage.vue'),
    },
    {
      path: '/tickets/:id',
      name: 'ticket-detail',
      component: () => import('@/views/TicketDetailPage.vue'),
    },
    {
      path: '/admin/configuracion',
      name: 'admin-configuration',
      component: () => import('@/views/AdminConfigurationPage.vue'),
      meta: { requiresAdmin: true },
    },
    {
      path: '/login',
      name: 'login',
      component: () => import('@/views/LoginPage.vue'),
    },
  ],
})

router.beforeEach((to) => {
  if (!to.meta.requiresAdmin) return true
  if (getStoredUserRole() === 'admin') return true
  return { name: 'login', query: { redirect: to.fullPath } }
})

export default router
