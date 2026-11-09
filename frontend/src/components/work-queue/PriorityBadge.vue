<script setup lang="ts">
import { computed } from 'vue'

import type { PriorityRef } from '@/types/workQueue'
import {
  PRIORITY_BADGE_CLASS,
  PRIORITY_BADGE_INACTIVE_CLASS,
} from '@/utils/slaStyles'

const props = defineProps<{ priority: PriorityRef }>()

const classes = computed(() => {
  const palette = props.priority.is_active
    ? (PRIORITY_BADGE_CLASS[props.priority.level] ?? PRIORITY_BADGE_INACTIVE_CLASS)
    : PRIORITY_BADGE_INACTIVE_CLASS
  return [
    'inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-semibold',
    palette,
  ].join(' ')
})
</script>

<template>
  <span :class="classes">
    {{ priority.name }}
    <span v-if="!priority.is_active" class="ml-1 font-normal">(inactiva)</span>
  </span>
</template>
