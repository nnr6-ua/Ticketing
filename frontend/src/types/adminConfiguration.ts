export type ConfigEntityType = 'category' | 'priority' | 'sla_rule'

export type ConfigAction =
  | 'create'
  | 'update'
  | 'deactivate'
  | 'reactivate'
  | 'delete'
  | 'set_default'
  | 'rule_upsert'
  | 'rule_retire'

export interface UserRef {
  id: string
  name: string
  email: string
}

export interface ConfigurationVersionRef {
  id: string
  version: number
  created_at: string
  created_by: UserRef | null
}

export interface CategoryRef {
  id: string
  name: string
  is_active?: boolean
}

export interface PriorityRef {
  id: string
  name: string
  level: number
  color: string | null
  base_hours: string | null
  is_active?: boolean
}

export interface CategoryAdmin extends CategoryRef {
  description: string | null
  keywords: string[]
  is_default: boolean
  is_system: boolean
  sort_order: number
  revision: number
  ticket_count: number
  rule_count: number
  can_delete: boolean
}

export interface PriorityAdmin extends PriorityRef {
  keywords: string[]
  is_default: boolean
  is_system: boolean
  sort_order: number
  revision: number
  ticket_count: number
  rule_count: number
  can_delete: boolean
}

export interface CategoryCreateRequest {
  name: string
  description?: string | null
  keywords?: string[]
  sort_order?: number
  is_default?: boolean
}

export interface CategoryUpdateRequest {
  expected_revision: number
  name?: string
  description?: string | null
  keywords?: string[]
  sort_order?: number
  is_active?: boolean
  is_default?: boolean
  replacement_default_id?: string | null
}

export interface PriorityCreateRequest {
  name: string
  level: number
  color?: string | null
  base_hours: string
  keywords?: string[]
  sort_order?: number
  is_default?: boolean
}

export interface PriorityUpdateRequest {
  expected_revision: number
  name?: string
  level?: number
  color?: string | null
  base_hours?: string
  keywords?: string[]
  sort_order?: number
  is_active?: boolean
  is_default?: boolean
  replacement_default_id?: string | null
}

export interface DeleteRequest {
  expected_revision: number
}

export interface DeleteResponse {
  deleted: boolean
  id: string
  configuration_version: ConfigurationVersionRef
}

export interface SlaRuleAdmin {
  id: string
  category: CategoryRef
  priority: PriorityRef
  hours: string
  valid_from_version: number
  configuration_version_id: string
  created_at: string
  created_by: UserRef
}

export interface SlaMatrixResponse {
  configuration_version: ConfigurationVersionRef
  items: SlaRuleAdmin[]
  combinations: {
    categories: CategoryRef[]
    priorities: PriorityRef[]
  }
}

export type SlaChange =
  | {
      operation: 'upsert'
      category_id: string
      priority_id: string
      hours: string
      expected_rule_id: string | null
    }
  | {
      operation: 'retire'
      rule_id: string
      expected_rule_id: string
    }

export interface SlaBatchRequest {
  changes: SlaChange[]
}

export interface SlaBatchResponse {
  configuration_version: ConfigurationVersionRef
  items: SlaRuleAdmin[]
}

export interface ConfigHistoryEntry {
  id: string
  configuration_version: ConfigurationVersionRef
  entity_type: ConfigEntityType
  entity_id: string
  action: ConfigAction
  actor: UserRef
  occurred_at: string
  previous_values: Record<string, unknown> | null
  new_values: Record<string, unknown> | null
  summary: string
}

export interface Pagination {
  page: number
  page_size: number
  total_items: number
  total_pages: number
  has_next: boolean
  has_previous: boolean
}

export interface ConfigHistoryResponse {
  items: ConfigHistoryEntry[]
  pagination: Pagination
}

export interface ConfigHistoryFilters {
  from?: string
  to?: string
  entity_type?: ConfigEntityType
  entity_id?: string
  action?: ConfigAction
  configuration_version_id?: string
  page?: number
  page_size?: number
}

export interface ApiErrorBody {
  detail: {
    code: string
    message: string
  }
}
