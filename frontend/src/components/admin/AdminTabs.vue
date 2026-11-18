<script setup lang="ts">
const props = defineProps<{
  tabs: { id: string; label: string }[]
  modelValue: string
}>()

const emit = defineEmits<{ (event: 'update:modelValue', value: string): void }>()

function select(id: string): void {
  emit('update:modelValue', id)
}

function onKeydown(event: KeyboardEvent, index: number): void {
  let next = index
  if (event.key === 'ArrowRight') next = (index + 1) % props.tabs.length
  else if (event.key === 'ArrowLeft') {
    next = (index - 1 + props.tabs.length) % props.tabs.length
  } else if (event.key === 'Home') next = 0
  else if (event.key === 'End') next = props.tabs.length - 1
  else return
  event.preventDefault()
  const target = props.tabs[next]
  if (target) {
    select(target.id)
    const element = document.getElementById(`tab-${target.id}`)
    element?.focus()
  }
}
</script>

<template>
  <div
    role="tablist"
    aria-label="Secciones de configuración"
    class="flex gap-2 overflow-x-auto border-b border-slate-200"
  >
    <button
      v-for="(tab, index) in tabs"
      :id="`tab-${tab.id}`"
      :key="tab.id"
      type="button"
      role="tab"
      :aria-controls="`panel-${tab.id}`"
      :aria-selected="modelValue === tab.id"
      :tabindex="modelValue === tab.id ? 0 : -1"
      class="-mb-px whitespace-nowrap border-b-2 px-4 py-3 text-sm font-medium focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sky-500 focus-visible:ring-offset-2"
      :class="
        modelValue === tab.id
          ? 'border-sky-600 text-sky-700'
          : 'border-transparent text-slate-600 hover:text-slate-900'
      "
      @click="select(tab.id)"
      @keydown="onKeydown($event, index)"
    >
      {{ tab.label }}
    </button>
  </div>
</template>
