import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { ApiClientError } from '@/api/client'
import {
  addInternalComment,
  getTimeline,
  getWorkflow,
  requestInformation,
  respondToInformation,
  transitionStatus,
} from '@/services/ticketWorkflow'
import { useTicketDetailStore } from '@/stores/ticketDetail'
import type {
  InformationRequestResponse,
  InformationResponseResponse,
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

const getWorkflowMock = vi.mocked(getWorkflow)
const getTimelineMock = vi.mocked(getTimeline)
const requestMock = vi.mocked(requestInformation)
const responseMock = vi.mocked(respondToInformation)

const REQUEST_1 = '00000000-0000-4000-8000-000000000001'
const REQUEST_2 = '00000000-0000-4000-8000-000000000002'

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
    can_request_information: true,
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

function requestResponse(): InformationRequestResponse {
  return {
    changed: true,
    message: null,
    ticket: {
      ...makeWorkflow().ticket,
      status: 'pendiente_usuario',
      status_label: 'Pendiente de usuario',
      updated_at: '2026-11-04T10:05:00Z',
    },
    timeline_entries: [],
    information_request: {
      id: 'r1',
      body: '¿Qué navegador usas?',
      requested_at: '2026-11-04T10:05:00Z',
      requested_by: { id: 'u1', name: 'Técnica Asignada', role: 'tecnico' },
    },
  }
}

function informationResponse(): InformationResponseResponse {
  return {
    changed: true,
    message: null,
    ticket: {
      ...makeWorkflow().ticket,
      status: 'en_progreso',
      updated_at: '2026-11-04T10:10:00Z',
    },
    timeline_entries: [],
    information_response: makeEntry({
      id: 'e2',
      type: 'user_response',
      from_status: null,
      to_status: null,
      body: 'Uso Chrome 131.',
      reply_to_id: 'r1',
    }),
  }
}

describe('useTicketDetailStore (información)', () => {
  let uuidCalls: string[]

  beforeEach(() => {
    setActivePinia(createPinia())
    getWorkflowMock.mockReset()
    getTimelineMock.mockReset()
    requestMock.mockReset()
    responseMock.mockReset()
    getWorkflowMock.mockResolvedValue(makeWorkflow())
    getTimelineMock.mockResolvedValue(makeTimeline())

    uuidCalls = [REQUEST_1, REQUEST_2]
    vi.stubGlobal('crypto', {
      randomUUID: vi.fn(() => uuidCalls.shift() ?? REQUEST_2),
    })
  })

  it('envía la petición normalizada y refresca workflow y timeline', async () => {
    const base = makeWorkflow()
    getWorkflowMock
      .mockResolvedValueOnce(base)
      .mockResolvedValue(
        makeWorkflow({
          ticket: {
            ...base.ticket,
            status: 'pendiente_usuario',
            status_label: 'Pendiente de usuario',
            updated_at: '2026-11-04T10:05:00Z',
          },
        }),
      )
    const store = useTicketDetailStore()
    await store.loadWorkflow('t1')
    requestMock.mockResolvedValue(requestResponse())

    store.informationRequestText = '  ¿Qué navegador usas?  '
    const result = await store.requestInformation('t1', store.informationRequestText)

    expect(result?.changed).toBe(true)
    expect(requestMock).toHaveBeenCalledWith('t1', {
      body: '¿Qué navegador usas?',
      expected_updated_at: '2026-11-04T10:00:00Z',
      request_id: REQUEST_1,
    })
    expect(store.informationRequestText).toBe('')
    expect(store.notice).toBe('La petición de información se ha enviado.')
    expect(store.ticket?.status).toBe('pendiente_usuario')
    expect(getWorkflowMock).toHaveBeenCalledTimes(2)
    expect(getTimelineMock).toHaveBeenCalledTimes(1)
  })

  it('envía la respuesta normalizada y refresca el ticket', async () => {
    const store = useTicketDetailStore()
    await store.loadWorkflow('t1')
    responseMock.mockResolvedValue(informationResponse())

    store.informationResponseText = '  Uso Chrome 131.  '
    const result = await store.respondToInformation(
      't1',
      store.informationResponseText,
    )

    expect(result?.changed).toBe(true)
    expect(responseMock).toHaveBeenCalledWith('t1', {
      body: 'Uso Chrome 131.',
      expected_updated_at: '2026-11-04T10:00:00Z',
      request_id: REQUEST_1,
    })
    expect(store.informationResponseText).toBe('')
    expect(store.notice).toBe('Tu respuesta se ha enviado.')
    expect(store.ticket?.status).toBe('en_progreso')
  })

  it('regenera request_id y recarga tras stale_ticket', async () => {
    const store = useTicketDetailStore()
    await store.loadWorkflow('t1')
    requestMock
      .mockRejectedValueOnce(
        new ApiClientError(
          'conflict',
          'El ticket ha sido modificado.',
          409,
          'stale_ticket',
        ),
      )
      .mockResolvedValueOnce(requestResponse())

    const first = await store.requestInformation('t1', 'Datos')
    expect(first).toBeNull()
    expect(store.errorCode).toBe('stale_ticket')
    expect(getWorkflowMock).toHaveBeenCalledTimes(2)

    const second = await store.requestInformation('t1', 'Datos')
    expect(second?.changed).toBe(true)
    expect(requestMock.mock.calls[1]?.[1].request_id).toBe(REQUEST_2)
  })

  it('conserva request_id en errores de red', async () => {
    const store = useTicketDetailStore()
    await store.loadWorkflow('t1')
    requestMock
      .mockRejectedValueOnce(
        new ApiClientError('network', 'No se pudo conectar con el servidor.'),
      )
      .mockResolvedValueOnce(requestResponse())

    await store.requestInformation('t1', 'Datos')
    await store.requestInformation('t1', 'Datos')

    expect(requestMock.mock.calls[0]?.[1].request_id).toBe(REQUEST_1)
    expect(requestMock.mock.calls[1]?.[1].request_id).toBe(REQUEST_1)
  })

  it('regenera request_id y refresca capacidades si ya había petición abierta', async () => {
    const store = useTicketDetailStore()
    await store.loadWorkflow('t1')
    requestMock
      .mockRejectedValueOnce(
        new ApiClientError(
          'conflict',
          'Ya hay una petición pendiente.',
          409,
          'information_request_already_open',
        ),
      )
      .mockResolvedValueOnce(requestResponse())

    await store.requestInformation('t1', 'Datos')
    expect(store.errorCode).toBe('information_request_already_open')
    expect(getWorkflowMock).toHaveBeenCalledTimes(2)

    await store.requestInformation('t1', 'Datos')
    expect(requestMock.mock.calls[1]?.[1].request_id).toBe(REQUEST_2)
  })

  it('regenera request_id de la respuesta tras invalid_transition', async () => {
    const store = useTicketDetailStore()
    await store.loadWorkflow('t1')
    responseMock
      .mockRejectedValueOnce(
        new ApiClientError(
          'conflict',
          'Transición no permitida.',
          409,
          'invalid_transition',
        ),
      )
      .mockResolvedValueOnce(informationResponse())

    await store.respondToInformation('t1', 'Respuesta')
    await store.respondToInformation('t1', 'Respuesta')

    expect(responseMock.mock.calls[0]?.[1].request_id).toBe(REQUEST_1)
    expect(responseMock.mock.calls[1]?.[1].request_id).toBe(REQUEST_2)
  })
})
