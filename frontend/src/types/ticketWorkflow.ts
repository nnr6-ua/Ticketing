/** Tipos alineados con `contracts/ticket-workflow.openapi.yaml` (HU-05). */

export type TicketStatus =
  | 'abierto'
  | 'en_progreso'
  | 'pendiente_usuario'
  | 'resuelto'
  | 'cerrado'

export type TimelineEventType =
  | 'status_change'
  | 'resolution'
  | 'internal_comment'

export interface StatusOption {
  value: TicketStatus
  label: string
}

export interface AuthorRef {
  id: string
  name: string
  role: 'usuario' | 'tecnico' | 'supervisor' | 'admin'
}

export interface TimelineEntry {
  id: string
  type: TimelineEventType
  from_status: TicketStatus | null
  to_status: TicketStatus | null
  body: string | null
  is_internal: boolean
  author: AuthorRef
  created_at: string
}

export interface TicketWorkflowSnapshot {
  id: string
  number: string
  title: string
  status: TicketStatus
  status_label: string
  assignee_id: string | null
  creator_id: string
  finalized_at: string | null
  closed_at: string | null
  updated_at: string
  allowed_transitions: StatusOption[]
}

export interface WorkflowResponse {
  ticket: TicketWorkflowSnapshot
  can_change_status: boolean
  can_comment_internally: boolean
  can_view_internal: boolean
}

export interface StatusTransitionRequest {
  target_status: TicketStatus
  resolution?: string | null
  expected_updated_at: string
  request_id: string
}

export interface StatusTransitionResponse {
  changed: boolean
  message: string | null
  ticket: TicketWorkflowSnapshot
  timeline_entries: TimelineEntry[]
}

export interface InternalCommentRequest {
  body: string
  request_id: string
}

export interface InternalCommentResponse {
  entry: TimelineEntry
  created: boolean
}

export interface Pagination {
  page: number
  page_size: number
  total_items: number
  total_pages: number
  has_next: boolean
  has_previous: boolean
}

export interface TimelineResponse {
  items: TimelineEntry[]
  pagination: Pagination
}

export interface ApiErrorBody {
  detail: {
    code: string
    message: string
  }
}
