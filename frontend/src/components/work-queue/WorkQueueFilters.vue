<script setup lang="ts">
import type {
  PriorityFilterOption,
  StatusFilterOption,
  TicketStatus,
} from '@/types/workQueue'

const props = defineProps<{
  statusOptions: StatusFilterOption[]
  priorityOptions: PriorityFilterOption[]
  selectedStatuses: TicketStatus[]
  selectedPriorities: number[]
  resultCount: number
  disabled: boolean
}>()

const emit = defineEmits<{
  (event: 'update:statuses', value: TicketStatus[]): void
  (event: 'update:priorities', value: number[]): void
  (event: 'clear'): void
}>()

function toggleStatus(value: TicketStatus, event: Event): void {
  const checked = (event.target as HTMLInputElement).checked
  const next = checked
    ? [...props.selectedStatuses, value]
    : props.selectedStatuses.filter((status) => status !== value)
  emit('update:statuses', next)
}

function togglePriority(level: number, event: Event): void {
  const checked = (event.target as HTMLInputElement).checked
  const next = checked
    ? [...props.selectedPriorities, level]
    : props.selectedPriorities.filter((value) => value !== level)
  emit('update:priorities', next)
}
</script>

<template>
  <section
    class="rounded-lg border border-slate-200 bg-white p-4 shadow-sm"
    aria-label="Filtros de la cola de trabajo"
    data-testid="work-queue-filters"
  >
    <div class="flex flex-wrap items-center justify-between gap-3">
      <h2 class="text-sm font-semibold uppercase tracking-wide text-slate-700">
        Filtros
      </h2>
      <p class="text-sm text-slate-700" aria-live="polite" data-testid="result-count">
        {{ resultCount }} {{ resultCount === 1 ? 'ticket' : 'tickets' }}
      </p>
    </div>

    <div class="mt-4 grid gap-4 lg:grid-cols-2">
      <fieldset :disabled="disabled">
        <legend class="text-sm font-semibold text-slate-900">Estado</legend>
        <div class="mt-2 flex flex-wrap gap-2">
          <label
            v-for="option in statusOptions"
            :key="option.value"
            :for="`filtro-estado-${option.value}`"
            class="cursor-pointer"
          >
            <input
              :id="`filtro-estado-${option.value}`"
              type="checkbox"
              class="peer sr-only"
              :checked="selectedStatuses.includes(option.value)"
              :disabled="disabled"
              @change="toggleStatus(option.value, $event)"
            />
            <span
              class="inline-flex items-center rounded-full border border-slate-300 bg-white px-3 py-1 text-sm text-slate-800 peer-checked:border-slate-900 peer-checked:bg-slate-900 peer-checked:text-white peer-focus-visible:ring-2 peer-focus-visible:ring-sky-700 peer-focus-visible:ring-offset-2 peer-disabled:opacity-60"
            >
              {{ option.label }}
              <span v-if="option.is_final" class="ml-1 text-xs">(final)</span>
            </span>
          </label>
        </div>
      </fieldset>

      <fieldset :disabled="disabled">
        <legend class="text-sm font-semibold text-slate-900">Prioridad</legend>
        <div class="mt-2 flex flex-wrap gap-2">
          <label
            v-for="option in priorityOptions"
            :key="option.level"
            :for="`filtro-prioridad-${option.level}`"
            class="cursor-pointer"
          >
            <input
              :id="`filtro-prioridad-${option.level}`"
              type="checkbox"
              class="peer sr-only"
              :checked="selectedPriorities.includes(option.level)"
              :disabled="disabled"
              @change="togglePriority(option.level, $event)"
            />
            <span
              class="inline-flex items-center rounded-full border border-slate-300 bg-white px-3 py-1 text-sm text-slate-800 peer-checked:border-slate-900 peer-checked:bg-slate-900 peer-checked:text-white peer-focus-visible:ring-2 peer-focus-visible:ring-sky-700 peer-focus-visible:ring-offset-2 peer-disabled:opacity-60"
            >
              {{ option.name }}
              <span v-if="!option.is_active" class="ml-1 text-xs"
                >(inactiva)</span
              >
            </span>
          </label>
          <span v-if="priorityOptions.length === 0" class="text-sm text-slate-600">
            No hay prioridades en tu cola.
          </span>
        </div>
      </fieldset>
    </div>

    <div class="mt-4">
      <button
        type="button"
        class="rounded-md border border-slate-300 bg-white px-3 py-1.5 text-sm font-medium text-slate-800 hover:bg-slate-100 disabled:cursor-not-allowed disabled:opacity-60"
        :disabled="disabled"
        @click="emit('clear')"
      >
        Limpiar filtros
      </button>
    </div>
  </section>
</template>
