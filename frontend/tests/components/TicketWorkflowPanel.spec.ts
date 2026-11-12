import { flushPromises, mount } from '@vue/test-utils'
import type { VueWrapper } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { nextTick } from 'vue'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { ApiClientError } from '@/api/client'
import TicketWorkflowPanel from '@/components/tickets/TicketWorkflowPanel.vue'
import {
  addInternalComment,
  getTimeline,
  getWorkflow,
  transitionStatus,
} from '@/services/ticketWorkflow'
import { useTicketDetailStore } from '@/stores/ticketDetail'
import type {
  StatusTransitionResponse,
  TicketWorkflowSnapshot,
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

const REQUEST_1 = '00000000-0000-4000-8000-000000000001'
const REQUEST_2 = '00000000-0000-4000-8000-000000000002'
const REQUEST_3 = '00000000-0000-4000-8000-000000000003'
const REQUEST_4 = '00000000-0000-4000-8000-000000000004'
const COMMENT_REQUEST = '00000000-0000-4000-8000-000000000010'

let randomUUIDMock: ReturnType<typeof vi.fn>
let pinia: ReturnType<typeof createPinia>

function makeTicket(
  overrides: Partial<TicketWorkflowSnapshot> = {},
): TicketWorkflowSnapshot {
  return {
    id: 't1',
    number: 'TK-000501',
    title: 'Ticket de prueba',
    status: 'abierto',
    status_label: 'Abierto',
    assignee_id: 'u1',
    creator_id: 'u2',
    finalized_at: null,
    closed_at: null,
    updated_at: '2026-11-04T10:00:00Z',
    allowed_transitions: [
      { value: 'en_progreso', label: 'En progreso' },
      { value: 'resuelto', label: 'Resuelto' },
    ],
    ...overrides,
  }
}

function makeWorkflow(
  ticketOverrides: Partial<TicketWorkflowSnapshot> = {},
  capabilities: Partial<
    Pick<
      WorkflowResponse,
      'can_change_status' | 'can_comment_internally' | 'can_view_internal'
    >
  > = {},
): WorkflowResponse {
  return {
    ticket: makeTicket(ticketOverrides),
    can_change_status: true,
    can_comment_internally: true,
    can_view_internal: true,
    ...capabilities,
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

function mountPanel(): VueWrapper {
  return mount(TicketWorkflowPanel, {
    props: { ticketId: 't1' },
    attachTo: document.body,
    global: { plugins: [pinia] },
  })
}

function buttonByText(wrapper: VueWrapper, label: string) {
  const button = wrapper
    .findAll('button')
    .find((candidate) => candidate.text().includes(label))
  if (!button) {
    throw new Error(`No se encontró el botón «${label}».`)
  }
  return button
}

async function selectTarget(wrapper: VueWrapper, target: string): Promise<void> {
  await wrapper.find(`input[value="${target}"]`).trigger('change')
  await nextTick()
}

async function settle(): Promise<void> {
  await flushPromises()
  await nextTick()
  await flushPromises()
}

describe('TicketWorkflowPanel', () => {
  beforeEach(() => {
    pinia = createPinia()
    setActivePinia(pinia)
    getWorkflowMock.mockReset()
    getTimelineMock.mockReset()
    transitionMock.mockReset()
    addCommentMock.mockReset()
    getWorkflowMock.mockResolvedValue(makeWorkflow())
    getTimelineMock.mockResolvedValue(makeTimeline())

    randomUUIDMock = vi.fn()
    randomUUIDMock
      .mockReturnValueOnce(REQUEST_1)
      .mockReturnValueOnce(REQUEST_2)
      .mockReturnValueOnce(REQUEST_3)
      .mockReturnValueOnce(REQUEST_4)
      .mockReturnValue(COMMENT_REQUEST)
    vi.stubGlobal('crypto', { randomUUID: randomUUIDMock })
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('carga workflow y timeline y renderiza las capacidades', async () => {
    getTimelineMock.mockResolvedValue(
      makeTimeline([
        makeEntry(),
        makeEntry({
          id: 'i1',
          type: 'internal_comment',
          from_status: null,
          to_status: null,
          body: 'Nota privada.',
          is_internal: true,
        }),
      ]),
    )

    const wrapper = mountPanel()
    await settle()

    expect(getWorkflowMock).toHaveBeenCalledWith('t1')
    expect(getTimelineMock).toHaveBeenCalledWith('t1', 1, 50)
    expect(wrapper.text()).toContain('TK-000501')
    expect(wrapper.text()).toContain('Ticket de prueba')
    expect(wrapper.text()).toContain('Abierto')
    expect(wrapper.text()).toContain('Interno')
    expect(wrapper.text()).toContain('Nota privada.')
    expect(wrapper.find('#internal-comment').exists()).toBe(true)
  })

  it('muestra la carga de la timeline y no el estado vacío mientras se resuelve', async () => {
    let resolveTimeline!: (value: TimelineResponse) => void
    getTimelineMock.mockReturnValue(
      new Promise<TimelineResponse>((resolve) => {
        resolveTimeline = resolve
      }),
    )

    const wrapper = mountPanel()
    await settle()

    expect(wrapper.text()).toContain('Cargando la línea temporal…')
    expect(wrapper.text()).not.toContain(
      'Todavía no hay actividad en este ticket.',
    )

    resolveTimeline(makeTimeline([]))
    await settle()

    expect(wrapper.text()).not.toContain('Cargando la línea temporal…')
    expect(wrapper.text()).toContain('Todavía no hay actividad en este ticket.')
  })

  it('muestra «Reintentar» si falla la timeline con el ticket cargado y recarga workflow y timeline', async () => {
    getTimelineMock.mockRejectedValueOnce(
      new ApiClientError('server', 'boom', 500, 'internal_error'),
    )

    const wrapper = mountPanel()
    await settle()

    expect(wrapper.text()).toContain('TK-000501')
    expect(wrapper.text()).toContain('No se pudo guardar el cambio')
    const retry = buttonByText(wrapper, 'Reintentar')
    expect(retry.exists()).toBe(true)

    await retry.trigger('click')
    await settle()

    expect(getWorkflowMock).toHaveBeenCalledTimes(2)
    expect(getTimelineMock).toHaveBeenCalledTimes(2)
    expect(wrapper.text()).toContain('Técnica Asignada cambió el estado')
    expect(wrapper.text()).not.toContain('No se pudo guardar el cambio')
  })

  it('envía el cambio con expected_updated_at y request_id y refresca la timeline', async () => {
    transitionMock.mockResolvedValue({
      changed: true,
      message: null,
      ticket: makeTicket({
        status: 'en_progreso',
        status_label: 'En progreso',
        updated_at: '2026-11-04T10:05:00Z',
        allowed_transitions: [
          { value: 'pendiente_usuario', label: 'Pendiente de usuario' },
          { value: 'resuelto', label: 'Resuelto' },
        ],
      }),
      timeline_entries: [],
    })

    const wrapper = mountPanel()
    await settle()
    await selectTarget(wrapper, 'en_progreso')
    await buttonByText(wrapper, 'Guardar cambio').trigger('click')
    await settle()

    expect(transitionMock).toHaveBeenCalledTimes(1)
    expect(transitionMock.mock.calls[0]?.[1]).toEqual({
      target_status: 'en_progreso',
      expected_updated_at: '2026-11-04T10:00:00Z',
      request_id: REQUEST_1,
    })
    expect(getTimelineMock).toHaveBeenCalledTimes(2)
    expect(wrapper.text()).toContain('En progreso')
    expect(wrapper.find('[role="status"]').text()).toContain(
      'El estado del ticket se ha actualizado.',
    )
  })

  it('oculta los controles de estado al cerrar el ticket en la misma sesión', async () => {
    getWorkflowMock.mockResolvedValue(
      makeWorkflow({
        status: 'resuelto',
        status_label: 'Resuelto',
        finalized_at: '2026-11-04T09:00:00Z',
        allowed_transitions: [
          { value: 'en_progreso', label: 'En progreso' },
          { value: 'cerrado', label: 'Cerrado' },
        ],
      }),
    )
    transitionMock.mockResolvedValue({
      changed: true,
      message: null,
      ticket: makeTicket({
        status: 'cerrado',
        status_label: 'Cerrado',
        updated_at: '2026-11-04T10:05:00Z',
        finalized_at: '2026-11-04T09:00:00Z',
        closed_at: '2026-11-04T10:05:00Z',
        allowed_transitions: [],
      }),
      timeline_entries: [],
    })

    const wrapper = mountPanel()
    await settle()
    await selectTarget(wrapper, 'cerrado')
    await buttonByText(wrapper, 'Guardar cambio').trigger('click')
    await settle()

    expect(wrapper.text()).toContain(
      'El cierre es definitivo: este ticket ya no admite cambios de estado.',
    )
    expect(wrapper.find('fieldset').exists()).toBe(false)
    expect(wrapper.find('#resolution').exists()).toBe(false)
    expect(
      wrapper
        .findAll('button')
        .some((button) => button.text().includes('Guardar cambio')),
    ).toBe(false)
    // El formulario de comentario interno sigue disponible tras el cierre.
    expect(wrapper.find('#internal-comment').exists()).toBe(true)
  })

  it('bloquea el botón y muestra «Guardando…» mientras submitting es true', async () => {
    let resolveTransition!: (value: StatusTransitionResponse) => void
    transitionMock.mockReturnValue(
      new Promise((resolve) => {
        resolveTransition = resolve
      }),
    )

    const wrapper = mountPanel()
    await settle()
    await selectTarget(wrapper, 'en_progreso')
    await buttonByText(wrapper, 'Guardar cambio').trigger('click')

    const savingButton = buttonByText(wrapper, 'Guardando…')
    expect(savingButton.attributes('disabled')).toBeDefined()
    expect(wrapper.find('fieldset').attributes('disabled')).toBeDefined()

    resolveTransition({
      changed: true,
      message: null,
      ticket: makeTicket({
        status: 'en_progreso',
        status_label: 'En progreso',
        updated_at: '2026-11-04T10:05:00Z',
      }),
      timeline_entries: [],
    })
    await settle()

    expect(buttonByText(wrapper, 'Guardar cambio').attributes('disabled')).toBeDefined()
  })

  it('ante 409 stale_ticket avisa, recarga y conserva el texto y el request_id', async () => {
    transitionMock.mockRejectedValue(
      new ApiClientError('conflict', 'conflicto', 409, 'stale_ticket'),
    )

    const wrapper = mountPanel()
    await settle()
    await selectTarget(wrapper, 'resuelto')
    await wrapper.find('#resolution').setValue('  Solución conservada  ')
    await buttonByText(wrapper, 'Guardar cambio').trigger('click')
    await settle()

    expect(transitionMock.mock.calls[0]?.[1]).toMatchObject({
      target_status: 'resuelto',
      resolution: 'Solución conservada',
      request_id: REQUEST_1,
    })
    expect(getWorkflowMock).toHaveBeenCalledTimes(2)
    expect(getTimelineMock).toHaveBeenCalledTimes(2)
    expect(wrapper.text()).toContain('modificado por otra persona')
    expect(
      (wrapper.find('#resolution').element as HTMLTextAreaElement).value,
    ).toBe('  Solución conservada  ')

    transitionMock.mockResolvedValue({
      changed: true,
      message: null,
      ticket: makeTicket({
        status: 'resuelto',
        status_label: 'Resuelto',
        updated_at: '2026-11-04T10:05:00Z',
        finalized_at: '2026-11-04T10:05:00Z',
        allowed_transitions: [
          { value: 'en_progreso', label: 'En progreso' },
          { value: 'cerrado', label: 'Cerrado' },
        ],
      }),
      timeline_entries: [],
    })
    await buttonByText(wrapper, 'Guardar cambio').trigger('click')
    await settle()

    expect(transitionMock.mock.calls[1]?.[1].request_id).toBe(REQUEST_1)
    expect(wrapper.find('#resolution').exists()).toBe(false)
  })

  it('reutiliza el request_id solo en un reintento idéntico y lo regenera al cambiar destino o resolución', async () => {
    transitionMock.mockRejectedValue(
      new ApiClientError('network', 'sin conexión'),
    )

    const wrapper = mountPanel()
    await settle()
    await selectTarget(wrapper, 'en_progreso')

    await buttonByText(wrapper, 'Guardar cambio').trigger('click')
    await settle()
    await buttonByText(wrapper, 'Guardar cambio').trigger('click')
    await settle()

    expect(transitionMock.mock.calls[0]?.[1].request_id).toBe(REQUEST_1)
    expect(transitionMock.mock.calls[1]?.[1].request_id).toBe(REQUEST_1)

    await selectTarget(wrapper, 'resuelto')
    await wrapper.find('#resolution').setValue('Primera solución')
    await buttonByText(wrapper, 'Guardar cambio').trigger('click')
    await settle()
    expect(transitionMock.mock.calls[2]?.[1].request_id).toBe(REQUEST_2)

    await wrapper.find('#resolution').setValue('Segunda solución')
    await buttonByText(wrapper, 'Guardar cambio').trigger('click')
    await settle()
    expect(transitionMock.mock.calls[3]?.[1].request_id).toBe(REQUEST_3)
  })

  it('muestra el formulario solo para «Resuelto» y bloquea el envío sin texto', async () => {
    const wrapper = mountPanel()
    await settle()

    expect(wrapper.find('#resolution').exists()).toBe(false)

    await selectTarget(wrapper, 'resuelto')
    expect(wrapper.find('#resolution').exists()).toBe(true)
    expect(buttonByText(wrapper, 'Guardar cambio').attributes('disabled')).toBeDefined()

    await wrapper.find('#resolution').setValue('   ')
    expect(buttonByText(wrapper, 'Guardar cambio').attributes('disabled')).toBeDefined()

    await wrapper.find('#resolution').setValue('Solución válida')
    expect(buttonByText(wrapper, 'Guardar cambio').attributes('disabled')).toBeUndefined()
  })

  it('deshabilita el envío y marca el contador por encima de 5.000 caracteres', async () => {
    const wrapper = mountPanel()
    await settle()
    await selectTarget(wrapper, 'resuelto')

    await wrapper.find('#resolution').setValue('a'.repeat(5001))

    expect(wrapper.find('#resolution-counter').text()).toBe('5001 / 5000')
    expect(wrapper.find('#resolution-counter').classes()).toContain('text-red-700')
    expect(buttonByText(wrapper, 'Guardar cambio').attributes('disabled')).toBeDefined()
    expect(transitionMock).not.toHaveBeenCalled()
  })

  it('envía la resolución normalizada y limpia el texto solo tras el éxito', async () => {
    transitionMock.mockResolvedValue({
      changed: true,
      message: null,
      ticket: makeTicket({
        status: 'resuelto',
        status_label: 'Resuelto',
        updated_at: '2026-11-04T10:05:00Z',
        finalized_at: '2026-11-04T10:05:00Z',
        allowed_transitions: [
          { value: 'en_progreso', label: 'En progreso' },
          { value: 'cerrado', label: 'Cerrado' },
        ],
      }),
      timeline_entries: [],
    })

    const wrapper = mountPanel()
    await settle()
    await selectTarget(wrapper, 'resuelto')
    await wrapper.find('#resolution').setValue('  Solución final  ')
    await buttonByText(wrapper, 'Guardar cambio').trigger('click')
    await settle()

    expect(transitionMock.mock.calls[0]?.[1]).toMatchObject({
      target_status: 'resuelto',
      resolution: 'Solución final',
    })
    expect(wrapper.find('#resolution').exists()).toBe(false)
    expect(wrapper.find('[role="status"]').text()).toContain(
      'El estado del ticket se ha actualizado.',
    )
    expect(getTimelineMock).toHaveBeenCalledTimes(2)
  })

  it('omite resolution cuando el destino no es resuelto', async () => {
    transitionMock.mockResolvedValue({
      changed: true,
      message: null,
      ticket: makeTicket({
        status: 'en_progreso',
        status_label: 'En progreso',
        updated_at: '2026-11-04T10:05:00Z',
        allowed_transitions: [
          { value: 'pendiente_usuario', label: 'Pendiente de usuario' },
          { value: 'resuelto', label: 'Resuelto' },
        ],
      }),
      timeline_entries: [],
    })

    const wrapper = mountPanel()
    await settle()

    await selectTarget(wrapper, 'resuelto')
    await wrapper.find('#resolution').setValue('Texto que no debe enviarse')
    await selectTarget(wrapper, 'en_progreso')
    await buttonByText(wrapper, 'Guardar cambio').trigger('click')
    await settle()

    expect(transitionMock).toHaveBeenCalledTimes(1)
    expect(transitionMock.mock.calls[0]?.[1]).toEqual({
      target_status: 'en_progreso',
      expected_updated_at: '2026-11-04T10:00:00Z',
      request_id: REQUEST_1,
    })
    expect(transitionMock.mock.calls[0]?.[1]).not.toHaveProperty('resolution')
  })

  it('muestra el error de resolución, conserva el texto y mueve el foco al textarea', async () => {
    transitionMock.mockRejectedValue(
      new ApiClientError(
        'invalid',
        'Indica la descripción de la solución para marcar el ticket como Resuelto.',
        422,
        'resolution_required',
      ),
    )

    const wrapper = mountPanel()
    await settle()
    await selectTarget(wrapper, 'resuelto')
    await wrapper.find('#resolution').setValue('Texto que se conserva')
    await buttonByText(wrapper, 'Guardar cambio').trigger('click')
    await settle()

    const textarea = wrapper.find('#resolution').element as HTMLTextAreaElement
    expect(wrapper.find('#resolution-error').text()).toBe(
      'Indica la descripción de la solución para marcar el ticket como Resuelto.',
    )
    expect(textarea.value).toBe('Texto que se conserva')
    expect(document.activeElement).toBe(textarea)
    expect(transitionMock).toHaveBeenCalledTimes(1)
  })

  it('permite comentar en un ticket cerrado, refresca la timeline y limpia tras el éxito', async () => {
    getWorkflowMock.mockResolvedValue(
      makeWorkflow(
        {
          status: 'cerrado',
          status_label: 'Cerrado',
          finalized_at: '2026-11-04T09:00:00Z',
          closed_at: '2026-11-04T09:00:00Z',
          allowed_transitions: [],
        },
        {
          can_change_status: false,
          can_comment_internally: true,
          can_view_internal: true,
        },
      ),
    )
    getTimelineMock.mockResolvedValue(
      makeTimeline([
        makeEntry({
          id: 'i1',
          type: 'internal_comment',
          from_status: null,
          to_status: null,
          body: 'Nota privada.',
          is_internal: true,
        }),
      ]),
    )
    addCommentMock.mockResolvedValue({
      created: true,
      entry: makeEntry({
        id: 'i2',
        type: 'internal_comment',
        from_status: null,
        to_status: null,
        body: 'Nota nueva',
        is_internal: true,
      }),
    })

    const wrapper = mountPanel()
    await settle()

    expect(wrapper.text()).toContain(
      'El cierre es definitivo: este ticket ya no admite cambios de estado.',
    )
    expect(wrapper.text()).toContain('Nota privada.')
    expect(wrapper.find('#internal-comment').exists()).toBe(true)

    await wrapper.find('#internal-comment').setValue('  Nota nueva  ')
    await wrapper.find('form').trigger('submit')
    await settle()

    expect(addCommentMock).toHaveBeenCalledWith('t1', {
      body: 'Nota nueva',
      request_id: REQUEST_1,
    })
    expect(getTimelineMock).toHaveBeenCalledTimes(2)
    expect(
      (wrapper.find('#internal-comment').element as HTMLTextAreaElement).value,
    ).toBe('')
    expect(wrapper.find('[role="status"]').text()).toContain(
      'El comentario interno se ha añadido.',
    )
  })

  it('conserva el comentario si el alta falla y lo limpia en el reintento correcto', async () => {
    addCommentMock.mockRejectedValueOnce(
      new ApiClientError('network', 'sin conexión'),
    )
    addCommentMock.mockResolvedValueOnce({
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

    const wrapper = mountPanel()
    await settle()
    await wrapper.find('#internal-comment').setValue('Nota interna')
    await wrapper.find('form').trigger('submit')
    await settle()

    expect(
      (wrapper.find('#internal-comment').element as HTMLTextAreaElement).value,
    ).toBe('Nota interna')
    expect(wrapper.text()).toContain('No se pudo guardar el cambio')

    await wrapper.find('form').trigger('submit')
    await settle()

    expect(addCommentMock).toHaveBeenCalledTimes(2)
    expect(addCommentMock.mock.calls[1]?.[1].request_id).toBe(
      addCommentMock.mock.calls[0]?.[1].request_id,
    )
    expect(
      (wrapper.find('#internal-comment').element as HTMLTextAreaElement).value,
    ).toBe('')
  })

  it('no muestra entradas internas ni formulario de comentario sin capacidades', async () => {
    getWorkflowMock.mockResolvedValue(
      makeWorkflow(
        { allowed_transitions: [] },
        {
          can_change_status: false,
          can_comment_internally: false,
          can_view_internal: false,
        },
      ),
    )
    getTimelineMock.mockResolvedValue(
      makeTimeline([
        makeEntry({
          id: 'i1',
          type: 'internal_comment',
          from_status: null,
          to_status: null,
          body: 'Nota privada.',
          is_internal: true,
        }),
      ]),
    )

    const wrapper = mountPanel()
    await settle()

    expect(wrapper.text()).not.toContain('Nota privada.')
    expect(wrapper.find('[data-entry-type="internal_comment"]').exists()).toBe(false)
    expect(wrapper.find('#internal-comment').exists()).toBe(false)
    expect(wrapper.text()).toContain('No tienes permiso para cambiar el estado')
  })

  it('mantiene el estado del store alineado con el ticket cargado', async () => {
    const wrapper = mountPanel()
    await settle()

    const store = useTicketDetailStore(pinia)
    expect(store.ticket?.id).toBe('t1')
    expect(store.timeline).toHaveLength(1)
    expect(store.canChangeStatus).toBe(true)
    expect(store.canComment).toBe(true)
    expect(store.canSeeInternal).toBe(true)
    wrapper.unmount()
  })
})
