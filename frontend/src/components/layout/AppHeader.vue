<script setup lang="ts">
import { onMounted, onUnmounted } from 'vue'

import NotificationBell from '@/components/notifications/NotificationBell.vue'
import { getAccessToken, getStoredUserRole } from '@/api/client'
import { useNotificationsStore } from '@/stores/notifications'

const notifications = useNotificationsStore()

const role = getStoredUserRole()
const canViewSlaDashboard = role === 'supervisor' || role === 'admin'

onMounted(() => {
  if (getAccessToken()) {
    notifications.startPolling()
  }
})

onUnmounted(() => {
  notifications.stopPolling()
})
</script>

<template>
  <header class="border-b border-slate-200 bg-white">
    <div class="mx-auto flex max-w-7xl items-center justify-between gap-4 px-4 py-3">
      <nav class="flex items-center gap-6" aria-label="Navegación principal">
        <RouterLink
          to="/cola-de-trabajo"
          class="text-base font-semibold text-slate-900 underline-offset-4 hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-slate-900 focus-visible:ring-offset-2"
        >
          Mesa de ayuda
        </RouterLink>
        <RouterLink
          v-if="canViewSlaDashboard"
          to="/dashboard-sla"
          class="text-sm font-medium text-slate-700 underline-offset-4 hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-slate-900 focus-visible:ring-offset-2"
          data-testid="sla-dashboard-link"
        >
          Dashboard SLA
        </RouterLink>
      </nav>

      <NotificationBell />
    </div>
  </header>
</template>
