<script setup lang="ts">
defineProps<{
  message: string
  reloading?: boolean
}>()

const emit = defineEmits<{ (event: 'reload'): void }>()
</script>

<template>
  <div
    role="alert"
    aria-live="assertive"
    class="rounded-xl border border-amber-300 bg-amber-50 p-4"
  >
    <p class="font-semibold text-amber-950">La configuración ha cambiado</p>
    <p class="mt-1 text-sm text-amber-900">{{ message }}</p>
    <button
      type="button"
      class="mt-3 rounded-lg border border-amber-300 bg-white px-3 py-1.5 text-sm font-semibold text-amber-900 hover:bg-amber-100 disabled:opacity-60"
      :disabled="reloading"
      @click="emit('reload')"
    >
      {{ reloading ? 'Recargando…' : 'Recargar configuración' }}
    </button>
  </div>
</template>
