<script setup lang="ts">
import { computed, ref } from 'vue'

const props = withDefaults(
  defineProps<{
    modelValue: string
    disabled?: boolean
    error?: string | null
  }>(),
  { disabled: false, error: null },
)

const emit = defineEmits<{
  'update:modelValue': [value: string]
  submit: []
}>()

const MAX_LENGTH = 5000

const trimmedLength = computed(() => props.modelValue.trim().length)
const isValid = computed(
  () => trimmedLength.value >= 1 && trimmedLength.value <= MAX_LENGTH,
)
const isOverLimit = computed(() => trimmedLength.value > MAX_LENGTH)
const canSubmit = computed(() => isValid.value && !props.disabled)
const textarea = ref<HTMLTextAreaElement | null>(null)

defineExpose({
  focus: () => textarea.value?.focus(),
})

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
  <form novalidate @submit.prevent="onSubmit">
    <label for="internal-comment" class="block text-sm font-medium text-slate-900">
      Comentario interno
    </label>
    <p id="internal-comment-help" class="mt-1 text-sm text-slate-600">
      Solo visible para el técnico asignado, supervisores y administradores.
    </p>
    <textarea
      id="internal-comment"
      ref="textarea"
      :value="modelValue"
      :maxlength="MAX_LENGTH"
      :disabled="disabled"
      rows="4"
      :aria-invalid="error ? 'true' : undefined"
      aria-describedby="internal-comment-help internal-comment-counter internal-comment-error"
      class="mt-2 block w-full rounded-md border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 shadow-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-slate-900 focus-visible:ring-offset-2 disabled:bg-slate-100"
      @input="onInput"
    ></textarea>
    <div class="mt-1 flex items-center justify-between gap-3">
      <p
        id="internal-comment-counter"
        class="text-xs"
        :class="isOverLimit ? 'font-medium text-red-700' : 'text-slate-600'"
      >
        {{ trimmedLength }} / {{ MAX_LENGTH }}
      </p>
      <p class="text-xs text-slate-500">
        No cambia el estado del ticket.
      </p>
    </div>
    <p
      v-if="error"
      id="internal-comment-error"
      role="alert"
      class="mt-2 text-sm text-red-700"
    >
      {{ error }}
    </p>
    <button
      type="submit"
      :disabled="!canSubmit"
      class="mt-3 inline-flex items-center rounded-md bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:bg-slate-700 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-slate-900 focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:bg-slate-300 disabled:text-slate-600"
    >
      Añadir comentario interno
    </button>
  </form>
</template>
