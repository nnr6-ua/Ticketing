<script setup lang="ts">
import { computed } from 'vue'

import type { StatusOption, TicketStatus } from '@/types/ticketWorkflow'

const props = withDefaults(
  defineProps<{
    currentStatus: TicketStatus
    options: StatusOption[]
    disabled?: boolean
  }>(),
  { disabled: false },
)

const emit = defineEmits<{
  select: [value: TicketStatus]
}>()

const STATUS_LABELS: Record<TicketStatus, string> = {
  abierto: 'Abierto',
  en_progreso: 'En progreso',
  pendiente_usuario: 'Pendiente de usuario',
  resuelto: 'Resuelto',
  cerrado: 'Cerrado',
}

// El backend ya excluye el estado actual; se filtra también aquí para no
// ofrecer nunca un destino redundante si la vista recibe datos incompletos.
const availableOptions = computed(() =>
  props.options.filter((option) => option.value !== props.currentStatus),
)

const currentLabel = computed(
  () =>
    props.options.find((option) => option.value === props.currentStatus)?.label ??
    STATUS_LABELS[props.currentStatus],
)

function onChange(value: TicketStatus): void {
  emit('select', value)
}
</script>

<template>
  <section aria-labelledby="ticket-status-heading">
    <h2 id="ticket-status-heading" class="text-base font-semibold text-slate-900">
      Estado del ticket
    </h2>
    <p class="mt-1 text-sm text-slate-700">
      Estado actual: <span class="font-medium">{{ currentLabel }}</span>
    </p>

    <fieldset
      v-if="availableOptions.length > 0"
      class="mt-4 rounded-lg border border-slate-200 p-4"
      :class="{ 'opacity-50': disabled }"
      :disabled="disabled"
      aria-describedby="ticket-status-help"
    >
      <legend class="px-1 text-sm font-medium text-slate-900">Nuevo estado</legend>
      <p id="ticket-status-help" class="mb-3 text-sm text-slate-600">
        Elige el estado al que quieres mover el ticket.
      </p>
      <div class="space-y-2">
        <label
          v-for="option in availableOptions"
          :key="option.value"
          class="flex cursor-pointer items-center gap-3 rounded-md px-2 py-1 focus-within:bg-slate-50"
        >
          <input
            type="radio"
            name="ticket-status"
            :value="option.value"
            :disabled="disabled"
            class="h-4 w-4 border-slate-400 text-slate-900 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-slate-900 focus-visible:ring-offset-2"
            @change="onChange(option.value)"
          />
          <span class="text-sm text-slate-800">{{ option.label }}</span>
        </label>
      </div>
    </fieldset>

    <p
      v-else
      class="mt-4 rounded-lg border border-slate-200 bg-slate-50 p-4 text-sm text-slate-700"
    >
      No hay cambios de estado disponibles.
    </p>
  </section>
</template>
