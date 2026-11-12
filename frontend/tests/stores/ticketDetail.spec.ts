import { flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { ApiClientError } from '@/api/client'
import {
  addInternalComment,
  getTimeline,
  getWorkflow,
  transitionStatus,
} from '@/services/ticketWorkflow'
import { useTicketDetailStore } from '@/stores/ticketDetail'
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
  addInternalComment: vi.fn(),
}))

const getWorkflowMock = vi.mocked(getWorkflow)
const getTimelineMock = vi.mocked(getTimeline)
const transitionMock = vi.mocked(transitionStatus)
const addCommentMock = vi.mocked(addInternalComment)

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

describe('useTicketDetailStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    getWorkflowMock.mockReset()
    getTimelineMock.mockReset()
    transitionMock.mockReset()
    addCommentMock.mockReset()
    getWorkflowMock.mockResolvedValue(makeWorkflow())
    getTimelineMock.mockResolvedValue(makeTimeline())
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
})
