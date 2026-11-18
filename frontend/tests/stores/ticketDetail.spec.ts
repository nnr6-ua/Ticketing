import { flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { ApiClientError } from '@/api/client'
import {
  escalateTicket,
  getAssigneeChangeOptions,
  reassignTicket,
} from '@/services/assigneeChange'
import {
  addInternalComment,
  getTimeline,
  getWorkflow,
  transitionStatus,
} from '@/services/ticketWorkflow'
import { useTicketDetailStore } from '@/stores/ticketDetail'
import type {
  AssigneeChangeOptions,
  AssigneeChangeResponse,
  AssigneeRef,
  EscalationRequest,
  ReassignmentRequest,
} from '@/types/assigneeChange'
import type {
  StatusTransitionRequest,
  TimelineEntry,
  TimelineResponse,
  WorkflowResponse,
} from '@/types/ticketWorkflow'

vi.mock('@/services/ticketWorkflow', () => ({
  getWorkflow: vi.fn(),
  getTimeline: vi.fn(),
  transitionStatus: vi.fn(),
  requestInformation: vi.fn(),
  respondToInformation: vi.fn(),
  addInternalComment: vi.fn(),
}))

vi.mock('@/services/assigneeChange', () => ({
  getAssigneeChangeOptions: vi.fn(),
  reassignTicket: vi.fn(),
  escalateTicket: vi.fn(),
}))

const getWorkflowMock = vi.mocked(getWorkflow)
const getTimelineMock = vi.mocked(getTimeline)
const transitionMock = vi.mocked(transitionStatus)
const addCommentMock = vi.mocked(addInternalComment)
const optionsMock = vi.mocked(getAssigneeChangeOptions)
const reassignMock = vi.mocked(reassignTicket)
const escalateMock = vi.mocked(escalateTicket)

function makeWorkflow(overrides: Partial<WorkflowResponse> = {}): WorkflowResponse {
  return {
    ticket: {
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
    },
    can_change_status: true,
    can_comment_internally: true,
    can_view_internal: true,
    can_request_information: false,
    can_respond_to_information: false,
    awaiting_user_response: false,
    active_information_request: null,
    reminder_active: false,
    reminder_due_at: null,
    can_reassign: false,
    can_escalate: false,
    ...overrides,
  }
}

function makeEntry(overrides: Partial<TimelineEntry> = {}): TimelineEntry {
  return {
    id: 'e1',
    type: 'status_change',
    from_status: 'abierto',
    to_status: 'en_progreso',
    body: null,
    is_internal: false,
    author: { id: 'u1', name: 'Técnica Asignada', role: 'tecnico' },
    created_at: '2026-11-04T10:00:00Z',
    reply_to_id: null,
    change_kind: null,
    previous_assignee: null,
    new_assignee: null,
    from_escalation_level: null,
    from_escalation_level_label: null,
    to_escalation_level: null,
    to_escalation_level_label: null,
    ...overrides,
  }
}

function makeTimeline(entries: TimelineEntry[] = [makeEntry()]): TimelineResponse {
  return {
    items: entries,
    pagination: {
      page: 1,
      page_size: 50,
      total_items: entries.length,
      total_pages: entries.length > 0 ? 1 : 0,
      has_next: false,
      has_previous: false,
    },
  }
}

function makeAssignee(overrides: Partial<AssigneeRef> = {}): AssigneeRef {
  return {
    id: 'u1',
    name: 'Técnica Asignada',
    role: 'tecnico',
    team: 'Soporte',
    escalation_level: 'nivel_1',
    escalation_level_label: 'Nivel 1',
    ...overrides,
  }
}

function makeOptions(
  overrides: Partial<AssigneeChangeOptions> = {},
): AssigneeChangeOptions {
  return {
    ticket_id: 't1',
    status: 'en_progreso',
    current_assignee: makeAssignee(),
    has_reassignment_candidates: true,
    has_available_escalation_target: true,
    reassignment_candidates: [
      makeAssignee({ id: 'u3', name: 'Técnico B' }),
    ],
    escalation_targets: [
      {
        value: 'nivel_2',
        label: 'Nivel 2',
        technician_count: 2,
        is_available: true,
      },
    ],
    ...overrides,
  }
}

function makeChangeResponse(
  overrides: Partial<AssigneeChangeResponse> = {},
): AssigneeChangeResponse {
  return {
    changed: true,
    message: null,
    ticket: {
      ...makeWorkflow().ticket,
      assignee_id: 'u3',
      updated_at: '2026-11-04T10:05:00Z',
    },
    previous_assignee: makeAssignee(),
    new_assignee: makeAssignee({ id: 'u3', name: 'Técnico B' }),
    change_kind: 'reassignment',
    from_escalation_level: 'nivel_1',
    from_escalation_level_label: 'Nivel 1',
    to_escalation_level: 'nivel_1',
    to_escalation_level_label: 'Nivel 1',
    timeline_entry: makeEntry({
      id: 'ac1',
      type: 'assignee_change',
      from_status: null,
      to_status: null,
      change_kind: 'reassignment',
      previous_assignee: makeAssignee(),
      new_assignee: makeAssignee({ id: 'u3', name: 'Técnico B' }),
      body: 'Motivo del cambio.',
    }),
    ...overrides,
  }
}

const REASSIGN_PAYLOAD: ReassignmentRequest = {
  new_assignee_id: 'u3',
  reason: 'Motivo del cambio',
  expected_updated_at: '2026-11-04T10:00:00Z',
  request_id: '00000000-0000-4000-8000-000000000021',
}

const ESCALATE_PAYLOAD: EscalationRequest = {
  target_level: 'nivel_2',
  reason: 'Escalado por volumen',
  expected_updated_at: '2026-11-04T10:00:00Z',
  request_id: '00000000-0000-4000-8000-000000000022',
}

describe('useTicketDetailStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    getWorkflowMock.mockReset()
    getTimelineMock.mockReset()
    transitionMock.mockReset()
    addCommentMock.mockReset()
    optionsMock.mockReset()
    reassignMock.mockReset()
    escalateMock.mockReset()
    getWorkflowMock.mockResolvedValue(makeWorkflow())
    getTimelineMock.mockResolvedValue(makeTimeline())
    optionsMock.mockResolvedValue(makeOptions())
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('loadWorkflow y loadTimeline pueblan el estado y las capacidades', async () => {
    const store = useTicketDetailStore()

    await store.loadWorkflow('t1')
    await store.loadTimeline('t1')

    expect(store.ticket?.number).toBe('TK-000501')
    expect(store.canChangeStatus).toBe(true)
    expect(store.canComment).toBe(true)
    expect(store.canSeeInternal).toBe(true)
    expect(store.timeline).toHaveLength(1)
    expect(store.pagination?.total_items).toBe(1)
    expect(store.loading).toBe(false)
    expect(store.error).toBeNull()
  })

  it('expone timelineLoading mientras se resuelve la línea temporal', async () => {
    const store = useTicketDetailStore()
    await store.loadWorkflow('t1')

    let resolveTimeline!: (value: TimelineResponse) => void
    getTimelineMock.mockReturnValue(
      new Promise<TimelineResponse>((resolve) => {
        resolveTimeline = resolve
      }),
    )

    const pending = store.loadTimeline('t1')
    expect(store.timelineLoading).toBe(true)
    expect(store.timeline).toHaveLength(0)

    resolveTimeline(makeTimeline([]))
    await pending

    expect(store.timelineLoading).toBe(false)
    expect(store.timeline).toHaveLength(0)
  })

  it('envía expected_updated_at y request_id y refresca la timeline tras el éxito', async () => {
    const store = useTicketDetailStore()
    await store.loadWorkflow('t1')
    await store.loadTimeline('t1')
    transitionMock.mockResolvedValue({
      changed: true,
      message: null,
      ticket: {
        ...makeWorkflow().ticket,
        status: 'resuelto',
        status_label: 'Resuelto',
        updated_at: '2026-11-04T10:05:00Z',
        finalized_at: '2026-11-04T10:05:00Z',
      },
      timeline_entries: [],
    })
    getTimelineMock.mockResolvedValue(
      makeTimeline([
        makeEntry(),
        makeEntry({
          id: 'e2',
          type: 'resolution',
          from_status: null,
          to_status: 'resuelto',
          body: 'Solución.',
        }),
      ]),
    )
    const payload: StatusTransitionRequest = {
      target_status: 'resuelto',
      resolution: 'Solución.',
      expected_updated_at: '2026-11-04T10:00:00Z',
      request_id: '00000000-0000-4000-8000-000000000001',
    }

    const response = await store.transitionStatus('t1', payload)

    expect(transitionMock).toHaveBeenCalledWith('t1', payload)
    expect(response?.changed).toBe(true)
    expect(store.ticket?.status).toBe('resuelto')
    expect(store.timeline).toHaveLength(2)
    expect(getTimelineMock).toHaveBeenCalledTimes(2)
    expect(store.notice).toBe('El estado del ticket se ha actualizado.')
  })

  it('revoca canChangeStatus al cerrar el ticket en la misma sesión', async () => {
    const store = useTicketDetailStore()
    await store.loadWorkflow('t1')
    await store.loadTimeline('t1')
    expect(store.canChangeStatus).toBe(true)

    transitionMock.mockResolvedValue({
      changed: true,
      message: null,
      ticket: {
        ...makeWorkflow().ticket,
        status: 'cerrado',
        status_label: 'Cerrado',
        updated_at: '2026-11-04T10:05:00Z',
        finalized_at: '2026-11-04T10:05:00Z',
        closed_at: '2026-11-04T10:05:00Z',
        allowed_transitions: [],
      },
      timeline_entries: [],
    })

    await store.transitionStatus('t1', {
      target_status: 'cerrado',
      expected_updated_at: '2026-11-04T10:00:00Z',
      request_id: '00000000-0000-4000-8000-000000000004',
    })

    expect(store.ticket?.status).toBe('cerrado')
    expect(store.canChangeStatus).toBe(false)
    expect(store.canComment).toBe(true)
  })

  it('ante 409 stale_ticket recarga workflow y timeline y conserva los textos', async () => {
    const store = useTicketDetailStore()
    await store.loadWorkflow('t1')
    await store.loadTimeline('t1')
    store.resolutionText = 'Solución escrita'
    store.commentText = 'Comentario escrito'
    transitionMock.mockRejectedValue(
      new ApiClientError('conflict', 'conflicto', 409, 'stale_ticket'),
    )

    const response = await store.transitionStatus('t1', {
      target_status: 'resuelto',
      resolution: 'Solución escrita',
      expected_updated_at: '2026-11-04T10:00:00Z',
      request_id: '00000000-0000-4000-8000-000000000002',
    })

    expect(response).toBeNull()
    expect(getWorkflowMock).toHaveBeenCalledTimes(2)
    expect(getTimelineMock).toHaveBeenCalledTimes(2)
    expect(store.errorCode).toBe('stale_ticket')
    expect(store.error).toContain('modificado por otra persona')
    expect(store.resolutionText).toBe('Solución escrita')
    expect(store.commentText).toBe('Comentario escrito')
    expect(store.submitting).toBe(false)
  })

  it('expone el error sin perder el estado previo', async () => {
    const store = useTicketDetailStore()
    await store.loadWorkflow('t1')
    await store.loadTimeline('t1')
    await flushPromises()

    getWorkflowMock.mockRejectedValue(
      new ApiClientError('server', 'boom', 500, 'internal_error'),
    )
    await store.loadWorkflow('t1')

    expect(store.errorCode).toBe('internal_error')
    expect(store.error).toContain('No se pudo guardar el cambio')
    expect(store.ticket?.number).toBe('TK-000501')
    expect(store.timeline).toHaveLength(1)
  })

  it('addComment limpia el texto y refresca la timeline tras el alta', async () => {
    const store = useTicketDetailStore()
    await store.loadWorkflow('t1')
    await store.loadTimeline('t1')
    store.commentText = '  Nota interna  '
    addCommentMock.mockResolvedValue({
      created: true,
      entry: makeEntry({
        id: 'i1',
        type: 'internal_comment',
        from_status: null,
        to_status: null,
        body: 'Nota interna',
        is_internal: true,
      }),
    })

    const response = await store.addComment(
      't1',
      '00000000-0000-4000-8000-000000000003',
    )

    expect(response?.created).toBe(true)
    expect(addCommentMock).toHaveBeenCalledWith('t1', {
      body: 'Nota interna',
      request_id: '00000000-0000-4000-8000-000000000003',
    })
    expect(store.commentText).toBe('')
    expect(getTimelineMock).toHaveBeenCalledTimes(2)
    expect(store.notice).toBe('El comentario interno se ha añadido.')
  })

  it('reasigna con el payload recibido y refresca workflow, timeline y opciones en orden', async () => {
    getWorkflowMock.mockResolvedValue(
      makeWorkflow({ can_reassign: true, can_escalate: true }),
    )
    reassignMock.mockResolvedValue(makeChangeResponse())

    const store = useTicketDetailStore()
    await store.loadWorkflow('t1')
    await store.loadTimeline('t1')

    const response = await store.reassign('t1', REASSIGN_PAYLOAD)

    expect(reassignMock).toHaveBeenCalledWith('t1', REASSIGN_PAYLOAD)
    expect(response?.changed).toBe(true)
    expect(store.assigneeNotice).toBe('El cambio de responsable se ha aplicado.')
    expect(store.assigneeSubmitting).toBe(false)
    expect(store.assigneeError).toBeNull()
    expect(getWorkflowMock).toHaveBeenCalledTimes(2)
    expect(getTimelineMock).toHaveBeenCalledTimes(2)
    expect(optionsMock).toHaveBeenCalledWith('t1')

    const workflowOrder = getWorkflowMock.mock.invocationCallOrder[1] ?? 0
    const timelineOrder = getTimelineMock.mock.invocationCallOrder[1] ?? 0
    const optionsOrder = optionsMock.mock.invocationCallOrder[0] ?? 0
    expect(workflowOrder).toBeLessThan(optionsOrder)
    expect(timelineOrder).toBeLessThan(optionsOrder)
  })

  it('escala con la acción de escalado y sin identificador de persona', async () => {
    getWorkflowMock.mockResolvedValue(
      makeWorkflow({ can_reassign: true, can_escalate: true }),
    )
    escalateMock.mockResolvedValue(
      makeChangeResponse({
        change_kind: 'escalation',
        to_escalation_level: 'nivel_2',
        to_escalation_level_label: 'Nivel 2',
      }),
    )

    const store = useTicketDetailStore()
    await store.loadWorkflow('t1')
    await store.loadTimeline('t1')

    await store.escalate('t1', ESCALATE_PAYLOAD)

    expect(escalateMock).toHaveBeenCalledWith('t1', ESCALATE_PAYLOAD)
    expect(reassignMock).not.toHaveBeenCalled()
    expect(ESCALATE_PAYLOAD).not.toHaveProperty('assignee_id')
    expect(store.assigneeNotice).toBe('El cambio de responsable se ha aplicado.')
  })

  it('ante stale_ticket conserva el error, recarga workflow, timeline y opciones', async () => {
    getWorkflowMock.mockResolvedValue(
      makeWorkflow({ can_reassign: true, can_escalate: true }),
    )
    reassignMock.mockRejectedValue(
      new ApiClientError('conflict', 'conflicto', 409, 'stale_ticket'),
    )

    const store = useTicketDetailStore()
    await store.loadWorkflow('t1')
    await store.loadTimeline('t1')

    const response = await store.reassign('t1', REASSIGN_PAYLOAD)

    expect(response).toBeNull()
    expect(store.assigneeErrorCode).toBe('stale_ticket')
    expect(store.assigneeError).toContain('modificado por otra persona')
    expect(store.assigneeSubmitting).toBe(false)
    expect(getWorkflowMock).toHaveBeenCalledTimes(2)
    expect(getTimelineMock).toHaveBeenCalledTimes(2)
    expect(optionsMock).toHaveBeenCalledTimes(1)
    expect(store.assigneeErrorCode).toBe('stale_ticket')
  })

  it('mapea request_id_reused, validación, 401 y red a mensajes estables', async () => {
    const store = useTicketDetailStore()
    await store.loadWorkflow('t1')

    reassignMock.mockRejectedValueOnce(
      new ApiClientError('conflict', 'reutilizado', 409, 'request_id_reused'),
    )
    await store.reassign('t1', REASSIGN_PAYLOAD)
    expect(store.assigneeErrorCode).toBe('request_id_reused')
    expect(store.assigneeError).toContain('La solicitud ya se utilizó')

    reassignMock.mockRejectedValueOnce(
      new ApiClientError('invalid', 'destino', 422, 'invalid_reassignment_target'),
    )
    await store.reassign('t1', REASSIGN_PAYLOAD)
    expect(store.assigneeErrorCode).toBe('invalid_reassignment_target')
    expect(store.assigneeError).toContain('técnicos activos de tu equipo')

    reassignMock.mockRejectedValueOnce(
      new ApiClientError('unauthorized', 'sesión', 401, 'not_authenticated'),
    )
    await store.reassign('t1', REASSIGN_PAYLOAD)
    expect(store.assigneeErrorCode).toBe('not_authenticated')
    expect(store.assigneeError).toContain('sesión no es válida')

    reassignMock.mockRejectedValueOnce(
      new ApiClientError('network', 'sin conexión'),
    )
    await store.reassign('t1', REASSIGN_PAYLOAD)
    expect(store.assigneeErrorCode).toBeNull()
    expect(store.assigneeError).toContain('No se pudo guardar el cambio')
  })

  it('descarta respuestas fuera de orden al cargar las opciones', async () => {
    let resolveFirst!: (value: AssigneeChangeOptions) => void
    optionsMock.mockImplementationOnce(
      () =>
        new Promise<AssigneeChangeOptions>((resolve) => {
          resolveFirst = resolve
        }),
    )
    const store = useTicketDetailStore()

    const first = store.loadAssigneeOptions('t1')
    optionsMock.mockResolvedValueOnce(
      makeOptions({
        reassignment_candidates: [makeAssignee({ id: 'u9', name: 'Última' })],
      }),
    )
    const second = store.loadAssigneeOptions('t1')
    await second

    resolveFirst(makeOptions({ reassignment_candidates: [] }))
    await first

    expect(store.assigneeOptions?.reassignment_candidates[0]?.id).toBe('u9')
    expect(store.assigneeOptionsLoading).toBe(false)
  })

  it('refleja la entrada assignee_change en menos de 2 s tras confirmar', async () => {
    const assigneeEntry = makeEntry({
      id: 'ac-latency',
      type: 'assignee_change',
      from_status: null,
      to_status: null,
      change_kind: 'reassignment',
      previous_assignee: makeAssignee(),
      new_assignee: makeAssignee({ id: 'u3', name: 'Técnico B' }),
      body: 'Motivo del cambio.',
    })
    getWorkflowMock.mockResolvedValue(
      makeWorkflow({ can_reassign: true, can_escalate: true }),
    )
    const store = useTicketDetailStore()
    await store.loadWorkflow('t1')
    await store.loadTimeline('t1')

    vi.useFakeTimers()
    getTimelineMock.mockResolvedValue(makeTimeline([assigneeEntry]))
    reassignMock.mockImplementation(
      () =>
        new Promise((resolve) => {
          setTimeout(() => resolve(makeChangeResponse()), 800)
        }),
    )

    const started = Date.now()
    const pending = store.reassign('t1', REASSIGN_PAYLOAD)
    await vi.advanceTimersByTimeAsync(800)
    await pending

    expect(
      store.timeline.some((entry) => entry.type === 'assignee_change'),
    ).toBe(true)
    expect(Date.now() - started).toBeLessThan(2000)
  })
})
