<script setup lang="ts">
import { computed } from 'vue'

const props = withDefaults(
  defineProps<{
    variant?: 'full' | 'warning' | 'forbidden'
    message?: string
  }>(),
  { variant: 'full', message: undefined },
)

const emit = defineEmits<{ (event: 'retry'): void }>()

const title = computed(() => {
  if (props.variant === 'forbidden') {
    return 'No tienes acceso a esta vista'
  }
  if (props.variant === 'warning') {
    return 'No se pudo actualizar la cola de trabajo'
  }
  return 'No se pudo cargar tu cola de trabajo'
})

const body = computed(() => {
  if (props.variant === 'forbidden') {
    return 'Esta vista está disponible solo para técnicos.'
  }
  if (props.variant === 'warning') {
    return 'No se pudo actualizar; se muestran los últimos datos.'
  }
  return props.message ?? 'Comprueba tu conexión e inténtalo de nuevo.'
})
</script>

<template>
  <div
    :class="
      variant === 'warning'
        ? 'rounded-md border border-amber-300 bg-amber-50 p-4'
        : 'rounded-lg border border-red-300 bg-red-50 p-10 text-center'
    "
    :role="variant === 'warning' ? 'status' : 'alert'"
    data-testid="work-queue-error"
    :data-variant="variant"
  >
    <h2
      :class="
        variant === 'warning'
          ? 'text-sm font-semibold text-amber-900'
          : 'text-lg font-semibold text-red-900'
      "
    >
      {{ title }}
    </h2>
    <p
      :class="
        variant === 'warning'
          ? 'mt-1 text-sm text-amber-900'
          : 'mt-2 text-sm text-red-900'
      "
    >
      {{ body }}
    </p>
    <button
      type="button"
      :class="
        variant === 'warning'
          ? 'mt-2 rounded-md border border-amber-400 bg-white px-3 py-1.5 text-sm font-medium text-amber-900 hover:bg-amber-100'
          : 'mt-4 rounded-md bg-red-800 px-4 py-2 text-sm font-medium text-white hover:bg-red-900'
      "
      @click="emit('retry')"
    >
      Reintentar
    </button>
  </div>
</template>
