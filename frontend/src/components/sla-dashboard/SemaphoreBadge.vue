<script setup lang="ts">
import { computed } from 'vue'

import type { SlaSemaphore } from '@/types/slaDashboard'
import { formatPercent } from '@/utils/format'
import {
  SEMAPHORE_BADGE_CLASS,
  SEMAPHORE_ICON,
  SEMAPHORE_LABEL,
} from '@/utils/slaStyles'

const props = withDefaults(
  defineProps<{
    semaphore: SlaSemaphore
    pct: number | null
    compact?: boolean
  }>(),
  { compact: false },
)

const label = computed(() => SEMAPHORE_LABEL[props.semaphore])
const icon = computed(() => SEMAPHORE_ICON[props.semaphore])
const badgeClass = computed(() => SEMAPHORE_BADGE_CLASS[props.semaphore])

const percentText = computed(() => formatPercent(props.pct))

const ariaLabel = computed(() => {
  if (props.pct === null) {
    return `Cumplimiento sin datos, ${label.value.toLocaleLowerCase('es-ES')}`
  }
  return `Cumplimiento ${percentText.value}, ${label.value.toLocaleLowerCase('es-ES')}`
})
</script>

<template>
  <span
    :class="[
      'inline-flex items-center gap-1.5 rounded-full font-medium',
      compact ? 'px-2 py-0.5 text-xs' : 'px-2.5 py-1 text-sm',
      badgeClass,
    ]"
    role="img"
    :aria-label="ariaLabel"
    data-testid="semaphore-badge"
    :data-semaphore="semaphore"
  >
    <component :is="icon" class="h-4 w-4 shrink-0" aria-hidden="true" />
    <span v-if="!compact">{{ label }}</span>
    <span class="tabular-nums">{{ percentText }}</span>
    <span v-if="compact" class="sr-only">{{ label }}</span>
  </span>
</template>
