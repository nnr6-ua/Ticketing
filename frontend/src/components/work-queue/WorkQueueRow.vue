<script setup lang="ts">
import { computed } from 'vue'

import PriorityBadge from '@/components/work-queue/PriorityBadge.vue'
import SlaIndicator from '@/components/work-queue/SlaIndicator.vue'
import StatusBadge from '@/components/work-queue/StatusBadge.vue'
import type { SlaState, WorkQueueItem } from '@/types/workQueue'
import { classifyFromRemaining, formatDuration } from '@/utils/sla'
import { SLA_ROW_CLASS } from '@/utils/slaStyles'

const props = defineProps<{
  item: WorkQueueItem
  nowMs: number
  dataNowMs: number
}>()

const liveRemaining = computed<number | null>(() => {
  if (props.item.sla.remaining_seconds === null) {
    return null
  }
  const elapsed = Math.max(0, Math.floor((props.nowMs - props.dataNowMs) / 1000))
  return props.item.sla.remaining_seconds - elapsed
})

const effectiveState = computed<SlaState>(() => {
  const sla = props.item.sla
  if (sla.state === 'finalized' || sla.state === 'no_sla') {
    return sla.state
  }
  if (liveRemaining.value === null || sla.warning_threshold_seconds === null) {
    return sla.state
  }
  return classifyFromRemaining(liveRemaining.value, sla.warning_threshold_seconds)
})

const rowClass = computed(
  () => `border-b border-slate-200 ${SLA_ROW_CLASS[effectiveState.value]}`,
)

const slaCellLabel = computed(() => {
  const state = effectiveState.value
  if (state === 'overdue') {
    return `SLA vencido hace ${formatDuration(Math.abs(liveRemaining.value ?? 0))}`
  }
  if (state === 'at_risk') {
    return liveRemaining.value !== null && liveRemaining.value <= 0
      ? 'SLA a punto de vencer: vence ahora'
      : 'SLA próximo a vencer'
  }
  if (state === 'on_time') {
    return 'SLA dentro de plazo'
  }
  if (state === 'finalized') {
    return 'Ticket finalizado'
  }
  return 'Ticket sin SLA definido'
})
</script>

<template>
  <tr :class="rowClass" data-testid="work-queue-row">
    <td class="whitespace-nowrap px-4 py-3 align-top font-mono text-sm">
      <RouterLink
        :to="`/tickets/${item.id}`"
        class="rounded text-sky-800 underline-offset-2 hover:underline"
      >
        {{ item.number }}
      </RouterLink>
    </td>
    <td class="max-w-xs px-4 py-3 align-top text-sm">
      <RouterLink
        :to="`/tickets/${item.id}`"
        :title="item.title"
        class="block max-w-xs truncate rounded font-medium text-slate-900 hover:underline"
      >
        {{ item.title }}
      </RouterLink>
    </td>
    <td class="whitespace-nowrap px-4 py-3 align-top text-sm text-slate-700">
      {{ item.category?.name ?? 'Sin categoría' }}
    </td>
    <td class="whitespace-nowrap px-4 py-3 align-top">
      <PriorityBadge :priority="item.priority" />
    </td>
    <td class="whitespace-nowrap px-4 py-3 align-top">
      <StatusBadge :status="item.status" :label="item.status_label" />
    </td>
    <td class="whitespace-nowrap px-4 py-3 align-top" :aria-label="slaCellLabel">
      <SlaIndicator
        :state="effectiveState"
        :remaining-seconds="liveRemaining"
        :outcome="item.sla.outcome"
        :breach-delay-seconds="item.sla.breach_delay_seconds"
      />
    </td>
  </tr>
</template>
