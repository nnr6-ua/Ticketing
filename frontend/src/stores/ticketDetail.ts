import { computed, ref } from 'vue'
import { defineStore } from 'pinia'

import { ApiClientError } from '@/api/client'
import {
  addInternalComment,
  getTimeline,
  getWorkflow,
  transitionStatus as postStatusTransition,
} from '@/services/ticketWorkflow'
import type {
  InternalCommentResponse,
  Pagination,
  StatusTransitionRequest,
  StatusTransitionResponse,
  TicketWorkflowSnapshot,
  TimelineEntry,
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
  const notice = ref<string | null>(null)

  // Secuencias para descartar respuestas de carga fuera de orden.
  let workflowSeq = 0
  let timelineSeq = 0

  const hasInternalEntries = computed(() =>
    timeline.value.some((entry) => entry.type === 'internal_comment'),
  )

  function clearError(): void {
    error.value = null
    errorCode.value = null
  }

  function applyWorkflow(response: {
    ticket: TicketWorkflowSnapshot
    can_change_status: boolean
    can_comment_internally: boolean
    can_view_internal: boolean
  }): void {
    ticket.value = response.ticket
    canChangeStatus.value = response.can_change_status
    canComment.value = response.can_comment_internally
    canSeeInternal.value = response.can_view_internal
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
    notice.value = null
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
    notice,
    hasInternalEntries,
    loadWorkflow,
    loadTimeline,
    refresh,
    transitionStatus,
    addComment,
    reset,
  }
})
