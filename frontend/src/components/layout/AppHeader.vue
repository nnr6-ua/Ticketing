<script setup lang="ts">
import { onMounted, onUnmounted } from 'vue'

import NotificationBell from '@/components/notifications/NotificationBell.vue'
import { getAccessToken } from '@/api/client'
import { useNotificationsStore } from '@/stores/notifications'

const notifications = useNotificationsStore()

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
      <RouterLink
        to="/cola-de-trabajo"
        class="text-base font-semibold text-slate-900 underline-offset-4 hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-slate-900 focus-visible:ring-offset-2"
      >
        Mesa de ayuda
      </RouterLink>

      <NotificationBell />
    </div>
  </header>
</template>
