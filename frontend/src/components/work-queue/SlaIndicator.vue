<script setup lang="ts">
import { computed } from 'vue'

import type { SlaOutcome, SlaState } from '@/types/workQueue'
import { formatDuration, formatRemaining } from '@/utils/sla'
import { SLA_BADGE_CLASS, SLA_ICON } from '@/utils/slaStyles'

const props = defineProps<{
  state: SlaState
  remainingSeconds: number | null
  outcome: SlaOutcome
  breachDelaySeconds: number | null
}>()

const icon = computed(() => SLA_ICON[props.state])

const text = computed(() => {
  switch (props.state) {
    case 'overdue':
      return `Vencido hace ${formatDuration(Math.abs(props.remainingSeconds ?? 0))}`
    case 'at_risk':
      return props.remainingSeconds !== null && props.remainingSeconds <= 0
        ? 'Vence ahora'
        : `Próximo a vencer · ${formatRemaining(props.remainingSeconds ?? 0)}`
    case 'on_time':
      return `Dentro de plazo · ${formatRemaining(props.remainingSeconds ?? 0)}`
    case 'no_sla':
      return 'Sin SLA definido'
    case 'finalized':
      if (props.outcome === 'met') {
        return 'Dentro de plazo'
      }
      if (props.outcome === 'breached') {
        return `Incumplido hace ${formatDuration(props.breachDelaySeconds ?? 0)}`
      }
      return 'Sin SLA definido'
    default:
      return 'Sin SLA definido'
  }
})

const classes = computed(() =>
  [
    'inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium',
    SLA_BADGE_CLASS[props.state],
  ].join(' '),
)
</script>

<template>
  <span :class="classes" :data-sla-state="state">
    <component :is="icon" class="h-4 w-4 shrink-0" aria-hidden="true" />
    <span>{{ text }}</span>
  </span>
</template>
