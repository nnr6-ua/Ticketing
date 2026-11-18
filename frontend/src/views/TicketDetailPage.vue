<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'

import TicketWorkflowPanel from '@/components/tickets/TicketWorkflowPanel.vue'
import { isTechnician } from '@/auth/session'
import { MY_TICKETS_PATH, WORK_QUEUE_PATH } from '@/router/landing'

const backTarget = isTechnician() ? WORK_QUEUE_PATH : MY_TICKETS_PATH
const backLabel = isTechnician()
  ? 'Volver a la cola de trabajo'
  : 'Volver a mis tickets'

const route = useRoute()

const ticketId = computed(() => {
  const raw = route.params.id
  return Array.isArray(raw) ? (raw[0] ?? '') : (raw ?? '')
})
</script>

<template>
  <main class="mx-auto max-w-7xl px-4 py-8">
    <RouterLink
      :to="backTarget"
      class="inline-flex items-center text-sm font-medium text-slate-700 underline-offset-4 hover:text-slate-900 hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-slate-900 focus-visible:ring-offset-2"
    >
      {{ backLabel }}
    </RouterLink>

    <div class="mt-4">
      <TicketWorkflowPanel :ticket-id="ticketId" />
    </div>
  </main>
</template>
