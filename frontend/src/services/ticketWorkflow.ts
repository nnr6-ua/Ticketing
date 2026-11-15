import { apiGet, apiPost } from '@/api/client'
import type {
  InformationRequestRequest,
  InformationRequestResponse,
  InformationResponseRequest,
  InformationResponseResponse,
  InternalCommentRequest,
  InternalCommentResponse,
  StatusTransitionRequest,
  StatusTransitionResponse,
  TimelineResponse,
  WorkflowResponse,
} from '@/types/ticketWorkflow'

const BASE_PATH = '/api/v1/tickets'

/** `GET /api/v1/tickets/{id}/workflow` */
export function getWorkflow(
  ticketId: string,
  signal?: AbortSignal,
): Promise<WorkflowResponse> {
  return apiGet<WorkflowResponse>(
    `${BASE_PATH}/${encodeURIComponent(ticketId)}/workflow`,
    { signal },
  )
}

/** `POST /api/v1/tickets/{id}/status-transitions` */
export function transitionStatus(
  ticketId: string,
  payload: StatusTransitionRequest,
  signal?: AbortSignal,
): Promise<StatusTransitionResponse> {
  return apiPost<StatusTransitionResponse, StatusTransitionRequest>(
    `${BASE_PATH}/${encodeURIComponent(ticketId)}/status-transitions`,
    payload,
    { signal },
  )
}

/** `POST /api/v1/tickets/{id}/information-requests` */
export function requestInformation(
  ticketId: string,
  payload: InformationRequestRequest,
  signal?: AbortSignal,
): Promise<InformationRequestResponse> {
  return apiPost<InformationRequestResponse, InformationRequestRequest>(
    `${BASE_PATH}/${encodeURIComponent(ticketId)}/information-requests`,
    payload,
    { signal },
  )
}

/** `POST /api/v1/tickets/{id}/information-responses` */
export function respondToInformation(
  ticketId: string,
  payload: InformationResponseRequest,
  signal?: AbortSignal,
): Promise<InformationResponseResponse> {
  return apiPost<InformationResponseResponse, InformationResponseRequest>(
    `${BASE_PATH}/${encodeURIComponent(ticketId)}/information-responses`,
    payload,
    { signal },
  )
}

/** `POST /api/v1/tickets/{id}/internal-comments` */
export function addInternalComment(
  ticketId: string,
  payload: InternalCommentRequest,
  signal?: AbortSignal,
): Promise<InternalCommentResponse> {
  return apiPost<InternalCommentResponse, InternalCommentRequest>(
    `${BASE_PATH}/${encodeURIComponent(ticketId)}/internal-comments`,
    payload,
    { signal },
  )
}

/** `GET /api/v1/tickets/{id}/timeline?page=&page_size=` */
export function getTimeline(
  ticketId: string,
  page = 1,
  pageSize = 50,
  signal?: AbortSignal,
): Promise<TimelineResponse> {
  return apiGet<TimelineResponse>(
    `${BASE_PATH}/${encodeURIComponent(ticketId)}/timeline`,
    { signal, query: { page, page_size: pageSize } },
  )
}
