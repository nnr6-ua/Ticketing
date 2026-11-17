<script setup lang="ts">
import type {
  ConfigAction,
  ConfigEntityType,
  ConfigHistoryFilters,
  ConfigHistoryResponse,
  Pagination,
} from '@/types/adminConfiguration'

const props = defineProps<{
  response: ConfigHistoryResponse | null
  filters: ConfigHistoryFilters
  loading?: boolean
  error?: string | null
}>()

const emit = defineEmits<{
  (event: 'update:filters', value: ConfigHistoryFilters): void
  (event: 'retry'): void
}>()

const entityLabels: Record<ConfigEntityType, string> = {
  category: 'Categoría',
  priority: 'Prioridad',
  sla_rule: 'Regla SLA',
}

const actionLabels: Record<ConfigAction, string> = {
  create: 'Alta',
  update: 'Edición',
  deactivate: 'Desactivación',
  reactivate: 'Reactivación',
  delete: 'Eliminación',
  set_default: 'Predeterminada',
  rule_upsert: 'Regla guardada',
  rule_retire: 'Regla retirada',
}

function update(patch: Partial<ConfigHistoryFilters>): void {
  emit('update:filters', { ...props.filters, ...patch, page: patch.page ?? 1 })
}

function formatDate(value: string): string {
  return new Intl.DateTimeFormat('es-ES', {
    dateStyle: 'medium',
    timeStyle: 'short',
    timeZone: 'Europe/Madrid',
  }).format(new Date(value))
}

function formatValues(values: Record<string, unknown> | null): string[] {
  if (!values) return []
  return Object.entries(values).map(([key, value]) => {
    if (value === null || value === undefined) return `${key}: —`
    if (Array.isArray(value)) return `${key}: ${value.join(', ')}`
    return `${key}: ${String(value)}`
  })
}

function changePage(pagination: Pagination, page: number): void {
  if (page < 1 || page > pagination.total_pages) return
  update({ page })
}
</script>

<template>
  <section class="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
    <div class="flex flex-wrap items-end justify-between gap-3">
      <div>
        <h2 class="text-lg font-semibold text-slate-900">Histórico</h2>
        <p class="text-sm text-slate-600">Cambios de catálogos y reglas SLA.</p>
      </div>
      <button
        type="button"
        class="rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-sm font-semibold text-slate-700"
        @click="emit('update:filters', { page: 1, page_size: 25 })"
      >
        Limpiar filtros
      </button>
    </div>

    <div class="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-6">
      <div>
        <label for="history-from" class="block text-xs font-medium text-slate-700">Desde</label>
        <input
          id="history-from"
          type="date"
          :value="filters.from"
          class="mt-1 w-full rounded-lg border border-slate-300 px-2 py-1.5 text-sm"
          @change="update({ from: ($event.target as HTMLInputElement).value || undefined })"
        />
      </div>
      <div>
        <label for="history-to" class="block text-xs font-medium text-slate-700">Hasta</label>
        <input
          id="history-to"
          type="date"
          :value="filters.to"
          class="mt-1 w-full rounded-lg border border-slate-300 px-2 py-1.5 text-sm"
          @change="update({ to: ($event.target as HTMLInputElement).value || undefined })"
        />
      </div>
      <div>
        <label for="history-entity" class="block text-xs font-medium text-slate-700">Entidad</label>
        <select
          id="history-entity"
          :value="filters.entity_type ?? ''"
          class="mt-1 w-full rounded-lg border border-slate-300 px-2 py-1.5 text-sm"
          @change="update({ entity_type: (($event.target as HTMLSelectElement).value || undefined) as ConfigEntityType | undefined })"
        >
          <option value="">Todas</option>
          <option value="category">Categoría</option>
          <option value="priority">Prioridad</option>
          <option value="sla_rule">Regla SLA</option>
        </select>
      </div>
      <div>
        <label for="history-action" class="block text-xs font-medium text-slate-700">Acción</label>
        <select
          id="history-action"
          :value="filters.action ?? ''"
          class="mt-1 w-full rounded-lg border border-slate-300 px-2 py-1.5 text-sm"
          @change="update({ action: (($event.target as HTMLSelectElement).value || undefined) as ConfigAction | undefined })"
        >
          <option value="">Todas</option>
          <option v-for="(label, value) in actionLabels" :key="value" :value="value">
            {{ label }}
          </option>
        </select>
      </div>
      <div class="lg:col-span-2">
        <label for="history-version" class="block text-xs font-medium text-slate-700">
          Versión (ID)
        </label>
        <input
          id="history-version"
          type="text"
          :value="filters.configuration_version_id"
          class="mt-1 w-full rounded-lg border border-slate-300 px-2 py-1.5 text-sm"
          @change="update({ configuration_version_id: ($event.target as HTMLInputElement).value || undefined })"
        />
      </div>
    </div>

    <p v-if="error" role="alert" class="mt-4 rounded-xl border border-rose-300 bg-rose-50 p-3 text-sm text-rose-800">
      {{ error }}
      <button type="button" class="ml-2 font-semibold underline" @click="emit('retry')">
        Reintentar
      </button>
    </p>

    <div class="mt-4 overflow-x-auto">
      <table class="min-w-full divide-y divide-slate-200 text-sm">
        <caption class="sr-only">Histórico de cambios de configuración</caption>
        <thead class="bg-slate-50 text-left text-xs uppercase tracking-wide text-slate-600">
          <tr>
            <th scope="col" class="px-3 py-2">Fecha</th>
            <th scope="col" class="px-3 py-2">Autor</th>
            <th scope="col" class="px-3 py-2">Entidad</th>
            <th scope="col" class="px-3 py-2">Acción</th>
            <th scope="col" class="px-3 py-2">Valores anteriores</th>
            <th scope="col" class="px-3 py-2">Valores nuevos</th>
            <th scope="col" class="px-3 py-2">Versión</th>
          </tr>
        </thead>
        <tbody class="divide-y divide-slate-100">
          <tr v-if="loading">
            <td colspan="7" class="px-3 py-6">
              <div class="h-4 animate-pulse rounded bg-slate-100" />
            </td>
          </tr>
          <tr v-for="entry in response?.items ?? []" v-else :key="entry.id">
            <td class="whitespace-nowrap px-3 py-2 text-slate-700">
              {{ formatDate(entry.occurred_at) }}
            </td>
            <td class="px-3 py-2 text-slate-700">{{ entry.actor.name }}</td>
            <td class="px-3 py-2 text-slate-700">{{ entityLabels[entry.entity_type] }}</td>
            <td class="px-3 py-2 text-slate-700">{{ actionLabels[entry.action] }}</td>
            <td class="px-3 py-2 text-xs text-slate-600">
              <span v-if="!entry.previous_values">—</span>
              <ul v-else class="space-y-0.5">
                <li v-for="line in formatValues(entry.previous_values)" :key="line">{{ line }}</li>
              </ul>
            </td>
            <td class="px-3 py-2 text-xs text-slate-600">
              <span v-if="!entry.new_values">—</span>
              <ul v-else class="space-y-0.5">
                <li v-for="line in formatValues(entry.new_values)" :key="line">{{ line }}</li>
              </ul>
            </td>
            <td class="whitespace-nowrap px-3 py-2 text-slate-700">
              v{{ entry.configuration_version.version }}
            </td>
          </tr>
          <tr v-if="!loading && (response?.items.length ?? 0) === 0">
            <td colspan="7" class="px-3 py-8 text-center text-slate-600">
              No hay cambios para los filtros seleccionados.
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <nav
      v-if="response"
      class="mt-4 flex flex-wrap items-center justify-between gap-3"
      aria-label="Paginación del histórico"
    >
      <button
        type="button"
        class="rounded-md border border-slate-300 bg-white px-3 py-1.5 text-sm font-medium text-slate-800 disabled:opacity-50"
        :disabled="!response.pagination.has_previous"
        @click="changePage(response.pagination, response.pagination.page - 1)"
      >
        Anterior
      </button>
      <p class="text-sm text-slate-700">
        Página {{ response.pagination.page }} de {{ response.pagination.total_pages }}
      </p>
      <button
        type="button"
        class="rounded-md border border-slate-300 bg-white px-3 py-1.5 text-sm font-medium text-slate-800 disabled:opacity-50"
        :disabled="!response.pagination.has_next"
        @click="changePage(response.pagination, response.pagination.page + 1)"
      >
        Siguiente
      </button>
    </nav>
  </section>
</template>
