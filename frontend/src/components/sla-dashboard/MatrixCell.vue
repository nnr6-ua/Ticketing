<script setup lang="ts">
import { computed } from 'vue'

import SemaphoreBadge from '@/components/sla-dashboard/SemaphoreBadge.vue'
import type { ComplianceMetrics } from '@/types/slaDashboard'
import { formatCount, formatDurationEs } from '@/utils/format'

const props = defineProps<{ metrics: ComplianceMetrics }>()

const avgResponse = computed(() =>
  props.metrics.avg_response_seconds === null
    ? 'Sin datos'
    : formatDurationEs(props.metrics.avg_response_seconds),
)
</script>

<template>
  <div class="space-y-1" data-testid="matrix-cell">
    <p class="text-sm font-semibold tabular-nums text-slate-900">
      {{ formatCount(metrics.ticket_count) }}
      {{ metrics.ticket_count === 1 ? 'ticket' : 'tickets' }}
    </p>
    <SemaphoreBadge
      :semaphore="metrics.semaphore"
      :pct="metrics.compliance_pct"
      compact
    />
    <p class="text-xs text-slate-700">
      Tiempo medio:
      <span class="font-medium tabular-nums">{{ avgResponse }}</span>
    </p>
    <p class="text-xs" :class="metrics.overdue_count > 0 ? 'text-red-700' : 'text-slate-700'">
      Vencidos:
      <span class="font-medium tabular-nums">{{ formatCount(metrics.overdue_count) }}</span>
    </p>
  </div>
</template>
