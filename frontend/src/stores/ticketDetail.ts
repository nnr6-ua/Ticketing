import { computed, ref } from 'vue'
import { defineStore } from 'pinia'

import { ApiClientError } from '@/api/client'
import {
  addInternalComment,
  getTimeline,
  getWorkflow,
  requestInformation as postInformationRequest,
  respondToInformation as postInformationResponse,
  transitionStatus as postStatusTransition,
} from '@/services/ticketWorkflow'
import type {
  InformationRequestRef,
  InformationRequestResponse,
  InformationResponseResponse,
  InternalCommentResponse,
  Pagination,
  StatusTransitionRequest,
  StatusTransitionResponse,
  TicketWorkflowSnapshot,
  TimelineEntry,
  WorkflowResponse,
} from '@/types/ticketWorkflow'

const DEFAULT_PAGE_SIZE = 50

const CODE_MESSAGES: Record<string, string> = {
  stale_ticket:
    'El ticket ha sido modificado por otra persona. Actualiza la información e inténtalo de nuevo.',
  not_ticket_assignee: 'Este ticket ya no está asignado a ti.',
  request_id_reused:
    'La solicitud ya se utilizó con otros datos. Genera una nueva solicitud e inténtalo de nuevo.',
  forbidden: 'No tienes permiso para modificar este ticket.',
  not_authenticated: 'La sesión no es válida o ha caducado.',
  internal_error:
    'No se pudo guardar el cambio. El ticket no se ha modificado. Inténtalo de nuevo.',
  information_request_already_open:
    'Ya hay una petición de información pendiente de respuesta.',
  information_request_required:
    'Escribe qué información necesitas del usuario.',
  information_request_too_long:
    'La petición de información no puede superar los 5.000 caracteres.',
  information_response_required:
    'Escribe la información que te ha pedido el técnico.',
  information_response_too_long:
    'La respuesta no puede superar los 5.000 caracteres.',
  ticket_not_found: 'No se ha encontrado el ticket.',
}

function extractErrorCode(caught: unknown): string | null {
  return caught instanceof ApiClientError ? (caught.code ?? null) : null
}

function errorMessage(caught: unknown): string {
  if (caught instanceof ApiClientError) {
    if (caught.code && CODE_MESSAGES[caught.code]) {
      return CODE_MESSAGES[caught.code]
    }
    if (caught.kind === 'network') {
      return 'No se pudo guardar el cambio. El ticket no se ha modificado. Inténtalo de nuevo.'
    }
    return caught.message
  }
  return 'No se pudo guardar el cambio. El ticket no se ha modificado. Inténtalo de nuevo.'
}

export const useTicketDetailStore = defineStore('ticketDetail', () => {
  const ticket = ref<TicketWorkflowSnapshot | null>(null)
  const timeline = ref<TimelineEntry[]>([])
  const pagination = ref<Pagination | null>(null)
  const canChangeStatus = ref(false)
  const canComment = ref(false)
  const canSeeInternal = ref(false)
  const loading = ref(false)
  const timelineLoading = ref(false)
  const submitting = ref(false)
  const error = ref<string | null>(null)
  const errorCode = ref<string | null>(null)
  const resolutionText = ref('')
  const commentText = ref('')
  const informationRequest = ref<InformationRequestRef | null>(null)
  const canRequestInformation = ref(false)
  const canRespondToInformation = ref(false)
  const awaitingUserResponse = ref(false)
  const reminderActive = ref(false)
  const reminderDueAt = ref<string | null>(null)
  const informationRequestText = ref('')
  const informationResponseText = ref('')
  const notice = ref<string | null>(null)

  // Secuencias para descartar respuestas de carga fuera de orden.
  let workflowSeq = 0
  let timelineSeq = 0
  let informationRequestId = ''
  let informationRequestSignature = ''
  let informationResponseId = ''
  let informationResponseSignature = ''

  const hasInternalEntries = computed(() =>
    timeline.value.some((entry) => entry.type === 'internal_comment'),
  )

  function clearError(): void {
    error.value = null
    errorCode.value = null
  }

  function applyWorkflow(response: WorkflowResponse): void {
    ticket.value = response.ticket
    canChangeStatus.value = response.can_change_status
    canComment.value = response.can_comment_internally
    canSeeInternal.value = response.can_view_internal
    canRequestInformation.value = response.can_request_information ?? false
    canRespondToInformation.value = response.can_respond_to_information ?? false
    awaitingUserResponse.value = response.awaiting_user_response ?? false
    informationRequest.value = response.active_information_request ?? null
    reminderActive.value = response.reminder_active ?? false
    reminderDueAt.value = response.reminder_due_at ?? null
  }

  function applyTransitionTicket(snapshot: TicketWorkflowSnapshot): void {
    // El servidor solo rellena `allowed_transitions` cuando el usuario puede
    // cambiar el estado. Al cerrar el ticket la lista queda vacía, así que la
    // capacidad se revoca en la misma sesión sin esperar a otra carga.
    ticket.value = snapshot
    canChangeStatus.value =
      snapshot.status !== 'cerrado' && snapshot.allowed_transitions.length > 0
  }

  async function loadWorkflow(ticketId: string): Promise<void> {
    const sequence = ++workflowSeq
    loading.value = true
    clearError()
    try {
      const response = await getWorkflow(ticketId)
      if (sequence !== workflowSeq) {
        return
      }
      applyWorkflow(response)
    } catch (caught) {
      if (sequence !== workflowSeq) {
        return
      }
      error.value = errorMessage(caught)
      errorCode.value = extractErrorCode(caught)
    } finally {
      if (sequence === workflowSeq) {
        loading.value = false
      }
    }
  }

  async function loadTimeline(
    ticketId: string,
    page = 1,
    pageSize = DEFAULT_PAGE_SIZE,
  ): Promise<void> {
    const sequence = ++timelineSeq
    timelineLoading.value = true
    try {
      const response = await getTimeline(ticketId, page, pageSize)
      if (sequence !== timelineSeq) {
        return
      }
      timeline.value = response.items
      pagination.value = response.pagination
    } catch (caught) {
      if (sequence !== timelineSeq) {
        return
      }
      if (!error.value) {
        error.value = errorMessage(caught)
        errorCode.value = extractErrorCode(caught)
      }
    } finally {
      if (sequence === timelineSeq) {
        timelineLoading.value = false
      }
    }
  }

  async function refresh(ticketId: string): Promise<void> {
    await Promise.all([loadWorkflow(ticketId), loadTimeline(ticketId)])
  }

  async function transitionStatus(
    ticketId: string,
    payload: StatusTransitionRequest,
  ): Promise<StatusTransitionResponse | null> {
    submitting.value = true
    clearError()
    notice.value = null
    try {
      const response = await postStatusTransition(ticketId, payload)
      applyTransitionTicket(response.ticket)
      if (response.changed) {
        resolutionText.value = ''
        notice.value = 'El estado del ticket se ha actualizado.'
        await loadTimeline(ticketId)
      } else if (response.message) {
        notice.value = response.message
      }
      return response
    } catch (caught) {
      const message = errorMessage(caught)
      const code = extractErrorCode(caught)
      error.value = message
      errorCode.value = code
      // Los conflictos de versión y las transiciones invalidas dejan la
      // pantalla desactualizada: se recarga conservando los textos escritos.
      if (code === 'stale_ticket' || code === 'invalid_transition' || code === 'ticket_closed') {
        await refresh(ticketId)
        error.value = message
        errorCode.value = code
      }
      return null
    } finally {
      submitting.value = false
    }
  }


  function ensureInformationRequestId(body: string): string {
    if (!informationRequestId || body !== informationRequestSignature) {
      informationRequestId = crypto.randomUUID()
      informationRequestSignature = body
    }
    return informationRequestId
  }

  function ensureInformationResponseId(body: string): string {
    if (!informationResponseId || body !== informationResponseSignature) {
      informationResponseId = crypto.randomUUID()
      informationResponseSignature = body
    }
    return informationResponseId
  }

  function resetInformationRequestId(): void {
    informationRequestId = ''
    informationRequestSignature = ''
  }

  function resetInformationResponseId(): void {
    informationResponseId = ''
    informationResponseSignature = ''
  }

  async function reloadAfterInformationConflict(
    ticketId: string,
    message: string,
    code: string | null,
  ): Promise<void> {
    await refresh(ticketId)
    error.value = message
    errorCode.value = code
  }

  async function requestInformation(
    ticketId: string,
    body: string,
  ): Promise<InformationRequestResponse | null> {
    const normalized = body.trim()
    submitting.value = true
    clearError()
    notice.value = null
    try {
      const response = await postInformationRequest(ticketId, {
        body: normalized,
        expected_updated_at: ticket.value?.updated_at ?? '',
        request_id: ensureInformationRequestId(normalized),
      })
      ticket.value = response.ticket
      if (response.changed) {
        informationRequestText.value = ''
        notice.value = 'La petición de información se ha enviado.'
      } else {
        notice.value = response.message
      }
      await refresh(ticketId)
      resetInformationRequestId()
      return response
    } catch (caught) {
      const message = errorMessage(caught)
      const code = extractErrorCode(caught)
      if (
        code === 'stale_ticket' ||
        code === 'information_request_already_open' ||
        code === 'invalid_transition'
      ) {
        await reloadAfterInformationConflict(ticketId, message, code)
      } else {
        error.value = message
        errorCode.value = code
      }
      if (
        code === 'request_id_reused' ||
        code === 'stale_ticket' ||
        code === 'information_request_already_open'
      ) {
        resetInformationRequestId()
      }
      return null
    } finally {
      submitting.value = false
    }
  }

  async function respondToInformation(
    ticketId: string,
    body: string,
  ): Promise<InformationResponseResponse | null> {
    const normalized = body.trim()
    submitting.value = true
    clearError()
    notice.value = null
    try {
      const response = await postInformationResponse(ticketId, {
        body: normalized,
        expected_updated_at: ticket.value?.updated_at ?? '',
        request_id: ensureInformationResponseId(normalized),
      })
      ticket.value = response.ticket
      if (response.changed) {
        informationResponseText.value = ''
        notice.value = 'Tu respuesta se ha enviado.'
      } else {
        notice.value = response.message
      }
      await refresh(ticketId)
      resetInformationResponseId()
      return response
    } catch (caught) {
      const message = errorMessage(caught)
      const code = extractErrorCode(caught)
      if (code === 'stale_ticket' || code === 'invalid_transition') {
        await reloadAfterInformationConflict(ticketId, message, code)
      } else {
        error.value = message
        errorCode.value = code
      }
      if (
        code === 'request_id_reused' ||
        code === 'stale_ticket' ||
        code === 'invalid_transition'
      ) {
        resetInformationResponseId()
      }
      return null
    } finally {
      submitting.value = false
    }
  }

  async function addComment(
    ticketId: string,
    requestId: string,
  ): Promise<InternalCommentResponse | null> {
    const body = commentText.value.trim()
    submitting.value = true
    clearError()
    notice.value = null
    try {
      const response = await addInternalComment(ticketId, { body, request_id: requestId })
      commentText.value = ''
      notice.value = response.created
        ? 'El comentario interno se ha añadido.'
        : 'El comentario interno ya estaba registrado.'
      await loadTimeline(ticketId)
      return response
    } catch (caught) {
      error.value = errorMessage(caught)
      errorCode.value = extractErrorCode(caught)
      return null
    } finally {
      submitting.value = false
    }
  }

  function reset(): void {
    ticket.value = null
    timeline.value = []
    pagination.value = null
    canChangeStatus.value = false
    canComment.value = false
    canSeeInternal.value = false
    loading.value = false
    timelineLoading.value = false
    submitting.value = false
    resolutionText.value = ''
    commentText.value = ''
    informationRequest.value = null
    canRequestInformation.value = false
    canRespondToInformation.value = false
    awaitingUserResponse.value = false
    reminderActive.value = false
    reminderDueAt.value = null
    informationRequestText.value = ''
    informationResponseText.value = ''
    notice.value = null
    resetInformationRequestId()
    resetInformationResponseId()
    clearError()
  }

  return {
    ticket,
    timeline,
    pagination,
    canChangeStatus,
    canComment,
    canSeeInternal,
    loading,
    timelineLoading,
    submitting,
    error,
    errorCode,
    resolutionText,
    commentText,
    informationRequest,
    canRequestInformation,
    canRespondToInformation,
    awaitingUserResponse,
    reminderActive,
    reminderDueAt,
    informationRequestText,
    informationResponseText,
    notice,
    hasInternalEntries,
    loadWorkflow,
    loadTimeline,
    refresh,
    transitionStatus,
    requestInformation,
    respondToInformation,
    addComment,
    reset,
  }
})
