import { flushPromises, mount } from '@vue/test-utils'
import type { VueWrapper } from '@vue/test-utils'
import axe from 'axe-core'
import { createPinia, setActivePinia } from 'pinia'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { ApiClientError } from '@/api/client'
import TicketAssigneeChangePanel from '@/components/tickets/TicketAssigneeChangePanel.vue'
import {
  escalateTicket,
  getAssigneeChangeOptions,
  reassignTicket,
} from '@/services/assigneeChange'
import { getTimeline, getWorkflow } from '@/services/ticketWorkflow'
import type {
  AssigneeChangeOptions,
  AssigneeChangeResponse,
  AssigneeRef,
} from '@/types/assigneeChange'
import type {
  TicketWorkflowSnapshot,
  TimelineResponse,
  WorkflowResponse,
} from '@/types/ticketWorkflow'

vi.mock('@/services/assigneeChange', () => ({
  getAssigneeChangeOptions: vi.fn(),
  reassignTicket: vi.fn(),
  escalateTicket: vi.fn(),
}))

vi.mock('@/services/ticketWorkflow', () => ({
  getWorkflow: vi.fn(),
  getTimeline: vi.fn(),
  transitionStatus: vi.fn(),
  addInternalComment: vi.fn(),
}))

const optionsMock = vi.mocked(getAssigneeChangeOptions)
const reassignMock = vi.mocked(reassignTicket)
const escalateMock = vi.mocked(escalateTicket)
const workflowMock = vi.mocked(getWorkflow)
const timelineMock = vi.mocked(getTimeline)

const REQUEST_1 = '00000000-0000-4000-8000-000000000001'
const REQUEST_2 = '00000000-0000-4000-8000-000000000002'

let pinia: ReturnType<typeof createPinia>
let randomUUIDMock: ReturnType<typeof vi.fn>

function assignee(overrides: Partial<AssigneeRef> = {}): AssigneeRef {
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
    status: 'abierto',
    current_assignee: assignee(),
    has_reassignment_candidates: true,
    has_available_escalation_target: true,
    reassignment_candidates: [
      assignee({
        id: 'u2',
        name: 'Técnico B',
        escalation_level: 'nivel_1',
        escalation_level_label: 'Nivel 1',
      }),
    ],
    escalation_targets: [
      {
        value: 'nivel_2',
        label: 'Nivel 2',
        technician_count: 2,
        is_available: true,
      },
      {
        value: 'especialista',
        label: 'Especialista',
        technician_count: 0,
        is_available: false,
      },
    ],
    ...overrides,
  }
}

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
    creator_id: 'u3',
    finalized_at: null,
    closed_at: null,
    updated_at: '2026-11-04T10:00:00Z',
    allowed_transitions: [{ value: 'en_progreso', label: 'En progreso' }],
    ...overrides,
  }
}

function makeWorkflow(capabilities: Partial<WorkflowResponse> = {}): WorkflowResponse {
  return {
    ticket: makeTicket(),
    can_change_status: true,
    can_comment_internally: true,
    can_view_internal: true,
    can_reassign: false,
    can_escalate: false,
    ...capabilities,
  }
}

function makeTimeline(): TimelineResponse {
  return {
    items: [],
    pagination: {
      page: 1,
      page_size: 50,
      total_items: 0,
      total_pages: 0,
      has_next: false,
      has_previous: false,
    },
  }
}

function makeResponse(
  overrides: Partial<AssigneeChangeResponse> = {},
): AssigneeChangeResponse {
  return {
    changed: true,
    message: null,
    ticket: makeTicket({ assignee_id: 'u2' }),
    previous_assignee: assignee(),
    new_assignee: assignee({ id: 'u2', name: 'Técnico B' }),
    change_kind: 'reassignment',
    from_escalation_level: 'nivel_1',
    from_escalation_level_label: 'Nivel 1',
    to_escalation_level: 'nivel_1',
    to_escalation_level_label: 'Nivel 1',
    timeline_entry: null,
    ...overrides,
  }
}

function mountPanel(props: Partial<{ canReassign: boolean; canEscalate: boolean }> = {}) {
  return mount(TicketAssigneeChangePanel, {
    props: {
      ticketId: 't1',
      ticket: makeTicket(),
      canReassign: true,
      canEscalate: true,
      ...props,
    },
    attachTo: document.body,
    global: { plugins: [pinia] },
  })
}

async function settle(): Promise<void> {
  await flushPromises()
  await flushPromises()
}

async function chooseMode(wrapper: VueWrapper, mode: 'reassign' | 'escalate') {
  await wrapper.find(`input[value="${mode}"]`).trigger('change')
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

describe('TicketAssigneeChangePanel', () => {
  beforeEach(() => {
    pinia = createPinia()
    setActivePinia(pinia)
    optionsMock.mockReset()
    reassignMock.mockReset()
    escalateMock.mockReset()
    workflowMock.mockReset()
    timelineMock.mockReset()
    optionsMock.mockResolvedValue(makeOptions())
    workflowMock.mockResolvedValue(
      makeWorkflow({ can_reassign: true, can_escalate: true }),
    )
    timelineMock.mockResolvedValue(makeTimeline())

    randomUUIDMock = vi.fn()
    randomUUIDMock.mockReturnValueOnce(REQUEST_1).mockReturnValue(REQUEST_2)
    vi.stubGlobal('crypto', { randomUUID: randomUUIDMock })
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('carga las opciones y muestra ambos modos según las capacidades', async () => {
    const wrapper = mountPanel()
    await settle()

    expect(optionsMock).toHaveBeenCalledWith('t1')
    expect(wrapper.text()).toContain('Cambiar responsable')
    expect(wrapper.text()).toContain('Reasignar a un compañero')
    expect(wrapper.text()).toContain('Escalar a un nivel superior')
    await chooseMode(wrapper, 'escalate')
    expect(wrapper.find('fieldset').exists()).toBe(true)
    expect(wrapper.text()).toContain('Nivel 2')
    expect(wrapper.text()).toContain('Sin técnicos disponibles')
  })

  it('no muestra el modo de escalado si canEscalate es false', async () => {
    const wrapper = mountPanel({ canEscalate: false })
    await settle()

    expect(wrapper.text()).toContain('Reasignar a un compañero')
    expect(wrapper.text()).not.toContain('Escalar a un nivel superior')
  })

  it('envía la reasignación con expected_updated_at, request_id y motivo normalizado', async () => {
    reassignMock.mockResolvedValue(makeResponse())

    const wrapper = mountPanel()
    await settle()

    await chooseMode(wrapper, 'reassign')
    await wrapper.find('#assignee-select').setValue('u2')
    await wrapper.find('#assignee-change-reason').setValue('  Motivo del cambio  ')
    await buttonByText(wrapper, 'Confirmar cambio').trigger('click')
    await settle()

    expect(reassignMock).toHaveBeenCalledWith('t1', {
      new_assignee_id: 'u2',
      reason: 'Motivo del cambio',
      expected_updated_at: '2026-11-04T10:00:00Z',
      request_id: REQUEST_1,
    })
    expect(wrapper.emitted('changed')).toHaveLength(1)
    expect(wrapper.emitted('notice')).toEqual([
      ['El cambio de responsable se ha aplicado.'],
    ])
    expect(
      (wrapper.find('#assignee-change-reason').element as HTMLTextAreaElement).value,
    ).toBe('')
  })

  it('envía el escalado sin identificador de persona', async () => {
    escalateMock.mockResolvedValue(
      makeResponse({
        change_kind: 'escalation',
        to_escalation_level: 'nivel_2',
        to_escalation_level_label: 'Nivel 2',
      }),
    )

    const wrapper = mountPanel()
    await settle()

    await chooseMode(wrapper, 'escalate')
    await wrapper.find('input[type="radio"][value="nivel_2"]').trigger('change')
    await wrapper.find('#assignee-change-reason').setValue('Escalado por volumen')
    await buttonByText(wrapper, 'Confirmar cambio').trigger('click')
    await settle()

    expect(escalateMock).toHaveBeenCalledTimes(1)
    const payload = escalateMock.mock.calls[0]?.[1]
    expect(payload).toEqual({
      target_level: 'nivel_2',
      reason: 'Escalado por volumen',
      expected_updated_at: '2026-11-04T10:00:00Z',
      request_id: REQUEST_1,
    })
    expect(payload).not.toHaveProperty('assignee_id')
  })

  it('mantiene deshabilitado el envío sin destino o con motivo vacío', async () => {
    const wrapper = mountPanel()
    await settle()

    await chooseMode(wrapper, 'reassign')
    expect(buttonByText(wrapper, 'Confirmar cambio').attributes('disabled')).toBeDefined()

    await wrapper.find('#assignee-select').setValue('u2')
    await wrapper.find('#assignee-change-reason').setValue('    ')
    const submit = buttonByText(wrapper, 'Confirmar cambio')
    expect(submit.attributes('disabled')).toBeDefined()

    await submit.trigger('click')
    await settle()

    expect(reassignMock).not.toHaveBeenCalled()
  })

  it('ante stale_ticket muestra el aviso, conserva el motivo y recarga datos', async () => {
    reassignMock.mockRejectedValue(
      new ApiClientError('conflict', 'conflicto', 409, 'stale_ticket'),
    )

    const wrapper = mountPanel()
    await settle()

    await chooseMode(wrapper, 'reassign')
    await wrapper.find('#assignee-select').setValue('u2')
    await wrapper.find('#assignee-change-reason').setValue('Motivo conservado')
    await buttonByText(wrapper, 'Confirmar cambio').trigger('click')
    await settle()

    expect(wrapper.text()).toContain('modificado por otra persona')
    expect(
      (wrapper.find('#assignee-change-reason').element as HTMLTextAreaElement).value,
    ).toBe('Motivo conservado')
    expect(workflowMock).toHaveBeenCalled()
    expect(optionsMock.mock.calls.length).toBeGreaterThanOrEqual(2)
    expect(wrapper.emitted('changed')).toHaveLength(1)
  })

  it('regenera el request_id tras request_id_reused y lo conserva en un reintento idéntico', async () => {
    reassignMock
      .mockRejectedValueOnce(
        new ApiClientError('conflict', 'reutilizado', 409, 'request_id_reused'),
      )
      .mockRejectedValueOnce(new ApiClientError('network', 'sin conexión'))
      .mockResolvedValueOnce(makeResponse())

    const wrapper = mountPanel()
    await settle()

    await chooseMode(wrapper, 'reassign')
    await wrapper.find('#assignee-select').setValue('u2')
    await wrapper.find('#assignee-change-reason').setValue('Motivo')
    await buttonByText(wrapper, 'Confirmar cambio').trigger('click')
    await settle()
    expect(wrapper.text()).toContain('La solicitud ya se utilizó con otros datos')

    await buttonByText(wrapper, 'Confirmar cambio').trigger('click')
    await settle()
    await buttonByText(wrapper, 'Confirmar cambio').trigger('click')
    await settle()

    expect(reassignMock.mock.calls[0]?.[1].request_id).toBe(REQUEST_1)
    expect(reassignMock.mock.calls[1]?.[1].request_id).toBe(REQUEST_2)
    expect(reassignMock.mock.calls[2]?.[1].request_id).toBe(REQUEST_2)
  })

  it('muestra los estados de acceso denegado y avisa al padre', async () => {
    optionsMock.mockRejectedValue(
      new ApiClientError('forbidden', 'sin permiso', 403, 'not_ticket_assignee'),
    )

    const wrapper = mountPanel()
    await settle()

    expect(wrapper.text()).toContain('Este ticket ya no está asignado a ti.')
    expect(wrapper.find('fieldset').exists()).toBe(false)
    expect(wrapper.find('#assignee-change-reason').exists()).toBe(false)
    expect(wrapper.emitted('changed')).toHaveLength(1)
  })

  it('muestra el aviso de ticket finalizado y no renderiza controles', async () => {
    optionsMock.mockRejectedValue(
      new ApiClientError('conflict', 'finalizado', 409, 'ticket_finalized'),
    )

    const wrapper = mountPanel()
    await settle()

    expect(wrapper.text()).toContain(
      'El ticket está finalizado y no admite cambios de responsable.',
    )
    expect(wrapper.find('button[type="radio"]').exists()).toBe(false)
  })

  it('expone errores de red con reintento y conserva los datos', async () => {
    optionsMock.mockRejectedValueOnce(new ApiClientError('network', 'sin conexión'))
    optionsMock.mockResolvedValueOnce(makeOptions())

    const wrapper = mountPanel()
    await settle()

    expect(wrapper.text()).toContain('No se pudo guardar el cambio')
    await buttonByText(wrapper, 'Reintentar').trigger('click')
    await settle()

    expect(optionsMock).toHaveBeenCalledTimes(2)
    expect(wrapper.text()).toContain('Reasignar a un compañero')
  })

  it('no tiene violaciones críticas de accesibilidad', async () => {
    document.documentElement.lang = 'es'
    const wrapper = mountPanel()
    await settle()
    await chooseMode(wrapper, 'reassign')

    const results = await axe.run(wrapper.element, {
      rules: { 'color-contrast': { enabled: false } },
    })
    expect(results.violations.filter((v) => v.impact === 'critical')).toEqual([])
  })
})
