<script setup lang="ts">
import WorkQueueRow from '@/components/work-queue/WorkQueueRow.vue'
import type { WorkQueueItem } from '@/types/workQueue'

defineProps<{
  items: WorkQueueItem[]
  nowMs: number
  dataNowMs: number
}>()
</script>

<template>
  <div class="overflow-x-auto rounded-lg border border-slate-200 bg-white shadow-sm">
    <table class="min-w-full border-collapse text-left" data-testid="work-queue-table">
      <caption class="sr-only">
        Cola de trabajo priorizada: tickets asignados al técnico, ordenados por
        prioridad y tiempo restante de SLA.
      </caption>
      <thead class="bg-slate-100 text-xs uppercase tracking-wide text-slate-700">
        <tr>
          <th scope="col" class="px-4 py-3 font-semibold">Ticket</th>
          <th scope="col" class="px-4 py-3 font-semibold">Título</th>
          <th scope="col" class="px-4 py-3 font-semibold">Categoría</th>
          <th scope="col" class="px-4 py-3 font-semibold">Prioridad</th>
          <th scope="col" class="px-4 py-3 font-semibold">Estado</th>
          <th scope="col" class="px-4 py-3 font-semibold">SLA</th>
        </tr>
      </thead>
      <tbody>
        <WorkQueueRow
          v-for="item in items"
          :key="item.id"
          :item="item"
          :now-ms="nowMs"
          :data-now-ms="dataNowMs"
        />
      </tbody>
    </table>
  </div>
</template>
