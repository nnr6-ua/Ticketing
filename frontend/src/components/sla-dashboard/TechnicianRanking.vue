<script setup lang="ts">
import { computed } from 'vue'

import type { RankingEntry } from '@/types/slaDashboard'
import { formatCount, formatDurationEs } from '@/utils/format'

const props = defineProps<{
  ranking: {
    technicians: RankingEntry[]
    unassigned: RankingEntry | null
    overdue_total: number
  }
}>()

interface RankedRow {
  entry: RankingEntry
  position: number | null
  isUnassigned: boolean
}

const rows = computed<RankedRow[]>(() => {
  const ranked: RankedRow[] = props.ranking.technicians.map((entry, index) => ({
    entry,
    position: index + 1,
    isUnassigned: false,
  }))
  if (props.ranking.unassigned) {
    ranked.push({
      entry: props.ranking.unassigned,
      position: null,
      isUnassigned: true,
    })
  }
  return ranked
})

const isEmpty = computed(() => rows.value.length === 0)
</script>

<template>
  <section
    class="overflow-hidden rounded-lg border border-slate-200 bg-white shadow-sm"
    aria-labelledby="technician-ranking-title"
    data-testid="technician-ranking"
  >
    <div class="flex flex-wrap items-baseline justify-between gap-2 border-b border-slate-200 p-4">
      <h2 id="technician-ranking-title" class="text-lg font-semibold text-slate-900">
        Técnicos con más tickets vencidos
      </h2>
      <p class="text-sm text-slate-700">
        Total de vencidos:
        <span class="font-semibold tabular-nums">{{ formatCount(ranking.overdue_total) }}</span>
      </p>
    </div>

    <p
      v-if="isEmpty"
      class="p-6 text-sm text-slate-700"
      role="status"
      data-testid="technician-ranking-empty"
    >
      No hay tickets vencidos en el periodo seleccionado.
    </p>

    <div v-else class="overflow-x-auto" aria-live="polite">
      <table class="min-w-full divide-y divide-slate-200 text-left text-sm">
        <caption class="sr-only">
          Ranking de técnicos por número de tickets vencidos. La fila «Sin
          asignar» se muestra al final y agrupa los tickets sin responsable.
        </caption>
        <thead class="bg-slate-50">
          <tr>
            <th scope="col" class="px-4 py-3 font-semibold text-slate-800">
              Posición
            </th>
            <th scope="col" class="px-4 py-3 font-semibold text-slate-800">
              Técnico
            </th>
            <th scope="col" class="px-4 py-3 font-semibold text-slate-800">
              Equipo
            </th>
            <th scope="col" class="px-4 py-3 text-right font-semibold text-slate-800">
              Vencidos
            </th>
            <th scope="col" class="px-4 py-3 text-right font-semibold text-slate-800">
              Retraso medio
            </th>
          </tr>
        </thead>
        <tbody class="divide-y divide-slate-100">
          <tr
            v-for="row in rows"
            :key="row.entry.technician_id ?? 'sin-asignar'"
            :class="row.isUnassigned ? 'border-t-2 border-slate-300 bg-slate-50' : ''"
            :data-unassigned="row.isUnassigned ? 'true' : undefined"
          >
            <td class="px-4 py-3 tabular-nums text-slate-700">
              {{ row.position ?? '—' }}
            </td>
            <th scope="row" class="px-4 py-3 font-medium text-slate-900">
              {{ row.entry.technician_name }}
              <template v-if="row.entry.is_active === false">
                <span class="text-slate-600">(inactivo)</span>
              </template>
            </th>
            <td class="px-4 py-3 text-slate-700">
              {{ row.entry.team ?? 'Sin equipo' }}
            </td>
            <td class="px-4 py-3 text-right font-semibold tabular-nums text-red-700">
              {{ formatCount(row.entry.overdue_count) }}
            </td>
            <td class="px-4 py-3 text-right tabular-nums text-slate-700">
              {{ formatDurationEs(row.entry.avg_delay_seconds) }}
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </section>
</template>
