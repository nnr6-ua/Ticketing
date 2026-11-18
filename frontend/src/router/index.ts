import { createRouter, createWebHistory } from 'vue-router'

import { getAccessToken, getStoredUserRole } from '@/api/client'

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
      path: '/login',
      name: 'login',
      component: () => import('@/views/LoginPage.vue'),
    },
  ],
})

/**
 * Guard cosmético de navegación (HU-07).
 *
 * Solo actúa sobre rutas que declaran `meta.requiresRoles`; el resto de la
 * navegación (`/cola-de-trabajo`, `/tickets/:id`, `/login`) queda intacta. Sin
 * token se envía a login conservando el destino. Con token, el rol del payload
 * debe estar en `requiresRoles`; si no, se bloquea el dashboard y se muestra
 * el estado `forbidden` en una ruta neutra, sin llegar a cargar métricas.
 * La autorización real la impone el backend (`403 forbidden`).
 */
router.beforeEach((to) => {
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
