/** Tipos alineados con `contracts/ticket-workflow.openapi.yaml` (HU-05 y HU-06). */

import type {
  AssigneeChangeKind,
  AssigneeRef,
  EscalationLevel,
} from '@/types/assigneeChange'

export type TicketStatus =
  | 'abierto'
  | 'en_progreso'
  | 'pendiente_usuario'
  | 'resuelto'
  | 'cerrado'

export type TimelineEventType =
  | 'created'
  | 'status_change'
  | 'resolution'
  | 'internal_comment'
  | 'information_request'
  | 'user_response'
  | 'assignee_change'

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
  reply_to_id: string | null
  change_kind: AssigneeChangeKind | null
  previous_assignee: AssigneeRef | null
  new_assignee: AssigneeRef | null
  from_escalation_level: EscalationLevel | null
  from_escalation_level_label: string | null
  to_escalation_level: EscalationLevel | null
  to_escalation_level_label: string | null
}

export interface InformationRequestRef {
  id: string
  body: string
  requested_at: string
  requested_by: AuthorRef
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
  can_request_information: boolean
  can_respond_to_information: boolean
  awaiting_user_response: boolean
  active_information_request: InformationRequestRef | null
  reminder_active: boolean
  reminder_due_at: string | null
  can_reassign: boolean
  can_escalate: boolean
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
  is_internal?: boolean
}

export interface InternalCommentResponse {
  entry: TimelineEntry
  created: boolean
}

export interface InformationRequestRequest {
  body: string
  expected_updated_at: string
  request_id: string
}

export interface InformationRequestResponse {
  changed: boolean
  message: string | null
  ticket: TicketWorkflowSnapshot
  timeline_entries: TimelineEntry[]
  information_request: InformationRequestRef
}

export interface InformationResponseRequest {
  body: string
  expected_updated_at: string
  request_id: string
}

export interface InformationResponseResponse {
  changed: boolean
  message: string | null
  ticket: TicketWorkflowSnapshot
  timeline_entries: TimelineEntry[]
  information_response: TimelineEntry
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
