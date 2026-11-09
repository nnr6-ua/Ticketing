<script setup lang="ts">
import { computed } from 'vue'

type EmptyVariant = 'no_assignments' | 'only_final' | 'no_results'

const props = defineProps<{ variant: EmptyVariant }>()

const emit = defineEmits<{ (event: 'clear'): void }>()

const content = computed(() => {
  if (props.variant === 'only_final') {
    return {
      title: 'No tienes tickets activos',
      body: 'Solo tienes tickets finalizados. Usa el filtro de estado para consultarlos.',
    }
  }
  if (props.variant === 'no_results') {
    return {
      title: 'No hay resultados para los filtros seleccionados',
      body: 'Prueba con otros estados o prioridades, o limpia los filtros.',
    }
  }
  return {
    title: 'No tienes tickets asignados actualmente',
    body: 'Cuando te asignen un ticket aparecerá en esta cola.',
  }
})
</script>

<template>
  <div
    class="rounded-lg border border-dashed border-slate-300 bg-white p-10 text-center"
    data-testid="work-queue-empty"
    :data-variant="variant"
  >
    <h2 class="text-lg font-semibold text-slate-900">{{ content.title }}</h2>
    <p class="mt-2 text-sm text-slate-700">{{ content.body }}</p>
    <button
      v-if="variant === 'no_results'"
      type="button"
      class="mt-4 rounded-md bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:bg-slate-700"
      @click="emit('clear')"
    >
      Limpiar filtros
    </button>
  </div>
</template>
