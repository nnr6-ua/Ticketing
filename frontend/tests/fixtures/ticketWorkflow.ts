import type { MyTicketSummary } from '@/types/myTickets'
import type {
  InformationRequestRef,
  TimelineEntry,
  TicketWorkflowSnapshot,
  WorkflowResponse,
} from '@/types/ticketWorkflow'

export function makeTicketWorkflowSnapshot(
  overrides: Partial<TicketWorkflowSnapshot> = {},
): TicketWorkflowSnapshot {
  return {
    id: 't1',
    number: 'TK-000501',
    title: 'Ticket de prueba',
    status: 'en_progreso',
    status_label: 'En progreso',
    assignee_id: 'u1',
    creator_id: 'u2',
    finalized_at: null,
    closed_at: null,
    updated_at: '2026-11-04T10:00:00Z',
    allowed_transitions: [
      { value: 'pendiente_usuario', label: 'Pendiente de usuario' },
      { value: 'resuelto', label: 'Resuelto' },
    ],
    ...overrides,
  }
}

export function makeInformationRequestRef(
  overrides: Partial<InformationRequestRef> = {},
): InformationRequestRef {
  return {
    id: 'r1',
    body: '¿Qué navegador usas?',
    requested_at: '2026-11-04T10:00:00Z',
    requested_by: { id: 'u1', name: 'Laura Técnica', role: 'tecnico' },
    ...overrides,
  }
}

export function makeWorkflowResponse(
  overrides: Partial<WorkflowResponse> = {},
): WorkflowResponse {
  return {
    ticket: makeTicketWorkflowSnapshot(),
    can_change_status: true,
    can_comment_internally: true,
    can_view_internal: true,
    can_request_information: true,
    can_respond_to_information: false,
    awaiting_user_response: false,
    active_information_request: null,
    reminder_active: false,
    reminder_due_at: null,
    ...overrides,
  }
}

export function makeTimelineEntryFixture(
  overrides: Partial<TimelineEntry> = {},
): TimelineEntry {
  return {
    id: 'e1',
    type: 'status_change',
    from_status: 'abierto',
    to_status: 'en_progreso',
    body: null,
    is_internal: false,
    author: { id: 'u1', name: 'Laura Técnica', role: 'tecnico' },
    created_at: '2026-11-04T10:00:00Z',
    reply_to_id: null,
    ...overrides,
  }
}

export function makeMyTicketSummaryFixture(
  overrides: Partial<MyTicketSummary> = {},
): MyTicketSummary {
  return {
    id: 't1',
    ticket_number: 'TK-000501',
    title: 'Ticket de prueba',
    status: 'pendiente_usuario',
    status_label: 'Pendiente de usuario',
    category: null,
    priority: { id: 'p1', name: 'Alta', level: 2, color: '#dc2626' },
    created_at: '2026-11-01T10:00:00Z',
    updated_at: '2026-11-04T10:00:00Z',
    awaiting_user_response: true,
    response_requested_at: '2026-11-04T10:00:00Z',
    reminder_active: false,
    reminder_due_at: '2026-11-06T10:00:00Z',
    ...overrides,
  }
}
