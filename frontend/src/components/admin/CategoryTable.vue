<script setup lang="ts">
import type { CategoryAdmin } from '@/types/adminConfiguration'

defineProps<{
  items: CategoryAdmin[]
  loading?: boolean
  disabled?: boolean
}>()

const emit = defineEmits<{
  (event: 'create'): void
  (event: 'edit', item: CategoryAdmin): void
  (event: 'toggle', item: CategoryAdmin): void
  (event: 'delete', item: CategoryAdmin): void
}>()
</script>

<template>
  <section class="rounded-2xl border border-slate-200 bg-white shadow-sm">
    <div class="flex flex-wrap items-center justify-between gap-3 border-b border-slate-200 p-4">
      <div>
        <h2 class="text-lg font-semibold text-slate-900">Categorías</h2>
        <p class="text-sm text-slate-600">Clasificación de las incidencias.</p>
      </div>
      <button
        type="button"
        class="rounded-lg bg-sky-600 px-4 py-2 text-sm font-semibold text-white shadow-sm hover:bg-sky-700 disabled:opacity-60"
        :disabled="disabled"
        @click="emit('create')"
      >
        Nueva categoría
      </button>
    </div>

    <div class="overflow-x-auto">
      <table class="min-w-full divide-y divide-slate-200 text-sm">
        <caption class="sr-only">Categorías configuradas</caption>
        <thead class="bg-slate-50 text-left text-xs uppercase tracking-wide text-slate-600">
          <tr>
            <th scope="col" class="px-4 py-3">Nombre</th>
            <th scope="col" class="px-4 py-3">Descripción</th>
            <th scope="col" class="px-4 py-3">Palabras clave</th>
            <th scope="col" class="px-4 py-3">Orden</th>
            <th scope="col" class="px-4 py-3">Estado</th>
            <th scope="col" class="px-4 py-3">Tickets</th>
            <th scope="col" class="px-4 py-3">Reglas</th>
            <th scope="col" class="px-4 py-3">Acciones</th>
          </tr>
        </thead>
        <tbody class="divide-y divide-slate-100">
          <tr v-if="loading">
            <td colspan="8" class="px-4 py-6">
              <div class="h-4 animate-pulse rounded bg-slate-100" />
            </td>
          </tr>
          <tr v-for="item in items" v-else :key="item.id">
            <th scope="row" class="whitespace-nowrap px-4 py-3 text-left font-medium text-slate-900">
              {{ item.name }}
            </th>
            <td class="max-w-xs px-4 py-3 text-slate-700">
              {{ item.description || '—' }}
            </td>
            <td class="px-4 py-3">
              <div class="flex flex-wrap gap-1">
                <span
                  v-for="keyword in item.keywords"
                  :key="keyword"
                  class="rounded-full bg-slate-100 px-2 py-0.5 text-xs text-slate-700"
                >
                  {{ keyword }}
                </span>
                <span v-if="item.keywords.length === 0" class="text-slate-400">—</span>
              </div>
            </td>
            <td class="px-4 py-3 text-slate-700">{{ item.sort_order }}</td>
            <td class="px-4 py-3">
              <span
                class="rounded-full px-2 py-0.5 text-xs font-medium"
                :class="
                  item.is_active
                    ? 'bg-emerald-50 text-emerald-800'
                    : 'bg-slate-100 text-slate-600'
                "
              >
                {{ item.is_active ? 'Activa' : 'Inactiva' }}
              </span>
              <span
                v-if="item.is_system"
                class="ml-1 rounded-full bg-amber-50 px-2 py-0.5 text-xs text-amber-800"
              >
                Sistema
              </span>
              <span
                v-if="item.is_default"
                class="ml-1 rounded-full bg-sky-50 px-2 py-0.5 text-xs text-sky-800"
              >
                Predeterminada
              </span>
            </td>
            <td class="px-4 py-3 text-slate-700">{{ item.ticket_count }}</td>
            <td class="px-4 py-3 text-slate-700">{{ item.rule_count }}</td>
            <td class="px-4 py-3">
              <div v-if="!item.is_system" class="flex flex-wrap gap-2">
                <button
                  type="button"
                  class="text-sm font-medium text-sky-700 hover:text-sky-900 disabled:opacity-50"
                  :aria-label="`Editar ${item.name}`"
                  :disabled="disabled"
                  @click="emit('edit', item)"
                >
                  Editar
                </button>
                <button
                  type="button"
                  class="text-sm font-medium text-slate-700 hover:text-slate-900 disabled:opacity-50"
                  :aria-label="`${item.is_active ? 'Desactivar' : 'Reactivar'} ${item.name}`"
                  :disabled="disabled"
                  @click="emit('toggle', item)"
                >
                  {{ item.is_active ? 'Desactivar' : 'Reactivar' }}
                </button>
                <button
                  type="button"
                  class="text-sm font-medium text-rose-700 hover:text-rose-900 disabled:cursor-not-allowed disabled:opacity-50"
                  :aria-label="`Eliminar ${item.name}`"
                  :title="
                    item.can_delete
                      ? undefined
                      : 'No se puede eliminar: es predeterminada, de sistema o tiene tickets o reglas.'
                  "
                  :disabled="disabled || !item.can_delete"
                  @click="emit('delete', item)"
                >
                  Eliminar
                </button>
              </div>
              <span v-else class="text-xs text-slate-500">Sistema</span>
            </td>
          </tr>
          <tr v-if="!loading && items.length === 0">
            <td colspan="8" class="px-4 py-8 text-center text-slate-600">
              Todavía no hay categorías configuradas.
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </section>
</template>
