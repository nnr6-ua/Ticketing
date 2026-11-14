<script setup lang="ts">
import { computed, watch } from 'vue'

import type { EscalationLevel, EscalationTarget } from '@/types/assigneeChange'

const props = withDefaults(
  defineProps<{
    modelValue: EscalationLevel | null
    targets: EscalationTarget[]
    disabled?: boolean
  }>(),
  { disabled: false },
)

const emit = defineEmits<{
  'update:modelValue': [value: EscalationLevel | null]
}>()

const isEmpty = computed(() => props.targets.length === 0)

const availableValues = computed(
  () => new Set(props.targets.filter((target) => target.is_available).map((target) => target.value)),
)

function isChecked(target: EscalationTarget): boolean {
  return props.modelValue === target.value
}

function onChange(target: EscalationTarget): void {
  emit('update:modelValue', target.value)
}

// Si el nivel seleccionado deja de estar disponible tras una recarga, se limpia.
watch(
  () => props.targets,
  () => {
    if (props.modelValue && !availableValues.value.has(props.modelValue)) {
      emit('update:modelValue', null)
    }
  },
)
</script>

<template>
  <fieldset class="mt-4">
    <legend class="text-sm font-medium text-slate-800">Nivel destino</legend>

    <p v-if="isEmpty" role="status" class="mt-2 text-sm text-slate-700">
      El ticket ya está en el nivel máximo de soporte.
    </p>

    <template v-else>
      <label
        v-for="target in targets"
        :key="target.value"
        class="mt-2 flex items-start gap-2 text-sm text-slate-800"
      >
        <input
          type="radio"
          name="escalation-level"
          :value="target.value"
          :checked="isChecked(target)"
          :disabled="disabled || !target.is_available"
          class="mt-0.5 h-4 w-4 border-slate-300 text-slate-900 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-slate-900 focus-visible:ring-offset-2 disabled:cursor-not-allowed"
          @change="onChange(target)"
        />
        <span>
          {{ target.label }}
          <span
            v-if="!target.is_available"
            class="ml-1 text-xs text-slate-600"
          >
            Sin técnicos disponibles
          </span>
        </span>
      </label>
      <p class="mt-2 text-xs text-slate-600">
        El sistema asignará al técnico con menor carga del nivel elegido.
      </p>
    </template>
  </fieldset>
</template>
