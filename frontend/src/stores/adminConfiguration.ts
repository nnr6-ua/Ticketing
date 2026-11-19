import { computed, ref } from 'vue'
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
  retireSlaRule as retireSlaRuleRequest,
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

type MatrixDraft = Record<string, string | null>

function cellKey(categoryId: string, priorityId: string): string {
  return `${categoryId}:${priorityId}`
}

function cloneMatrix(value: SlaMatrixResponse | null): SlaMatrixResponse | null {
  return value ? (JSON.parse(JSON.stringify(value)) as SlaMatrixResponse) : null
}

function buildMatrixChanges(
  baseline: SlaMatrixResponse | null,
  draft: MatrixDraft,
): SlaChange[] {
  if (!baseline) return []
  const changes: SlaChange[] = []
  for (const [cell, hours] of Object.entries(draft)) {
    const [categoryId, priorityId] = cell.split(':')
    if (!categoryId || !priorityId) continue
    const rule = baseline.items.find(
      (item) =>
        item.category.id === categoryId && item.priority.id === priorityId,
    )
    if (hours === null) {
      if (rule) {
        changes.push({
          operation: 'retire',
          rule_id: rule.id,
          expected_rule_id: rule.id,
        })
      }
      continue
    }
    if (rule && Number(rule.hours) === Number(hours)) continue
    changes.push({
      operation: 'upsert',
      category_id: categoryId,
      priority_id: priorityId,
      hours,
      expected_rule_id: rule?.id ?? null,
    })
  }
  return changes
}

export const useAdminConfigurationStore = defineStore(
  'adminConfiguration',
  () => {
    const categories = ref<CategoryAdmin[]>([])
    const priorities = ref<PriorityAdmin[]>([])
    const matrix = ref<SlaMatrixResponse | null>(null)
    const matrixDraft = ref<MatrixDraft>({})
    const matrixBaseline = ref<SlaMatrixResponse | null>(null)
    const matrixCellErrors = ref<Record<string, string>>({})
    const history = ref<ConfigHistoryResponse | null>(null)
    const historyFilters = ref<ConfigHistoryFilters>({ ...EMPTY_FILTERS })
    const loading = ref(false)
    const saving = ref(false)
    const error = ref<ApiClientError | null>(null)
    const conflict = ref<string | null>(null)
    const successMessage = ref<string | null>(null)

    const matrixChanges = computed(() =>
      buildMatrixChanges(matrixBaseline.value, matrixDraft.value),
    )
    const matrixIsDirty = computed(() => matrixChanges.value.length > 0)
    const configurationVersion = computed(
      () => matrix.value?.configuration_version ?? null,
    )
    const messages = computed(() => ({
      error: error.value?.message ?? null,
      conflict: conflict.value,
      success: successMessage.value,
    }))
    const messageList = computed(() =>
      Object.values(messages.value).filter(
        (message): message is string => message !== null,
      ),
    )

    function cellForRule(ruleId: string): string | null {
      const rule = matrix.value?.items.find((item) => item.id === ruleId)
      return rule ? cellKey(rule.category.id, rule.priority.id) : null
    }

    function markInactiveCells(changes: SlaChange[], message: string): void {
      const errors: Record<string, string> = {}
      for (const change of changes) {
        const cell =
          change.operation === 'upsert'
            ? cellKey(change.category_id, change.priority_id)
            : cellForRule(change.rule_id)
        if (cell) errors[cell] = message
      }
      matrixCellErrors.value = errors
    }

    function setMatrix(nextMatrix: SlaMatrixResponse | null): void {
      matrix.value = nextMatrix
      matrixBaseline.value = cloneMatrix(nextMatrix)
      matrixDraft.value = {}
      matrixCellErrors.value = {}
    }

    function setMatrixDraft(nextDraft: MatrixDraft): void {
      matrixDraft.value = { ...nextDraft }
    }

    function setMatrixCell(
      categoryId: string,
      priorityId: string,
      hours: string | null,
    ): void {
      setMatrixDraft({
        ...matrixDraft.value,
        [cellKey(categoryId, priorityId)]: hours,
      })
    }

    function clearMatrixDraft(): void {
      matrixDraft.value = {}
      matrixCellErrors.value = {}
    }

    function clearMessages(): void {
      error.value = null
      conflict.value = null
      successMessage.value = null
    }

    function handleError(caught: unknown): never {
      const apiError =
        caught instanceof ApiClientError
          ? caught
          : new ApiClientError('network', 'No se pudo completar la solicitud.')
      error.value = apiError
      successMessage.value = null
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
        setMatrix(nextMatrix)
      } catch (caught) {
        handleError(caught)
      } finally {
        loading.value = false
      }
    }

    async function reloadAll(): Promise<void> {
      successMessage.value = null
      await loadAll()
      conflict.value = null
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
        setMatrix(await getSlaMatrix())
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
        setMatrix(await getSlaMatrix())
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
        setMatrix(await getSlaMatrix())
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
        setMatrix(await getSlaMatrix())
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
        setMatrix(await getSlaMatrix())
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
        setMatrix(await getSlaMatrix())
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
      matrixCellErrors.value = {}
      try {
        const response = await saveSlaBatch({ changes })
        setMatrix({
          configuration_version: response.configuration_version,
          items: response.items,
          combinations: matrix.value?.combinations ?? {
            categories: [],
            priorities: [],
          },
        })
        setMatrix(await getSlaMatrix())
        successMessage.value = `Matriz guardada en la versión v${response.configuration_version.version}.`
      } catch (caught) {
        if (
          caught instanceof ApiClientError &&
          caught.code === 'inactive_catalog_item'
        ) {
          markInactiveCells(changes, caught.message)
        }
        handleError(caught)
      } finally {
        saving.value = false
      }
    }

    async function retireRule(ruleId: string): Promise<void> {
      saving.value = true
      error.value = null
      conflict.value = null
      matrixCellErrors.value = {}
      try {
        const response = await retireSlaRuleRequest(ruleId, ruleId)
        setMatrix({
          configuration_version: response.configuration_version,
          items: response.items,
          combinations: matrix.value?.combinations ?? {
            categories: [],
            priorities: [],
          },
        })
        setMatrix(await getSlaMatrix())
        successMessage.value = `Regla retirada en la versión v${response.configuration_version.version}.`
      } catch (caught) {
        if (
          caught instanceof ApiClientError &&
          caught.code === 'inactive_catalog_item'
        ) {
          const cell = cellForRule(ruleId)
          if (cell) {
            matrixCellErrors.value = { [cell]: caught.message }
          }
        }
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
      matrixDraft,
      draft: matrixDraft,
      matrixBaseline,
      baseline: matrixBaseline,
      matrixCellErrors,
      matrixChanges,
      matrixIsDirty,
      isDirty: matrixIsDirty,
      configurationVersion,
      currentVersion: configurationVersion,
      history,
      historyFilters,
      loading,
      saving,
      error,
      conflict,
      successMessage,
      messages,
      messageList,
      setMatrix,
      setMatrixDraft,
      setMatrixCell,
      clearMatrixDraft,
      clearMessages,
      loadAll,
      reloadAll,
      createCategory,
      updateCategory,
      deleteCategory,
      createPriority,
      updatePriority,
      deletePriority,
      saveMatrix,
      retireRule,
      loadHistory,
      clearConflict,
    }
  },
)
