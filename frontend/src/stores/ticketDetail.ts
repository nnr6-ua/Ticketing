import { computed, ref } from 'vue'
import { defineStore } from 'pinia'

import { ApiClientError } from '@/api/client'
import {
  escalateTicket as postEscalation,
  getAssigneeChangeOptions,
  reassignTicket as postReassignment,
} from '@/services/assigneeChange'
import {
  addInternalComment,
  getTimeline,
  getWorkflow,
  transitionStatus as postStatusTransition,
} from '@/services/ticketWorkflow'
import type {
  AssigneeChangeOptions,
  AssigneeChangeResponse,
  EscalationRequest,
  ReassignmentRequest,
} from '@/types/assigneeChange'
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
  reason_required: 'Indica el motivo del cambio de responsable.',
  reason_too_long: 'El motivo no puede superar los 5.000 caracteres.',
  self_reassignment: 'No puedes reasignarte el ticket a ti mismo.',
  creator_not_assignable: 'Ese usuario no puede recibir este ticket.',
  invalid_reassignment_target:
    'Solo puedes reasignar a técnicos activos de tu equipo y de tu nivel.',
  assignee_unavailable:
    'El técnico seleccionado ya no está disponible. Actualiza la lista e inténtalo de nuevo.',
  invalid_escalation_level:
    'Debes elegir un nivel superior al del responsable actual.',
  no_higher_level: 'El ticket ya está en el nivel máximo de soporte.',
  no_technicians_available:
    'No hay técnicos disponibles en ese nivel en este momento.',
  ticket_finalized:
    'El ticket está finalizado y no admite cambios de responsable.',
  assignee_inconsistent:
    'El responsable del ticket no coincide con el último cambio registrado. Actualiza la información.',
  notification_not_found: 'No se ha encontrado la notificación.',
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
  const canReassign = ref(false)
  const canEscalate = ref(false)
  const loading = ref(false)
  const timelineLoading = ref(false)
  const submitting = ref(false)
  const error = ref<string | null>(null)
  const errorCode = ref<string | null>(null)
  const resolutionText = ref('')
  const commentText = ref('')
  const notice = ref<string | null>(null)
  const assigneeOptions = ref<AssigneeChangeOptions | null>(null)
  const assigneeOptionsLoading = ref(false)
  const assigneeSubmitting = ref(false)
  const assigneeError = ref<string | null>(null)
  const assigneeErrorCode = ref<string | null>(null)
  const assigneeNotice = ref<string | null>(null)

  // Secuencias para descartar respuestas de carga fuera de orden.
  let workflowSeq = 0
  let timelineSeq = 0
  let optionsSeq = 0

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
    can_reassign: boolean
    can_escalate: boolean
  }): void {
    ticket.value = response.ticket
    canChangeStatus.value = response.can_change_status
    canComment.value = response.can_comment_internally
    canSeeInternal.value = response.can_view_internal
    canReassign.value = response.can_reassign
    canEscalate.value = response.can_escalate
  }

  function applyTransitionTicket(snapshot: TicketWorkflowSnapshot): void {
    // El servidor solo rellena `allowed_transitions` cuando el usuario puede
    // cambiar el estado. Al cerrar el ticket la lista queda vacía, así que la
    // capacidad se revoca en la misma sesión sin esperar a otra carga.
    ticket.value = snapshot
    canChangeStatus.value =
      snapshot.status !== 'cerrado' && snapshot.allowed_transitions.length > 0
    if (snapshot.status === 'resuelto' || snapshot.status === 'cerrado') {
      canReassign.value = false
      canEscalate.value = false
    }
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
    canReassign.value = false
    canEscalate.value = false
    loading.value = false
    timelineLoading.value = false
    submitting.value = false
    resolutionText.value = ''
    commentText.value = ''
    notice.value = null
    assigneeOptions.value = null
    assigneeOptionsLoading.value = false
    assigneeSubmitting.value = false
    assigneeError.value = null
    assigneeErrorCode.value = null
    assigneeNotice.value = null
    clearError()
  }

  function clearAssigneeError(): void {
    assigneeError.value = null
    assigneeErrorCode.value = null
  }

  async function loadAssigneeOptions(
    ticketId: string,
    preserveError = false,
  ): Promise<void> {
    const sequence = ++optionsSeq
    assigneeOptionsLoading.value = true
    if (!preserveError) {
      clearAssigneeError()
    }
    try {
      const response = await getAssigneeChangeOptions(ticketId)
      if (sequence !== optionsSeq) {
        return
      }
      assigneeOptions.value = response
    } catch (caught) {
      if (sequence !== optionsSeq) {
        return
      }
      assigneeOptions.value = null
      assigneeError.value = errorMessage(caught)
      assigneeErrorCode.value = extractErrorCode(caught)
      if (assigneeErrorCode.value === 'not_ticket_assignee') {
        await loadWorkflow(ticketId)
      }
    } finally {
      if (sequence === optionsSeq) {
        assigneeOptionsLoading.value = false
      }
    }
  }

  const RELOAD_OPTIONS_CODES = new Set([
    'invalid_reassignment_target',
    'assignee_unavailable',
    'invalid_escalation_level',
    'no_higher_level',
    'no_technicians_available',
    'creator_not_assignable',
    'stale_ticket',
  ])

  const RELOAD_WORKFLOW_CODES = new Set([
    'stale_ticket',
    'ticket_finalized',
    'not_ticket_assignee',
    'assignee_inconsistent',
  ])

  async function runAssigneeChange(
    ticketId: string,
    command: () => Promise<AssigneeChangeResponse>,
    successMessage: string,
  ): Promise<AssigneeChangeResponse | null> {
    assigneeSubmitting.value = true
    clearAssigneeError()
    assigneeNotice.value = null
    try {
      const response = await command()
      if (response.changed) {
        assigneeNotice.value = successMessage
      } else if (response.message) {
        assigneeNotice.value = response.message
      }
      await refreshAfterAssigneeChange(ticketId)
      return response
    } catch (caught) {
      const message = errorMessage(caught)
      const code = extractErrorCode(caught)
      assigneeError.value = message
      assigneeErrorCode.value = code
      if (code && RELOAD_WORKFLOW_CODES.has(code)) {
        await loadWorkflow(ticketId)
      }
      if (code === 'stale_ticket') {
        await loadTimeline(ticketId)
      }
      if (code && RELOAD_OPTIONS_CODES.has(code)) {
        await loadAssigneeOptions(ticketId, true)
      }
      return null
    } finally {
      assigneeSubmitting.value = false
    }
  }

  async function reassign(
    ticketId: string,
    payload: ReassignmentRequest,
  ): Promise<AssigneeChangeResponse | null> {
    return runAssigneeChange(
      ticketId,
      () => postReassignment(ticketId, payload),
      'El cambio de responsable se ha aplicado.',
    )
  }

  async function escalate(
    ticketId: string,
    payload: EscalationRequest,
  ): Promise<AssigneeChangeResponse | null> {
    return runAssigneeChange(
      ticketId,
      () => postEscalation(ticketId, payload),
      'El cambio de responsable se ha aplicado.',
    )
  }

  async function refreshAfterAssigneeChange(ticketId: string): Promise<void> {
    await Promise.all([loadWorkflow(ticketId), loadTimeline(ticketId)])
    if (canReassign.value || canEscalate.value) {
      await loadAssigneeOptions(ticketId)
    } else {
      assigneeOptions.value = null
    }
  }

  return {
    ticket,
    timeline,
    pagination,
    canChangeStatus,
    canComment,
    canSeeInternal,
    canReassign,
    canEscalate,
    loading,
    timelineLoading,
    submitting,
    error,
    errorCode,
    resolutionText,
    commentText,
    notice,
    assigneeOptions,
    assigneeOptionsLoading,
    assigneeSubmitting,
    assigneeError,
    assigneeErrorCode,
    assigneeNotice,
    hasInternalEntries,
    loadWorkflow,
    loadTimeline,
    refresh,
    transitionStatus,
    addComment,
    loadAssigneeOptions,
    reassign,
    escalate,
    refreshAfterAssigneeChange,
    reset,
  }
})
