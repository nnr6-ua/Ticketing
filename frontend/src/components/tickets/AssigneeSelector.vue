<script setup lang="ts">
import { computed } from 'vue'

import type { AssigneeRef } from '@/types/assigneeChange'

const props = withDefaults(
  defineProps<{
    modelValue: string | null
    candidates: AssigneeRef[]
    disabled?: boolean
  }>(),
  { disabled: false },
)

const emit = defineEmits<{
  'update:modelValue': [value: string | null]
}>()

const isEmpty = computed(() => props.candidates.length === 0)

function optionLabel(candidate: AssigneeRef): string {
  const team = candidate.team ? ` · ${candidate.team}` : ''
  return `${candidate.name}${team} — ${candidate.escalation_level_label}`
}

function onChange(event: Event): void {
  const value = (event.target as HTMLSelectElement).value
  emit('update:modelValue', value === '' ? null : value)
}
</script>

<template>
  <fieldset class="mt-4">
    <legend class="text-sm font-medium text-slate-800">Compañero destino</legend>

    <p v-if="isEmpty" role="status" class="mt-2 text-sm text-slate-700">
      No hay compañeros disponibles de tu equipo y nivel.
    </p>

    <template v-else>
      <label for="assignee-select" class="mt-2 block text-sm text-slate-700">
        Selecciona un compañero
      </label>
      <select
        id="assignee-select"
        :value="modelValue ?? ''"
        :disabled="disabled"
        aria-required="true"
        aria-describedby="assignee-select-help"
        class="mt-1 w-full rounded-md border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-slate-900 focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:bg-slate-100 disabled:text-slate-600"
        @change="onChange"
      >
        <option value="">Selecciona un compañero</option>
        <option
          v-for="candidate in candidates"
          :key="candidate.id"
          :value="candidate.id"
        >
          {{ optionLabel(candidate) }}
        </option>
      </select>
      <p id="assignee-select-help" class="mt-1 text-xs text-slate-600">
        Solo se muestran técnicos activos de tu mismo equipo y nivel.
      </p>
    </template>
  </fieldset>
</template>
