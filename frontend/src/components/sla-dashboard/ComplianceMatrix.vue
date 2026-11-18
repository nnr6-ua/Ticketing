<script setup lang="ts">
import { computed } from 'vue'

import MatrixCell from '@/components/sla-dashboard/MatrixCell.vue'
import type {
  ComplianceMetrics,
  MatrixRow,
  TotalsEntry,
} from '@/types/slaDashboard'

const props = defineProps<{
  matrix: MatrixRow[]
  priorityTotals: TotalsEntry[]
  categoryTotals: TotalsEntry[]
  summary: ComplianceMetrics
}>()

const priorityRows = computed(() =>
  [...props.priorityTotals].sort(
    (left, right) =>
      (left.priority_level ?? 0) - (right.priority_level ?? 0),
  ),
)

const categoryColumns = computed(() =>
  [...props.categoryTotals].sort((left, right) => {
    const leftNull = left.category_id === null ? 1 : 0
    const rightNull = right.category_id === null ? 1 : 0
    if (leftNull !== rightNull) {
      return leftNull - rightNull
    }
    return (left.category_name ?? '').localeCompare(
      right.category_name ?? '',
      'es',
      { sensitivity: 'base' },
    )
  }),
)

function cellFor(
  priorityLevel: number,
  categoryId: string | null,
): MatrixRow | undefined {
  return props.matrix.find(
    (row) =>
      row.priority_level === priorityLevel && row.category_id === categoryId,
  )
}

function priorityTotalFor(priorityLevel: number): TotalsEntry | undefined {
  return props.priorityTotals.find(
    (row) => row.priority_level === priorityLevel,
  )
}

function priorityLabel(row: TotalsEntry): string {
  const name = row.priority_name ?? `Prioridad ${row.priority_level ?? ''}`
  return row.priority_is_active === false ? `${name} (inactiva)` : name
}

function categoryLabel(row: TotalsEntry): string {
  const name = row.category_name ?? 'Sin categoría'
  return row.category_is_active === false ? `${name} (inactiva)` : name
}

const rows = computed(() =>
  priorityRows.value.map((priority) => ({
    priority,
    level: priority.priority_level ?? 0,
    cells: categoryColumns.value.map(
      (column) => cellFor(priority.priority_level ?? 0, column.category_id) ?? null,
    ),
    total: priorityTotalFor(priority.priority_level ?? 0) ?? null,
  })),
)
</script>

<template>
  <section
    class="overflow-hidden rounded-lg border border-slate-200 bg-white shadow-sm"
    aria-labelledby="compliance-matrix-title"
    data-testid="compliance-matrix"
  >
    <div class="border-b border-slate-200 p-4">
      <h2
        id="compliance-matrix-title"
        class="text-lg font-semibold text-slate-900"
      >
        Cumplimiento por prioridad y categoría
      </h2>
    </div>

    <div class="overflow-x-auto">
      <table class="min-w-full divide-y divide-slate-200 text-left text-sm">
        <caption class="sr-only">
          Matriz de cumplimiento de SLA por prioridad y categoría. Las celdas
          vacías indican que no hay tickets para esa combinación.
        </caption>
        <thead class="bg-slate-50">
          <tr>
            <th
              scope="col"
              class="whitespace-nowrap px-4 py-3 font-semibold text-slate-800"
            >
              Prioridad
            </th>
            <th
              v-for="column in categoryColumns"
              :key="column.category_id ?? 'sin-categoria'"
              scope="col"
              class="whitespace-nowrap px-4 py-3 font-semibold text-slate-800"
            >
              {{ categoryLabel(column) }}
            </th>
            <th
              scope="col"
              class="whitespace-nowrap bg-slate-100 px-4 py-3 font-semibold text-slate-900"
            >
              Total
            </th>
          </tr>
        </thead>
        <tbody class="divide-y divide-slate-100">
          <tr
            v-for="entry in rows"
            :key="entry.level || entry.priority.priority_name || 'prioridad'"
            :data-priority-level="entry.level"
          >
            <th scope="row" class="whitespace-nowrap px-4 py-3 align-top font-semibold text-slate-900">
              {{ priorityLabel(entry.priority) }}
            </th>
            <td
              v-for="(cell, index) in entry.cells"
              :key="categoryColumns[index]?.category_id ?? 'sin-categoria'"
              class="px-4 py-3 align-top"
            >
              <MatrixCell v-if="cell" :metrics="cell" />
              <span v-else class="text-slate-400">
                <span class="sr-only">Sin datos</span>
                <span aria-hidden="true">—</span>
              </span>
            </td>
            <td class="bg-slate-50 px-4 py-3 align-top">
              <MatrixCell v-if="entry.total" :metrics="entry.total" />
            </td>
          </tr>
        </tbody>
        <tfoot class="border-t-2 border-slate-300 bg-slate-100">
          <tr>
            <th scope="row" class="whitespace-nowrap px-4 py-3 font-semibold text-slate-900">
              Total
            </th>
            <td
              v-for="column in categoryColumns"
              :key="column.category_id ?? 'sin-categoria'"
              class="px-4 py-3 align-top"
            >
              <MatrixCell :metrics="column" />
            </td>
            <td class="px-4 py-3 align-top">
              <MatrixCell :metrics="summary" />
            </td>
          </tr>
        </tfoot>
      </table>
    </div>
  </section>
</template>
