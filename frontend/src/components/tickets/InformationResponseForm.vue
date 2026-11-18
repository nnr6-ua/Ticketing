<script setup lang="ts">
import { computed, ref } from 'vue'

import type { InformationRequestRef } from '@/types/ticketWorkflow'

const props = withDefaults(
  defineProps<{
    modelValue: string
    request: InformationRequestRef | null
    disabled?: boolean
    error?: string | null
    maxLength?: number
  }>(),
  { disabled: false, error: null, maxLength: 5000 },
)

const emit = defineEmits<{
  'update:modelValue': [value: string]
  submit: []
}>()

const dateFormatter = new Intl.DateTimeFormat('es-ES', {
  dateStyle: 'medium',
  timeStyle: 'short',
  timeZone: 'Europe/Madrid',
})

const trimmedLength = computed(() => props.modelValue.trim().length)
const isOverLimit = computed(() => trimmedLength.value > props.maxLength)
const isValid = computed(
  () => trimmedLength.value >= 1 && !isOverLimit.value,
)
const canSubmit = computed(() => isValid.value && !props.disabled)
const textarea = ref<HTMLTextAreaElement | null>(null)

defineExpose({
  focus: () => textarea.value?.focus(),
})

function formatDate(value: string): string {
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? value : dateFormatter.format(date)
}

function onInput(event: Event): void {
  emit('update:modelValue', (event.target as HTMLTextAreaElement).value)
}

function onSubmit(): void {
  if (!canSubmit.value) {
    return
  }
  emit('submit')
}
</script>

<template>
  <form novalidate class="space-y-4" @submit.prevent="onSubmit">
    <div
      v-if="request"
      class="rounded-lg border border-sky-200 bg-sky-50 p-4 text-sky-900"
      role="note"
      aria-labelledby="active-information-request-heading"
    >
      <p
        id="active-information-request-heading"
        class="text-sm font-semibold"
      >
        El técnico necesita esta información
      </p>
      <p class="mt-2 whitespace-pre-wrap break-words text-sm">
        {{ request.body }}
      </p>
      <p class="mt-2 text-xs text-sky-800">
        {{ request.requested_by.name }} ·
        {{ formatDate(request.requested_at) }}
      </p>
    </div>
    <p
      v-else
      role="status"
      class="rounded-lg border border-slate-200 bg-slate-50 p-4 text-sm text-slate-700"
    >
      Este ticket está pendiente de tu respuesta. Escribe la información que
      necesite el equipo técnico.
    </p>

    <div>
      <label
        for="information-response"
        class="block text-sm font-medium text-slate-900"
      >
        Tu respuesta
      </label>
      <p id="information-response-help" class="mt-1 text-sm text-slate-600">
        La respuesta quedará registrada en la actividad del ticket.
      </p>
      <textarea
        id="information-response"
        ref="textarea"
        :value="modelValue"
        :maxlength="maxLength"
        :disabled="disabled"
        rows="4"
        required
        aria-required="true"
        :aria-invalid="error ? 'true' : undefined"
        aria-describedby="information-response-help information-response-counter information-response-error"
        class="mt-2 block w-full rounded-md border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 shadow-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-slate-900 focus-visible:ring-offset-2 disabled:bg-slate-100"
        @input="onInput"
      ></textarea>
      <div class="mt-1 flex items-center justify-between gap-3">
        <p
          id="information-response-counter"
          class="text-xs"
          :class="isOverLimit ? 'font-medium text-red-700' : 'text-slate-600'"
        >
          {{ trimmedLength }} / {{ maxLength }}
        </p>
        <p class="text-xs text-slate-500">Máximo {{ maxLength }} caracteres.</p>
      </div>
      <p
        v-if="error"
        id="information-response-error"
        role="alert"
        class="mt-2 text-sm text-red-700"
      >
        {{ error }}
      </p>
    </div>

    <button
      type="submit"
      :disabled="!canSubmit"
      class="inline-flex items-center rounded-md bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:bg-slate-700 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-slate-900 focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:bg-slate-300 disabled:text-slate-600"
    >
      Enviar respuesta
    </button>
  </form>
</template>
