<script setup lang="ts">
import { computed } from 'vue'

import SemaphoreBadge from '@/components/sla-dashboard/SemaphoreBadge.vue'
import type { ComplianceMetrics } from '@/types/slaDashboard'
import { formatCount, formatDurationEs, formatPercent } from '@/utils/format'

const props = defineProps<{ summary: ComplianceMetrics }>()

const avgResponse = computed(() =>
  props.summary.avg_response_seconds === null
    ? 'Sin datos'
    : formatDurationEs(props.summary.avg_response_seconds),
)

const complianceText = computed(() => formatPercent(props.summary.compliance_pct))
</script>

<template>
  <section
    class="rounded-lg border border-slate-200 bg-white p-4 shadow-sm"
    aria-labelledby="sla-summary-title"
    data-testid="sla-summary"
  >
    <h2 id="sla-summary-title" class="text-lg font-semibold text-slate-900">
      Resumen global
    </h2>

    <dl class="mt-4 grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-6">
      <div>
        <dt class="text-xs font-medium uppercase tracking-wide text-slate-600">
          Tickets considerados
        </dt>
        <dd class="mt-1 text-xl font-semibold tabular-nums text-slate-900">
          {{ formatCount(summary.ticket_count) }}
        </dd>
      </div>
      <div>
        <dt class="text-xs font-medium uppercase tracking-wide text-slate-600">
          Atendidos con SLA
        </dt>
        <dd class="mt-1 text-xl font-semibold tabular-nums text-slate-900">
          {{ formatCount(summary.attended_with_sla) }}
        </dd>
      </div>
      <div>
        <dt class="text-xs font-medium uppercase tracking-wide text-slate-600">
          Cumplimiento
        </dt>
        <dd class="mt-1">
          <SemaphoreBadge
            :semaphore="summary.semaphore"
            :pct="summary.compliance_pct"
          />
          <span class="sr-only">{{ complianceText }}</span>
        </dd>
      </div>
      <div>
        <dt class="text-xs font-medium uppercase tracking-wide text-slate-600">
          Tiempo medio
        </dt>
        <dd class="mt-1 text-xl font-semibold tabular-nums text-slate-900">
          {{ avgResponse }}
        </dd>
      </div>
      <div>
        <dt class="text-xs font-medium uppercase tracking-wide text-slate-600">
          Vencidos
        </dt>
        <dd class="mt-1 text-xl font-semibold tabular-nums text-red-700">
          {{ formatCount(summary.overdue_count) }}
        </dd>
      </div>
      <div>
        <dt class="text-xs font-medium uppercase tracking-wide text-slate-600">
          Sin SLA
        </dt>
        <dd class="mt-1 text-xl font-semibold tabular-nums text-slate-900">
          {{ formatCount(summary.no_sla_count) }}
        </dd>
      </div>
    </dl>
  </section>
</template>
