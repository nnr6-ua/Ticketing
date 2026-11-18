<script setup lang="ts">
import { computed } from 'vue'

type EmptyVariant = 'periodo' | 'filtros' | 'sin-sla' | 'sin-vencidos'

const props = withDefaults(
  defineProps<{
    variant: EmptyVariant
    onAction?: () => void
  }>(),
  { onAction: undefined },
)

const emit = defineEmits<{ (event: 'action'): void }>()

const content = computed<{
  title: string
  body: string
  actionLabel: string | null
}>(() => {
  switch (props.variant) {
    case 'filtros':
      return {
        title: 'No hay resultados para los filtros seleccionados',
        body: 'Prueba con otras categorías o prioridades, o limpia los filtros.',
        actionLabel: 'Limpiar filtros',
      }
    case 'sin-sla':
      return {
        title: 'No hay tickets con SLA en el periodo seleccionado',
        body: 'Todos los tickets del periodo carecen de límite de SLA, por lo que no se puede calcular el cumplimiento.',
        actionLabel: null,
      }
    case 'sin-vencidos':
      return {
        title: 'No hay tickets vencidos en el periodo seleccionado',
        body: 'Ningún ticket del periodo ha superado su límite de SLA.',
        actionLabel: null,
      }
    default:
      return {
        title: 'No hay tickets en el periodo seleccionado',
        body: 'Prueba con un rango de fechas más amplio.',
        actionLabel: 'Ampliar fechas',
      }
  }
})

function runAction(): void {
  emit('action')
}
</script>

<template>
  <div
    class="rounded-lg border border-dashed border-slate-300 bg-white p-10 text-center"
    role="status"
    data-testid="sla-dashboard-empty"
    :data-variant="variant"
  >
    <h2 class="text-lg font-semibold text-slate-900">{{ content.title }}</h2>
    <p class="mt-2 text-sm text-slate-700">{{ content.body }}</p>
    <button
      v-if="content.actionLabel"
      type="button"
      class="mt-4 rounded-md bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:bg-slate-700 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-slate-900 focus-visible:ring-offset-2"
      @click="runAction"
    >
      {{ content.actionLabel }}
    </button>
  </div>
</template>
