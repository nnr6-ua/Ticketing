<script setup lang="ts">
import { computed, onMounted, onUnmounted, watch } from 'vue'
import { storeToRefs } from 'pinia'
import { useRouter } from 'vue-router'

import WorkQueueEmptyState from '@/components/work-queue/WorkQueueEmptyState.vue'
import WorkQueueErrorState from '@/components/work-queue/WorkQueueErrorState.vue'
import WorkQueueFilters from '@/components/work-queue/WorkQueueFilters.vue'
import WorkQueuePagination from '@/components/work-queue/WorkQueuePagination.vue'
import WorkQueueSkeleton from '@/components/work-queue/WorkQueueSkeleton.vue'
import WorkQueueTable from '@/components/work-queue/WorkQueueTable.vue'
import { useSlaClock } from '@/composables/useSlaClock'
import { useWorkQueueStore } from '@/stores/workQueue'
import type { TicketStatus } from '@/types/workQueue'

const store = useWorkQueueStore()
const router = useRouter()
const clock = useSlaClock()

const {
  items,
  pagination,
  availableFilters,
  appliedFilters,
  loading,
  refreshing,
  error,
  lastUpdatedAt,
} = storeToRefs(store)

const nowMs = computed(() => clock.now.value)
const dataNowMs = computed(() => lastUpdatedAt.value ?? Date.now())

const isUnauthorized = computed(() => error.value?.kind === 'unauthorized')
const fatalError = computed(
  () => error.value !== null && items.value.length === 0 && !isUnauthorized.value,
)
const fatalVariant = computed(() =>
  error.value?.kind === 'forbidden' ? 'forbidden' : 'full',
)
const degraded = computed(() => store.degraded && !isUnauthorized.value)

const emptyVariant = computed<'no_assignments' | 'only_final' | 'no_results' | null>(
  () => {
    if (store.isEmptyQueue) {
      return 'no_assignments'
    }
    if (store.hasOnlyFinalized) {
      return 'only_final'
    }
    if (store.isNoResults) {
      return 'no_results'
    }
    return null
  },
)

function retry(): void {
  void store.fetchQueue()
}

function onStatuses(statuses: TicketStatus[]): void {
  store.setStatusFilter(statuses)
}

function onPriorities(levels: number[]): void {
  store.setPriorityFilter(levels)
}

function onClear(): void {
  store.clearFilters()
}

function onPageChange(page: number): void {
  store.setPage(page)
}

watch(error, (current) => {
  if (current?.kind === 'unauthorized') {
    void router.replace({ name: 'login', query: { redirect: '/cola-de-trabajo' } })
  }
})

watch(lastUpdatedAt, () => clock.resync())

onMounted(() => {
  store.start()
  clock.start()
})

onUnmounted(() => {
  store.stop()
  clock.stop()
})
</script>

<template>
  <main class="mx-auto max-w-7xl px-4 py-8">
    <header class="mb-6">
      <h1 class="text-2xl font-semibold tracking-tight text-slate-900">
        Cola de trabajo
      </h1>
      <p class="mt-1 text-sm text-slate-700">
        Tickets asignados a ti, ordenados por urgencia: prioridad y tiempo
        restante de SLA.
      </p>
    </header>

    <p
      v-if="isUnauthorized"
      class="rounded-lg border border-slate-300 bg-white p-6 text-sm text-slate-800"
      role="status"
    >
      Redirigiendo al inicio de sesión…
    </p>

    <template v-else>
      <WorkQueueFilters
        :status-options="availableFilters.statuses"
        :priority-options="availableFilters.priorities"
        :selected-statuses="appliedFilters.status"
        :selected-priorities="appliedFilters.priority"
        :result-count="pagination.total_items"
        :disabled="loading || refreshing"
        @update:statuses="onStatuses"
        @update:priorities="onPriorities"
        @clear="onClear"
      />

      <WorkQueueErrorState
        v-if="degraded && error"
        class="mt-4"
        variant="warning"
        @retry="retry"
      />

      <div class="mt-4">
        <WorkQueueErrorState
          v-if="fatalError && error"
          :variant="fatalVariant"
          :message="error.message"
          @retry="retry"
        />
        <WorkQueueSkeleton v-else-if="loading && items.length === 0" />
        <WorkQueueEmptyState
          v-else-if="emptyVariant"
          :variant="emptyVariant"
          @clear="onClear"
        />
        <WorkQueueTable
          v-else
          :items="items"
          :now-ms="nowMs"
          :data-now-ms="dataNowMs"
        />
      </div>

      <WorkQueuePagination
        v-if="pagination.total_pages > 1"
        class="mt-4"
        :pagination="pagination"
        :disabled="loading || refreshing"
        @change="onPageChange"
      />
    </template>
  </main>
</template>
