/** Tipos alineados con `contracts/assignee-change.openapi.yaml` (HU-06). */

import type { TicketStatus, TicketWorkflowSnapshot, TimelineEntry } from '@/types/ticketWorkflow'

export type EscalationLevel = 'nivel_1' | 'nivel_2' | 'especialista'

export type AssigneeChangeKind = 'reassignment' | 'escalation'

export interface AssigneeRef {
  id: string
  name: string
  role: 'usuario' | 'tecnico' | 'supervisor' | 'admin'
  team: string | null
  escalation_level: EscalationLevel
  escalation_level_label: string
}

export interface EscalationTarget {
  value: EscalationLevel
  label: string
  technician_count: number
  is_available: boolean
}

export interface AssigneeChangeOptions {
  ticket_id: string
  status: TicketStatus
  current_assignee: AssigneeRef
  has_reassignment_candidates: boolean
  has_available_escalation_target: boolean
  reassignment_candidates: AssigneeRef[]
  escalation_targets: EscalationTarget[]
}

export interface ReassignmentRequest {
  new_assignee_id: string
  reason: string
  expected_updated_at: string
  request_id: string
}

export interface EscalationRequest {
  target_level: EscalationLevel
  reason: string
  expected_updated_at: string
  request_id: string
}

export interface AssigneeChangeResponse {
  changed: boolean
  message: string | null
  ticket: TicketWorkflowSnapshot
  previous_assignee: AssigneeRef
  new_assignee: AssigneeRef
  change_kind: AssigneeChangeKind
  from_escalation_level: EscalationLevel
  from_escalation_level_label: string
  to_escalation_level: EscalationLevel
  to_escalation_level_label: string
  timeline_entry: TimelineEntry | null
}
