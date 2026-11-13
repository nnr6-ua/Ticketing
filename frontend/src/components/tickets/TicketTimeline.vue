<script setup lang="ts">
import { computed } from 'vue'

import type { Pagination, TicketStatus, TimelineEntry } from '@/types/ticketWorkflow'

const props = withDefaults(
  defineProps<{
    entries: TimelineEntry[]
    canSeeInternal: boolean
    loading?: boolean
    pagination?: Pagination | null
  }>(),
  { loading: false },
)

const emit = defineEmits<{
  (e: 'page-change', page: number): void
}>()

function previousPage(): void {
  if (props.pagination?.has_previous) {
    emit('page-change', props.pagination.page - 1)
  }
}

function nextPage(): void {
  if (props.pagination?.has_next) {
    emit('page-change', props.pagination.page + 1)
  }
}

const STATUS_LABELS: Record<TicketStatus, string> = {
  abierto: 'Abierto',
  en_progreso: 'En progreso',
  pendiente_usuario: 'Pendiente de usuario',
  resuelto: 'Resuelto',
  cerrado: 'Cerrado',
}

const dateFormatter = new Intl.DateTimeFormat('es-ES', {
  dateStyle: 'medium',
  timeStyle: 'short',
  timeZone: 'Europe/Madrid',
})

function statusLabel(status: TicketStatus | null): string {
  return status ? STATUS_LABELS[status] : ''
}

function formatDate(value: string): string {
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? value : dateFormatter.format(date)
}

// El backend ya filtra las entradas internas; se vuelve a aplicar la regla en
// el cliente para no renderizar datos internos si llegasen por error.
const visibleEntries = computed(() =>
  props.entries.filter((entry) => !entry.is_internal || props.canSeeInternal),
)

// Reapertura: `status_change` de `resuelto` a `en_progreso`. Las resoluciones
// anteriores a la última reapertura se identifican como históricas sin alterar
// el orden ni el texto recibidos.
const historicalResolutionIds = computed(() => {
  let lastReopenIndex = -1
  props.entries.forEach((entry, index) => {
    if (
      entry.type === 'status_change' &&
      entry.from_status === 'resuelto' &&
      entry.to_status === 'en_progreso'
    ) {
      lastReopenIndex = index
    }
  })

  if (lastReopenIndex < 0) {
    return new Set<string>()
  }

  return new Set(
    props.entries
      .filter((entry, index) => index < lastReopenIndex && entry.type === 'resolution')
      .map((entry) => entry.id),
  )
})

function isHistoricalResolution(entryId: string): boolean {
  return historicalResolutionIds.value.has(entryId)
}
</script>

<template>
  <section aria-labelledby="ticket-timeline-heading">
    <h2 id="ticket-timeline-heading" class="text-base font-semibold text-slate-900">
      Actividad del ticket
    </h2>

    <p
      v-if="loading"
      role="status"
      class="mt-4 rounded-lg border border-slate-200 bg-white p-4 text-sm text-slate-700"
    >
      Cargando la línea temporal…
    </p>

    <p
      v-else-if="visibleEntries.length === 0"
      role="status"
      class="mt-4 rounded-lg border border-slate-200 bg-white p-4 text-sm text-slate-700"
    >
      Todavía no hay actividad en este ticket.
    </p>

    <ol v-else class="mt-4 space-y-3">
      <li
        v-for="entry in visibleEntries"
        :key="entry.id"
        class="rounded-lg border p-4"
        :class="
          entry.type === 'resolution'
            ? 'border-emerald-200 bg-emerald-50 text-emerald-800'
            : entry.type === 'internal_comment'
              ? 'border-amber-200 bg-amber-50 text-amber-800'
              : 'border-slate-200 bg-white text-slate-800'
        "
        :data-entry-type="entry.type"
      >
        <div class="flex flex-wrap items-start justify-between gap-2">
          <div class="min-w-0">
            <template v-if="entry.type === 'created'">
              <span
                class="inline-flex rounded-full bg-sky-50 px-2 py-0.5 text-xs font-medium text-sky-800"
              >
                Ticket creado
              </span>
              <p class="mt-2 text-sm">
                {{ entry.author.name }} creó el ticket.
              </p>
            </template>

            <template v-else-if="entry.type === 'status_change'">
              <span
                class="inline-flex rounded-full bg-slate-100 px-2 py-0.5 text-xs font-medium text-slate-700"
              >
                Cambio de estado
              </span>
              <p class="mt-2 text-sm">
                {{ entry.author.name }} cambió el estado de
                {{ statusLabel(entry.from_status) }} a
                {{ statusLabel(entry.to_status) }}.
              </p>
            </template>

            <template v-else-if="entry.type === 'resolution'">
              <span
                class="inline-flex rounded-full bg-emerald-50 px-2 py-0.5 text-xs font-medium text-emerald-800"
              >
                Resolución
              </span>
              <span
                v-if="isHistoricalResolution(entry.id)"
                class="ml-2 inline-flex rounded-full bg-slate-100 px-2 py-0.5 text-xs font-medium text-slate-700"
                data-historical-resolution="true"
              >
                Histórica
              </span>
              <p class="mt-2 whitespace-pre-wrap break-words text-sm">
                {{ entry.body }}
              </p>
            </template>

            <template v-else>
              <span
                class="inline-flex rounded-full bg-amber-50 px-2 py-0.5 text-xs font-medium text-amber-800"
              >
                Interno
              </span>
              <p class="mt-2 whitespace-pre-wrap break-words text-sm">
                {{ entry.body }}
              </p>
            </template>
          </div>
          <time
            :datetime="entry.created_at"
            class="shrink-0 text-xs text-slate-600"
          >
            {{ formatDate(entry.created_at) }}
          </time>
        </div>
        <p class="mt-2 text-xs text-slate-600">{{ entry.author.name }}</p>
      </li>
    </ol>

    <div
      v-if="pagination && pagination.total_items > 0"
      class="mt-4 flex items-center justify-between gap-2 px-4"
    >
      <button
        type="button"
        :disabled="!pagination.has_previous"
        class="px-3 py-1.5 rounded-md text-sm font-medium text-slate-600 bg-white border border-slate-200 hover:bg-slate-50 disabled:opacity-50 disabled:cursor-not-allowed focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-slate-900 focus-visible:ring-offset-2"
        @click="previousPage"
      >
        Anterior
      </button>
      <span class="text-sm text-slate-600">
        Página {{ pagination.page }} de {{ pagination.total_pages }}
      </span>
      <button
        type="button"
        :disabled="!pagination.has_next"
        class="px-3 py-1.5 rounded-md text-sm font-medium text-slate-600 bg-white border border-slate-200 hover:bg-slate-50 disabled:opacity-50 disabled:cursor-not-allowed focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-slate-900 focus-visible:ring-offset-2"
        @click="nextPage"
      >
        Siguiente
      </button>
    </div>
  </section>
</template>
