import { apiGet, apiPost } from '@/api/client'
import type {
  CategoryAdmin,
  CategoryCreateRequest,
  CategoryUpdateRequest,
  ConfigHistoryFilters,
  ConfigHistoryResponse,
  DeleteRequest,
  DeleteResponse,
  PriorityAdmin,
  PriorityCreateRequest,
  PriorityUpdateRequest,
  SlaBatchRequest,
  SlaBatchResponse,
  SlaMatrixResponse,
} from '@/types/adminConfiguration'

const BASE = '/api/v1/admin'
const GET_FALLBACK_MESSAGE =
  'No se pudo cargar la configuración. Inténtalo de nuevo.'

export function listCategories(signal?: AbortSignal) {
  return apiGet<CategoryAdmin[]>(`${BASE}/categories`, {
    signal,
    fallbackMessage: GET_FALLBACK_MESSAGE,
  })
}

export function createCategory(payload: CategoryCreateRequest) {
  return apiPost<CategoryAdmin, CategoryCreateRequest>(
    `${BASE}/categories`,
    payload,
  )
}

export function updateCategory(id: string, payload: CategoryUpdateRequest) {
  return apiPost<CategoryAdmin, CategoryUpdateRequest>(
    `${BASE}/categories/${encodeURIComponent(id)}/updates`,
    payload,
  )
}

export function deleteCategory(id: string, payload: DeleteRequest) {
  return apiPost<DeleteResponse, DeleteRequest>(
    `${BASE}/categories/${encodeURIComponent(id)}/deletion`,
    payload,
  )
}

export function listPriorities(signal?: AbortSignal) {
  return apiGet<PriorityAdmin[]>(`${BASE}/priorities`, {
    signal,
    fallbackMessage: GET_FALLBACK_MESSAGE,
  })
}

export function createPriority(payload: PriorityCreateRequest) {
  return apiPost<PriorityAdmin, PriorityCreateRequest>(
    `${BASE}/priorities`,
    payload,
  )
}

export function updatePriority(id: string, payload: PriorityUpdateRequest) {
  return apiPost<PriorityAdmin, PriorityUpdateRequest>(
    `${BASE}/priorities/${encodeURIComponent(id)}/updates`,
    payload,
  )
}

export function deletePriority(id: string, payload: DeleteRequest) {
  return apiPost<DeleteResponse, DeleteRequest>(
    `${BASE}/priorities/${encodeURIComponent(id)}/deletion`,
    payload,
  )
}

export function getSlaMatrix(signal?: AbortSignal) {
  return apiGet<SlaMatrixResponse>(`${BASE}/sla-rules`, {
    signal,
    fallbackMessage: GET_FALLBACK_MESSAGE,
  })
}

export function saveSlaBatch(payload: SlaBatchRequest) {
  return apiPost<SlaBatchResponse, SlaBatchRequest>(
    `${BASE}/sla-rules/batch`,
    payload,
  )
}

export function retireSlaRule(ruleId: string, expectedRuleId: string) {
  return apiPost<SlaBatchResponse, { expected_rule_id: string }>(
    `${BASE}/sla-rules/${encodeURIComponent(ruleId)}/retirement`,
    { expected_rule_id: expectedRuleId },
  )
}

export function getConfigHistory(
  filters: ConfigHistoryFilters,
  signal?: AbortSignal,
) {
  return apiGet<ConfigHistoryResponse>(`${BASE}/config-history`, {
    signal,
    fallbackMessage: GET_FALLBACK_MESSAGE,
    query: {
      from: filters.from,
      to: filters.to,
      entity_type: filters.entity_type,
      entity_id: filters.entity_id,
      action: filters.action,
      configuration_version_id: filters.configuration_version_id,
      page: filters.page,
      page_size: filters.page_size,
    },
  })
}
