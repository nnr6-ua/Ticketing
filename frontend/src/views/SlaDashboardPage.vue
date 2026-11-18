<script setup lang="ts">
import { computed, onMounted, onUnmounted } from 'vue'
import { storeToRefs } from 'pinia'

import ComplianceMatrix from '@/components/sla-dashboard/ComplianceMatrix.vue'
import DashboardEmptyState from '@/components/sla-dashboard/DashboardEmptyState.vue'
import DashboardErrorState from '@/components/sla-dashboard/DashboardErrorState.vue'
import SemaphoreLegend from '@/components/sla-dashboard/SemaphoreLegend.vue'
import SlaDashboardFilters from '@/components/sla-dashboard/SlaDashboardFilters.vue'
import SlaDashboardSkeleton from '@/components/sla-dashboard/SlaDashboardSkeleton.vue'
import SlaSummary from '@/components/sla-dashboard/SlaSummary.vue'
import TechnicianRanking from '@/components/sla-dashboard/TechnicianRanking.vue'
import { useSlaDashboardStore } from '@/stores/slaDashboard'
import type { SlaDashboardFilters as DashboardFilters } from '@/types/slaDashboard'
import { formatMadridDateTime } from '@/utils/format'

const store = useSlaDashboardStore()

const {
  data,
  meta,
  options,
  loading,
  updating,
  error,
  stale,
  effectiveFilters,
  emptyVariant,
  hasOnlyNoSla,
} = storeToRefs(store)

const isUnauthorized = computed(() => error.value?.kind === 'unauthorized')
const isForbidden = computed(() => error.value?.kind === 'forbidden')
const fatalError = computed(
  () =>
    error.value !== null &&
    !isUnauthorized.value &&
    (data.value === null || isForbidden.value),
)
const fatalVariant = computed(() => (isForbidden.value ? 'forbidden' : 'full'))
const degraded = computed(
  () => stale.value && error.value !== null && data.value !== null,
)
const showSkeleton = computed(() => loading.value && data.value === null)

const lastUpdated = computed(() =>
  meta.value ? formatMadridDateTime(meta.value.generated_at) : null,
)

function retry(): void {
  // Con datos previos el reintento es silencioso y conserva la instantánea.
  void store.refresh()
}

function retryFatal(): void {
  // Sin datos, una carga no silenciosa mantiene el skeleton hasta la respuesta.
  void store.load()
}

function onApply(filters: DashboardFilters): void {
  store.setFilters(filters)
}

function onReset(): void {
  store.resetFilters()
}

function onEmptyAction(): void {
  if (emptyVariant.value === 'periodo') {
    store.expandDateRange()
    return
  }
  store.resetFilters()
}

onMounted(() => {
  store.start()
})

onUnmounted(() => {
  store.stop()
})
</script>

<template>
  <main class="mx-auto max-w-7xl px-4 py-8">
    <header class="mb-6 flex flex-wrap items-start justify-between gap-4">
      <div>
        <h1 class="text-2xl font-semibold tracking-tight text-slate-900">
          Dashboard de cumplimiento de SLA
        </h1>
        <p class="mt-1 text-sm text-slate-700">
          Cumplimiento por prioridad y categoría, semáforo y técnicos con más
          tickets vencidos. Vista de solo lectura.
        </p>
      </div>
      <div class="flex flex-col items-end gap-1">
        <button
          v-if="meta"
          type="button"
          class="rounded-md border border-slate-300 bg-white px-3 py-1.5 text-sm font-medium text-slate-800 hover:bg-slate-100 disabled:cursor-not-allowed disabled:opacity-60 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-slate-900 focus-visible:ring-offset-2"
          :disabled="loading || updating"
          @click="retry"
        >
          Actualizar
        </button>
        <p v-if="lastUpdated" class="text-sm text-slate-700" data-testid="sla-last-updated">
          Última actualización: {{ lastUpdated }}
        </p>
      </div>
    </header>

    <p
      v-if="isUnauthorized"
      class="rounded-lg border border-slate-300 bg-white p-6 text-sm text-slate-800"
      role="status"
    >
      Redirigiendo al inicio de sesión…
    </p>

    <template v-else>
      <SlaDashboardFilters
        v-if="!fatalError"
        :filters="effectiveFilters"
        :options="options"
        :applying="loading || updating"
        @apply="onApply"
        @reset="onReset"
      />

      <DashboardErrorState
        v-if="degraded && error"
        class="mt-4"
        variant="warning"
        @retry="retry"
      />

      <div class="mt-4">
        <DashboardErrorState
          v-if="fatalError && error"
          :variant="fatalVariant"
          :message="error.message"
          @retry="retryFatal"
        />
        <SlaDashboardSkeleton v-else-if="showSkeleton" />
        <DashboardEmptyState
          v-else-if="emptyVariant"
          :variant="emptyVariant"
          @action="onEmptyAction"
        />
        <template v-else-if="data">
          <SlaSummary :summary="data.summary" />

          <DashboardEmptyState
            v-if="hasOnlyNoSla"
            class="mt-4"
            variant="sin-sla"
          />
          <ComplianceMatrix
            class="mt-4"
            :matrix="data.matrix"
            :priority-totals="data.priority_totals"
            :category-totals="data.category_totals"
            :summary="data.summary"
          />

          <SemaphoreLegend
            v-if="meta"
            class="mt-4"
            :thresholds="meta.thresholds"
          />

          <TechnicianRanking class="mt-4" :ranking="data.ranking" />
        </template>
      </div>
    </template>
  </main>
</template>
