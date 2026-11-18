<script setup lang="ts">
import { computed } from 'vue'

const props = withDefaults(
  defineProps<{
    variant?: 'full' | 'warning' | 'forbidden'
    message?: string
    onRetry?: () => void
  }>(),
  { variant: 'full', message: undefined, onRetry: undefined },
)

const emit = defineEmits<{ (event: 'retry'): void }>()

const title = computed(() => {
  if (props.variant === 'forbidden') {
    return 'No tienes permiso para acceder a este dashboard'
  }
  if (props.variant === 'warning') {
    return 'No se pudieron actualizar los datos'
  }
  return 'No se pudo cargar el dashboard'
})

const body = computed(() => {
  if (props.variant === 'forbidden') {
    return 'No tienes permiso para acceder a este dashboard.'
  }
  if (props.variant === 'warning') {
    return 'No se pudieron actualizar los datos. Se muestran los últimos datos disponibles.'
  }
  return props.message ?? 'No se pudo cargar el dashboard. Inténtalo de nuevo.'
})

const showRetry = computed(() => props.variant !== 'forbidden')

function retry(): void {
  emit('retry')
}
</script>

<template>
  <div
    :class="
      variant === 'warning'
        ? 'rounded-md border border-amber-300 bg-amber-50 p-4'
        : 'rounded-lg border border-red-300 bg-red-50 p-10 text-center'
    "
    :role="variant === 'warning' ? 'status' : 'alert'"
    data-testid="sla-dashboard-error"
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
      v-if="showRetry"
      type="button"
      :class="
        variant === 'warning'
          ? 'mt-2 rounded-md border border-amber-400 bg-white px-3 py-1.5 text-sm font-medium text-amber-900 hover:bg-amber-100'
          : 'mt-4 rounded-md bg-red-800 px-4 py-2 text-sm font-medium text-white hover:bg-red-900'
      "
      @click="retry"
    >
      Reintentar
    </button>
  </div>
</template>
