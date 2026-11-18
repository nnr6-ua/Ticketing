<script setup lang="ts">
import { computed } from 'vue'

import type { SlaThresholds } from '@/types/slaDashboard'
import { formatPercent } from '@/utils/format'
import {
  SEMAPHORE_BADGE_CLASS,
  SEMAPHORE_ICON,
  SEMAPHORE_LABEL,
} from '@/utils/slaStyles'

const props = defineProps<{ thresholds: SlaThresholds }>()

const bands = computed(() => [
  {
    key: 'verde' as const,
    label: SEMAPHORE_LABEL.verde,
    icon: SEMAPHORE_ICON.verde,
    rule: `≥ ${formatPercent(props.thresholds.green_pct)}`,
    className: SEMAPHORE_BADGE_CLASS.verde,
  },
  {
    key: 'ambar' as const,
    label: SEMAPHORE_LABEL.ambar,
    icon: SEMAPHORE_ICON.ambar,
    rule: `≥ ${formatPercent(props.thresholds.amber_pct)} y < ${formatPercent(props.thresholds.green_pct)}`,
    className: SEMAPHORE_BADGE_CLASS.ambar,
  },
  {
    key: 'rojo' as const,
    label: SEMAPHORE_LABEL.rojo,
    icon: SEMAPHORE_ICON.rojo,
    rule: `< ${formatPercent(props.thresholds.amber_pct)}`,
    className: SEMAPHORE_BADGE_CLASS.rojo,
  },
  {
    key: 'sin_datos' as const,
    label: SEMAPHORE_LABEL.sin_datos,
    icon: SEMAPHORE_ICON.sin_datos,
    rule: 'Sin tickets atendidos con SLA',
    className: SEMAPHORE_BADGE_CLASS.sin_datos,
  },
])
</script>

<template>
  <section
    class="rounded-lg border border-slate-200 bg-white p-4"
    aria-labelledby="sla-legend-title"
    data-testid="semaphore-legend"
  >
    <h2 id="sla-legend-title" class="text-sm font-semibold text-slate-900">
      Cómo leer el semáforo
    </h2>
    <ul class="mt-3 flex flex-wrap gap-3 text-sm text-slate-700">
      <li
        v-for="band in bands"
        :key="band.key"
        class="inline-flex items-center gap-2"
        :data-band="band.key"
      >
        <span
          :class="[
            'inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium',
            band.className,
          ]"
        >
          <component :is="band.icon" class="h-4 w-4 shrink-0" aria-hidden="true" />
          {{ band.label }}
        </span>
        <span>{{ band.rule }}</span>
      </li>
    </ul>
  </section>
</template>
