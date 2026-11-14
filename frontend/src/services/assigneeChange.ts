import { apiGet, apiPost } from '@/api/client'
import type {
  AssigneeChangeOptions,
  AssigneeChangeResponse,
  EscalationRequest,
  ReassignmentRequest,
} from '@/types/assigneeChange'

const BASE_PATH = '/api/v1/tickets'

/** `GET /api/v1/tickets/{id}/assignee-change-options` */
export function getAssigneeChangeOptions(
  ticketId: string,
  signal?: AbortSignal,
): Promise<AssigneeChangeOptions> {
  return apiGet<AssigneeChangeOptions>(
    `${BASE_PATH}/${encodeURIComponent(ticketId)}/assignee-change-options`,
    { signal },
  )
}

/** `POST /api/v1/tickets/{id}/reassignments` */
export function reassignTicket(
  ticketId: string,
  payload: ReassignmentRequest,
  signal?: AbortSignal,
): Promise<AssigneeChangeResponse> {
  return apiPost<AssigneeChangeResponse, ReassignmentRequest>(
    `${BASE_PATH}/${encodeURIComponent(ticketId)}/reassignments`,
    payload,
    { signal },
  )
}

/** `POST /api/v1/tickets/{id}/escalations` */
export function escalateTicket(
  ticketId: string,
  payload: EscalationRequest,
  signal?: AbortSignal,
): Promise<AssigneeChangeResponse> {
  return apiPost<AssigneeChangeResponse, EscalationRequest>(
    `${BASE_PATH}/${encodeURIComponent(ticketId)}/escalations`,
    payload,
    { signal },
  )
}
