import { createRouter, createWebHistory } from 'vue-router'

import { getAccessToken } from '@/api/client'
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
      path: '/dashboard-sla',
      name: 'sla-dashboard',
      component: () => import('@/views/SlaDashboardPage.vue'),
      meta: { requiresRoles: ['supervisor', 'admin'] },
    },
    {
      path: '/acceso-denegado',
      name: 'forbidden',
      component: () => import('@/views/AccessForbiddenPage.vue'),
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

/**
 * Guard cosmético de navegación.
 *
 * Evalúa tanto `meta.requiresAdmin` (rutas de administración de `master`)
 * como `meta.requiresRoles` (dashboard de SLA de HU-07). La autorización real
 * la impone siempre el backend (`403 forbidden`).
 */
router.beforeEach((to) => {
  if (to.meta.requiresAdmin) {
    if (getStoredUserRole() === 'admin') return true
    return { name: 'login', query: { redirect: to.fullPath } }
  }

  const requiredRoles = to.meta.requiresRoles as string[] | undefined
  if (!requiredRoles || requiredRoles.length === 0) {
    return true
  }
  if (!getAccessToken()) {
    return { name: 'login', query: { redirect: to.fullPath } }
  }
  const role = getStoredUserRole()
  if (!role || !requiredRoles.includes(role)) {
    return { name: 'forbidden', replace: true }
  }
  return true
})

export default router