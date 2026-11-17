<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import AdminTabs from '@/components/admin/AdminTabs.vue'
import CategoryFormDialog from '@/components/admin/CategoryFormDialog.vue'
import CategoryTable from '@/components/admin/CategoryTable.vue'
import ConfigHistoryTable from '@/components/admin/ConfigHistoryTable.vue'
import ConflictBanner from '@/components/admin/ConflictBanner.vue'
import PriorityFormDialog from '@/components/admin/PriorityFormDialog.vue'
import PriorityTable from '@/components/admin/PriorityTable.vue'
import SlaMatrix from '@/components/admin/SlaMatrix.vue'
import { useAdminConfigurationStore } from '@/stores/adminConfiguration'
import type {
  CategoryAdmin,
  CategoryCreateRequest,
  CategoryUpdateRequest,
  ConfigHistoryFilters,
  PriorityAdmin,
  PriorityCreateRequest,
  PriorityUpdateRequest,
  SlaChange,
} from '@/types/adminConfiguration'

const route = useRoute()
const router = useRouter()
const store = useAdminConfigurationStore()

const tabs = [
  { id: 'categories', label: 'Categorías' },
  { id: 'priorities', label: 'Prioridades' },
  { id: 'matrix', label: 'Matriz SLA' },
  { id: 'history', label: 'Histórico' },
]

const validTabs = tabs.map((tab) => tab.id)
const initialTab = validTabs.includes(String(route.query.tab))
  ? String(route.query.tab)
  : 'categories'
const activeTab = ref(initialTab)

const categoryOpen = ref(false)
const selectedCategory = ref<CategoryAdmin | null>(null)
const priorityOpen = ref(false)
const selectedPriority = ref<PriorityAdmin | null>(null)
const matrixSavedVersion = ref<number | null>(null)

const serverError = computed(() => {
  if (!store.error || store.error.kind === 'conflict') return null
  return {
    code: store.error.code ?? 'request_failed',
    message: store.error.message,
  }
})

const forbidden = computed(() => store.error?.kind === 'forbidden')

watch(activeTab, (tab) => {
  void router.replace({ query: { ...route.query, tab } })
  if (tab === 'history' && !store.history) {
    void loadHistory(store.historyFilters)
  }
})

watch(
  () => route.query.tab,
  (tab) => {
    if (typeof tab === 'string' && validTabs.includes(tab) && tab !== activeTab.value) {
      activeTab.value = tab
    }
  },
)

onMounted(() => {
  void store.loadAll()
})

function openCategoryCreate(): void {
  selectedCategory.value = null
  categoryOpen.value = true
}

function openCategoryEdit(item: CategoryAdmin): void {
  selectedCategory.value = item
  categoryOpen.value = true
}

async function toggleCategory(item: CategoryAdmin): Promise<void> {
  if (item.is_default && item.is_active) {
    openCategoryEdit(item)
    return
  }
  try {
    await store.updateCategory(item.id, {
      expected_revision: item.revision,
      is_active: !item.is_active,
    })
  } catch {
    // El store ya expone el conflicto o error.
  }
}

async function removeCategory(item: CategoryAdmin): Promise<void> {
  try {
    await store.deleteCategory(item.id, { expected_revision: item.revision })
  } catch {
    // El store ya expone el conflicto o error.
  }
}

async function submitCategory(
  payload: CategoryCreateRequest | CategoryUpdateRequest,
): Promise<void> {
  try {
    if (selectedCategory.value) {
      await store.updateCategory(
        selectedCategory.value.id,
        payload as CategoryUpdateRequest,
      )
    } else {
      await store.createCategory(payload as CategoryCreateRequest)
    }
    categoryOpen.value = false
  } catch {
    // Se mantiene abierto para corregir o recargar.
  }
}

function openPriorityCreate(): void {
  selectedPriority.value = null
  priorityOpen.value = true
}

function openPriorityEdit(item: PriorityAdmin): void {
  selectedPriority.value = item
  priorityOpen.value = true
}

async function togglePriority(item: PriorityAdmin): Promise<void> {
  if (item.is_default && item.is_active) {
    openPriorityEdit(item)
    return
  }
  try {
    await store.updatePriority(item.id, {
      expected_revision: item.revision,
      is_active: !item.is_active,
    })
  } catch {
    // El store ya expone el conflicto o error.
  }
}

async function removePriority(item: PriorityAdmin): Promise<void> {
  try {
    await store.deletePriority(item.id, { expected_revision: item.revision })
  } catch {
    // El store ya expone el conflicto o error.
  }
}

async function submitPriority(
  payload: PriorityCreateRequest | PriorityUpdateRequest,
): Promise<void> {
  try {
    if (selectedPriority.value) {
      await store.updatePriority(
        selectedPriority.value.id,
        payload as PriorityUpdateRequest,
      )
    } else {
      await store.createPriority(payload as PriorityCreateRequest)
    }
    priorityOpen.value = false
  } catch {
    // Se mantiene abierto para corregir o recargar.
  }
}

async function saveMatrix(changes: SlaChange[]): Promise<void> {
  try {
    await store.saveMatrix(changes)
    matrixSavedVersion.value = store.matrix?.configuration_version.version ?? null
  } catch {
    // La matriz conserva el borrador y muestra el conflicto.
  }
}

async function loadHistory(filters: ConfigHistoryFilters): Promise<void> {
  try {
    await store.loadHistory(filters)
  } catch {
    // El componente muestra el error con reintento.
  }
}

async function reloadAll(): Promise<void> {
  try {
    await store.reloadAll()
    if (activeTab.value === 'history') {
      await store.loadHistory(store.historyFilters)
    }
    categoryOpen.value = false
    priorityOpen.value = false
  } catch {
    // El store ya muestra el error.
  }
}

function retryHistory(): void {
  void loadHistory(store.historyFilters)
}
</script>

<template>
  <main class="mx-auto max-w-7xl px-4 py-8">
    <header class="flex flex-wrap items-end justify-between gap-4">
      <div>
        <h1 class="text-2xl font-semibold tracking-tight text-slate-900">
          Configuración de plazos SLA
        </h1>
        <p class="mt-1 text-sm text-slate-700">
          Gestiona categorías, prioridades y la matriz de plazos sin afectar a
          tickets ya creados.
        </p>
      </div>
      <button
        type="button"
        class="rounded-lg border border-slate-300 bg-white px-4 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-50"
        :disabled="store.loading"
        @click="reloadAll"
      >
        Recargar
      </button>
    </header>

    <section v-if="forbidden" class="mt-6 rounded-2xl border border-slate-200 bg-white p-8 text-center shadow-sm">
      <h2 class="text-lg font-semibold text-slate-900">Solo administración</h2>
      <p class="mt-2 text-sm text-slate-600">
        Esta vista está disponible únicamente para el rol de administración.
      </p>
    </section>

    <template v-else>
      <AdminTabs v-model="activeTab" :tabs="tabs" class="mt-6" />

      <ConflictBanner
        v-if="store.conflict"
        :message="store.conflict"
        :reloading="store.loading"
        class="mt-4"
        @reload="reloadAll"
      />

      <p
        v-if="store.error && !store.conflict"
        class="mt-4 rounded-xl border border-rose-300 bg-rose-50 p-3 text-sm text-rose-800"
        role="alert"
      >
        {{ store.error.message }}
      </p>

      <div
        v-if="store.loading && store.categories.length === 0"
        class="mt-6 grid gap-3"
      >
        <div class="h-24 animate-pulse rounded-2xl bg-slate-100" />
        <div class="h-24 animate-pulse rounded-2xl bg-slate-100" />
      </div>

      <div
        v-show="activeTab === 'categories'"
        id="panel-categories"
        role="tabpanel"
        aria-labelledby="tab-categories"
        tabindex="0"
        class="mt-6"
      >
        <CategoryTable
          :items="store.categories"
          :loading="store.loading"
          :disabled="store.saving"
          @create="openCategoryCreate"
          @edit="openCategoryEdit"
          @toggle="toggleCategory"
          @delete="removeCategory"
        />
      </div>

      <div
        v-show="activeTab === 'priorities'"
        id="panel-priorities"
        role="tabpanel"
        aria-labelledby="tab-priorities"
        tabindex="0"
        class="mt-6"
      >
        <PriorityTable
          :items="store.priorities"
          :loading="store.loading"
          :disabled="store.saving"
          @create="openPriorityCreate"
          @edit="openPriorityEdit"
          @toggle="togglePriority"
          @delete="removePriority"
        />
      </div>

      <p
        v-if="matrixSavedVersion !== null"
        class="mt-4 rounded-xl border border-emerald-300 bg-emerald-50 p-3 text-sm text-emerald-900"
        role="status"
        aria-live="polite"
      >
        Matriz guardada en la versión v{{ matrixSavedVersion }}.
      </p>

      <div
        v-show="activeTab === 'matrix'"
        id="panel-matrix"
        role="tabpanel"
        aria-labelledby="tab-matrix"
        tabindex="0"
        class="mt-6"
      >
        <SlaMatrix
          :matrix="store.matrix"
          :saving="store.saving"
          :conflict="store.conflict"
          @save="saveMatrix"
          @reload="reloadAll"
        />
      </div>

      <div
        v-show="activeTab === 'history'"
        id="panel-history"
        role="tabpanel"
        aria-labelledby="tab-history"
        tabindex="0"
        class="mt-6"
      >
        <ConfigHistoryTable
          :response="store.history"
          :filters="store.historyFilters"
          :loading="store.loading"
          :error="store.error?.message ?? null"
          @update:filters="loadHistory"
          @retry="retryHistory"
        />
      </div>
    </template>

    <CategoryFormDialog
      v-model:open="categoryOpen"
      :category="selectedCategory"
      :default-candidates="store.categories"
      :saving="store.saving"
      :server-error="serverError"
      :conflict="store.conflict"
      @submit="submitCategory"
      @reload="reloadAll"
    />

    <PriorityFormDialog
      v-model:open="priorityOpen"
      :priority="selectedPriority"
      :default-candidates="store.priorities"
      :saving="store.saving"
      :server-error="serverError"
      :conflict="store.conflict"
      @submit="submitPriority"
      @reload="reloadAll"
    />
  </main>
</template>
