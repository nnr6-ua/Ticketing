/** Tipos alineados con `contracts/work-queue.openapi.yaml`. */

export type SlaState = 'on_time' | 'at_risk' | 'overdue' | 'no_sla' | 'finalized'

export type SlaOutcome = 'met' | 'breached' | 'no_sla' | null

export type TicketStatus =
  | 'abierto'
  | 'en_progreso'
  | 'pendiente_usuario'
  | 'resuelto'
  | 'cerrado'

export interface CategoryRef {
  id: string
  name: string
  is_active: boolean
}

export interface PriorityRef {
  id: string
  name: string
  level: number
  color: string | null
  is_active: boolean
}

export interface SlaInfo {
  deadline: string | null
  started_at: string | null
  total_seconds: number | null
  remaining_seconds: number | null
  warning_threshold_seconds: number | null
  state: SlaState
  outcome: SlaOutcome
  finalized_at: string | null
  breach_delay_seconds: number | null
}

export interface WorkQueueItem {
  id: string
  number: string
  title: string
  category: CategoryRef | null
  priority: PriorityRef
  status: TicketStatus
  status_label: string
  is_final: boolean
  sla: SlaInfo
  links: { self: string }
}

export interface Pagination {
  page: number
  page_size: number
  total_items: number
  total_pages: number
  has_next: boolean
  has_previous: boolean
}

export interface Counts {
  active: number
  finalized: number
}

export interface StatusFilterOption {
  value: TicketStatus
  label: string
  is_final: boolean
}

export interface PriorityFilterOption {
  id: string
  name: string
  level: number
  color?: string | null
  is_active: boolean
}

export interface AvailableFilters {
  statuses: StatusFilterOption[]
  priorities: PriorityFilterOption[]
  default_statuses: TicketStatus[]
}

export interface AppliedFilters {
  status: TicketStatus[]
  priority: number[]
  is_default: boolean
}

export interface WarningPolicy {
  short_sla_threshold_minutes: number
  short_sla_ratio: number
  long_sla_minimum_minutes: number
  long_sla_ratio: number
}

export interface Meta {
  server_time: string
  timezone: string
  warning_policy: WarningPolicy
}

export interface WorkQueueResponse {
  items: WorkQueueItem[]
  pagination: Pagination
  counts: Counts
  available_filters: AvailableFilters
  applied_filters: AppliedFilters
  meta: Meta
}

export interface WorkQueueParams {
  status?: TicketStatus[]
  priority?: number[]
  page?: number
  page_size?: number
}

export type WorkQueueErrorKind =
  | 'unauthorized'
  | 'forbidden'
  | 'invalid'
  | 'conflict'
  | 'server'
  | 'network'

export interface WorkQueueError {
  kind: WorkQueueErrorKind
  message: string
  status?: number
  code?: string
}
