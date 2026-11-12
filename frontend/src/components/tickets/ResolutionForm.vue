<script setup lang="ts">
import { computed, ref } from 'vue'

const props = withDefaults(
  defineProps<{
    modelValue: string
    disabled?: boolean
    error?: string | null
    maxLength?: number
  }>(),
  { disabled: false, error: null, maxLength: 5000 },
)

const emit = defineEmits<{
  'update:modelValue': [value: string]
}>()

const trimmedLength = computed(() => props.modelValue.trim().length)
const isOverLimit = computed(() => trimmedLength.value > props.maxLength)
const textarea = ref<HTMLTextAreaElement | null>(null)

defineExpose({
  focus: () => textarea.value?.focus(),
})

function onInput(event: Event): void {
  emit('update:modelValue', (event.target as HTMLTextAreaElement).value)
}
</script>

<template>
  <div>
    <label for="resolution" class="block text-sm font-medium text-slate-900">
      Descripción de la solución
    </label>
    <p id="resolution-help" class="mt-1 text-sm text-slate-600">
      Obligatoria para marcar el ticket como Resuelto. No podrás editarla después;
      si la solución cambia, reabre el ticket y documenta una nueva.
    </p>
    <textarea
      id="resolution"
      ref="textarea"
      :value="modelValue"
      :maxlength="maxLength"
      :disabled="disabled"
      rows="5"
      required
      aria-required="true"
      :aria-invalid="error ? 'true' : undefined"
      aria-describedby="resolution-help resolution-counter resolution-error"
      class="mt-2 block w-full rounded-md border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 shadow-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-slate-900 focus-visible:ring-offset-2 disabled:bg-slate-100"
      @input="onInput"
    ></textarea>
    <div class="mt-1 flex items-center justify-between gap-3">
      <p
        id="resolution-counter"
        class="text-xs"
        :class="isOverLimit ? 'font-medium text-red-700' : 'text-slate-600'"
      >
        {{ trimmedLength }} / {{ maxLength }}
      </p>
      <p class="text-xs text-slate-500">Máximo {{ maxLength }} caracteres.</p>
    </div>
    <p
      v-if="error"
      id="resolution-error"
      role="alert"
      class="mt-2 text-sm text-red-700"
    >
      {{ error }}
    </p>
  </div>
</template>
