import { createRouter, createWebHistory } from 'vue-router'

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
      // Placeholder para no romper el enlace de la cola: la vista de detalle
      // pertenece a la HU-06 y queda fuera del alcance de la HU-04.
      path: '/tickets/:id',
      name: 'ticket-detail',
      component: () => import('@/views/TicketDetailPlaceholder.vue'),
    },
    {
      path: '/login',
      name: 'login',
      component: () => import('@/views/LoginPage.vue'),
    },
  ],
})

export default router
