<script setup lang="ts">
import { ref } from 'vue'

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

const textareaRef = ref<HTMLTextAreaElement | null>(null)

defineExpose({
  focus: (): void => {
    textareaRef.value?.focus()
  },
})

function onInput(event: Event): void {
  emit('update:modelValue', (event.target as HTMLTextAreaElement).value)
}
</script>

<template>
  <div class="mt-4">
    <label for="assignee-change-reason" class="text-sm font-medium text-slate-800">
      Motivo del cambio de responsable
    </label>
    <textarea
      id="assignee-change-reason"
      ref="textareaRef"
      :value="modelValue"
      rows="4"
      :maxlength="maxLength"
      :disabled="disabled"
      aria-required="true"
      :aria-invalid="Boolean(error)"
      aria-describedby="assignee-change-reason-help assignee-change-reason-counter assignee-change-reason-error"
      class="mt-1 w-full rounded-md border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-slate-900 focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:bg-slate-100 disabled:text-slate-600"
      @input="onInput"
    ></textarea>

    <p id="assignee-change-reason-help" class="mt-1 text-xs text-slate-600">
      Obligatorio. El usuario creador podrá ver este motivo en la línea temporal.
    </p>
    <p
      id="assignee-change-reason-counter"
      class="mt-1 text-xs"
      :class="modelValue.trim().length > maxLength ? 'text-red-700' : 'text-slate-600'"
    >
      {{ modelValue.trim().length }} / {{ maxLength }}
    </p>

    <p
      v-if="error"
      id="assignee-change-reason-error"
      role="alert"
      class="mt-1 text-sm text-red-700"
    >
      {{ error }}
    </p>
  </div>
</template>
