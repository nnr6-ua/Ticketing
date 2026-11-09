<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'

import TicketWorkflowPanel from '@/components/tickets/TicketWorkflowPanel.vue'

const route = useRoute()

const ticketId = computed(() => {
  const raw = route.params.id
  return Array.isArray(raw) ? (raw[0] ?? '') : (raw ?? '')
})
</script>

<template>
  <main class="mx-auto max-w-7xl px-4 py-8">
    <RouterLink
      to="/cola-de-trabajo"
      class="inline-flex items-center text-sm font-medium text-slate-700 underline-offset-4 hover:text-slate-900 hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-slate-900 focus-visible:ring-offset-2"
    >
      Volver a la cola de trabajo
    </RouterLink>

    <div class="mt-4">
      <TicketWorkflowPanel :ticket-id="ticketId" />
    </div>
  </main>
</template>
