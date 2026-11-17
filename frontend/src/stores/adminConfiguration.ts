import { ref } from 'vue'
import { defineStore } from 'pinia'

import { ApiClientError } from '@/api/client'
import {
  createCategory as createCategoryRequest,
  createPriority as createPriorityRequest,
  deleteCategory as deleteCategoryRequest,
  deletePriority as deletePriorityRequest,
  getConfigHistory,
  getSlaMatrix,
  listCategories,
  listPriorities,
  saveSlaBatch,
  updateCategory as updateCategoryRequest,
  updatePriority as updatePriorityRequest,
} from '@/services/adminConfiguration'
import { getStoredUserRole } from '@/auth/session'
import { landingForRole } from '@/router/landing'
import router from '@/router'
import type {
  CategoryAdmin,
  CategoryCreateRequest,
  CategoryUpdateRequest,
  ConfigHistoryFilters,
  ConfigHistoryResponse,
  DeleteRequest,
  PriorityAdmin,
  PriorityCreateRequest,
  PriorityUpdateRequest,
  SlaChange,
  SlaMatrixResponse,
} from '@/types/adminConfiguration'

const EMPTY_FILTERS: ConfigHistoryFilters = { page: 1, page_size: 25 }

export const useAdminConfigurationStore = defineStore(
  'adminConfiguration',
  () => {
    const categories = ref<CategoryAdmin[]>([])
    const priorities = ref<PriorityAdmin[]>([])
    const matrix = ref<SlaMatrixResponse | null>(null)
    const history = ref<ConfigHistoryResponse | null>(null)
    const historyFilters = ref<ConfigHistoryFilters>({ ...EMPTY_FILTERS })
    const loading = ref(false)
    const saving = ref(false)
    const error = ref<ApiClientError | null>(null)
    const conflict = ref<string | null>(null)

    function handleError(caught: unknown): never {
      const apiError =
        caught instanceof ApiClientError
          ? caught
          : new ApiClientError('network', 'No se pudo completar la solicitud.')
      error.value = apiError
      if (
        apiError.kind === 'conflict' ||
        apiError.code === 'stale_configuration'
      ) {
        conflict.value = apiError.message
      }
      if (apiError.kind === 'unauthorized') {
        void router.replace({
          name: 'login',
          query: { redirect: router.currentRoute.value.fullPath },
        })
      }
      if (apiError.kind === 'forbidden') {
        void router.replace(landingForRole(getStoredUserRole()))
      }
      throw apiError
    }

    async function loadAll(): Promise<void> {
      loading.value = true
      error.value = null
      try {
        const [nextCategories, nextPriorities, nextMatrix] = await Promise.all([
          listCategories(),
          listPriorities(),
          getSlaMatrix(),
        ])
        categories.value = nextCategories
        priorities.value = nextPriorities
        matrix.value = nextMatrix
      } catch (caught) {
        handleError(caught)
      } finally {
        loading.value = false
      }
    }

    async function reloadAll(): Promise<void> {
      conflict.value = null
      await loadAll()
    }

    async function createCategory(
      payload: CategoryCreateRequest,
    ): Promise<CategoryAdmin> {
      saving.value = true
      error.value = null
      conflict.value = null
      try {
        const created = await createCategoryRequest(payload)
        categories.value = [...categories.value, created].sort(
          (left, right) =>
            left.sort_order - right.sort_order ||
            left.name.localeCompare(right.name, 'es'),
        )
        matrix.value = await getSlaMatrix()
        return created
      } catch (caught) {
        handleError(caught)
      } finally {
        saving.value = false
      }
    }

    async function updateCategory(
      id: string,
      payload: CategoryUpdateRequest,
    ): Promise<CategoryAdmin> {
      saving.value = true
      error.value = null
      conflict.value = null
      try {
        const updated = await updateCategoryRequest(id, payload)
        categories.value = categories.value.map((item) =>
          item.id === id ? updated : item,
        )
        matrix.value = await getSlaMatrix()
        return updated
      } catch (caught) {
        handleError(caught)
      } finally {
        saving.value = false
      }
    }

    async function deleteCategory(
      id: string,
      payload: DeleteRequest,
    ): Promise<void> {
      saving.value = true
      error.value = null
      conflict.value = null
      try {
        await deleteCategoryRequest(id, payload)
        categories.value = categories.value.filter((item) => item.id !== id)
        matrix.value = await getSlaMatrix()
      } catch (caught) {
        handleError(caught)
      } finally {
        saving.value = false
      }
    }

    async function createPriority(
      payload: PriorityCreateRequest,
    ): Promise<PriorityAdmin> {
      saving.value = true
      error.value = null
      conflict.value = null
      try {
        const created = await createPriorityRequest(payload)
        priorities.value = [...priorities.value, created].sort(
          (left, right) =>
            left.sort_order - right.sort_order || left.level - right.level,
        )
        matrix.value = await getSlaMatrix()
        return created
      } catch (caught) {
        handleError(caught)
      } finally {
        saving.value = false
      }
    }

    async function updatePriority(
      id: string,
      payload: PriorityUpdateRequest,
    ): Promise<PriorityAdmin> {
      saving.value = true
      error.value = null
      conflict.value = null
      try {
        const updated = await updatePriorityRequest(id, payload)
        priorities.value = priorities.value.map((item) =>
          item.id === id ? updated : item,
        )
        matrix.value = await getSlaMatrix()
        return updated
      } catch (caught) {
        handleError(caught)
      } finally {
        saving.value = false
      }
    }

    async function deletePriority(
      id: string,
      payload: DeleteRequest,
    ): Promise<void> {
      saving.value = true
      error.value = null
      conflict.value = null
      try {
        await deletePriorityRequest(id, payload)
        priorities.value = priorities.value.filter((item) => item.id !== id)
        matrix.value = await getSlaMatrix()
      } catch (caught) {
        handleError(caught)
      } finally {
        saving.value = false
      }
    }

    async function saveMatrix(changes: SlaChange[]): Promise<void> {
      saving.value = true
      error.value = null
      conflict.value = null
      try {
        const response = await saveSlaBatch({ changes })
        matrix.value = {
          configuration_version: response.configuration_version,
          items: response.items,
          combinations: matrix.value?.combinations ?? {
            categories: [],
            priorities: [],
          },
        }
        matrix.value = await getSlaMatrix()
      } catch (caught) {
        handleError(caught)
      } finally {
        saving.value = false
      }
    }

    async function loadHistory(
      filters: ConfigHistoryFilters = historyFilters.value,
    ): Promise<void> {
      loading.value = true
      error.value = null
      historyFilters.value = { ...EMPTY_FILTERS, ...filters }
      try {
        history.value = await getConfigHistory(historyFilters.value)
      } catch (caught) {
        handleError(caught)
      } finally {
        loading.value = false
      }
    }

    function clearConflict(): void {
      conflict.value = null
    }

    return {
      categories,
      priorities,
      matrix,
      history,
      historyFilters,
      loading,
      saving,
      error,
      conflict,
      loadAll,
      reloadAll,
      createCategory,
      updateCategory,
      deleteCategory,
      createPriority,
      updatePriority,
      deletePriority,
      saveMatrix,
      loadHistory,
      clearConflict,
    }
  },
)
