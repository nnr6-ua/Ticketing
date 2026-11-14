import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import TicketTimeline from '@/components/tickets/TicketTimeline.vue'
import type { TimelineEntry } from '@/types/ticketWorkflow'

function entry(overrides: Partial<TimelineEntry>): TimelineEntry {
  return {
    id: 'entry-1',
    type: 'status_change',
    from_status: 'abierto',
    to_status: 'en_progreso',
    body: null,
    is_internal: false,
    author: { id: 'u1', name: 'Técnica Asignada', role: 'tecnico' },
    created_at: '2026-11-02T10:16:00Z',
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

describe('TicketTimeline', () => {
  it('respeta el orden recibido del backend', () => {
    const wrapper = mount(TicketTimeline, {
      props: {
        canSeeInternal: true,
        entries: [
          entry({ id: 'a', created_at: '2026-11-02T10:00:00Z' }),
          entry({
            id: 'b',
            type: 'resolution',
            from_status: null,
            to_status: 'resuelto',
            body: 'Solución.',
            created_at: '2026-11-02T10:05:00Z',
          }),
        ],
      },
    })

    const items = wrapper.findAll('[data-entry-type]')
    expect(items).toHaveLength(2)
    expect(items[0]?.attributes('data-entry-type')).toBe('status_change')
    expect(items[1]?.attributes('data-entry-type')).toBe('resolution')
  })

  it('formatea las fechas en es-ES y Europe/Madrid', () => {
    const wrapper = mount(TicketTimeline, {
      props: { canSeeInternal: false, entries: [entry({})] },
    })

    const time = wrapper.find('time')
    expect(time.attributes('datetime')).toBe('2026-11-02T10:16:00Z')
    // 10:16 UTC = 11:16 en Madrid (CET).
    expect(time.text()).toMatch(/11:16/)
  })

  it('describe el cambio de estado con autor y etiquetas', () => {
    const wrapper = mount(TicketTimeline, {
      props: { canSeeInternal: false, entries: [entry({})] },
    })

    expect(wrapper.text()).toContain(
      'Técnica Asignada cambió el estado de Abierto a En progreso.',
    )
  })

  it('muestra la resolución como tarjeta destacada con texto plano', () => {
    const wrapper = mount(TicketTimeline, {
      props: {
        canSeeInternal: false,
        entries: [
          entry({
            id: 'r1',
            type: 'resolution',
            from_status: null,
            to_status: 'resuelto',
            body: '<b>No interpretar HTML</b>',
          }),
        ],
      },
    })

    expect(wrapper.text()).toContain('Resolución')
    expect(wrapper.text()).toContain('<b>No interpretar HTML</b>')
    expect(wrapper.find('b').exists()).toBe(false)
  })

  it('identifica como históricas las resoluciones anteriores a una reapertura', () => {
    const wrapper = mount(TicketTimeline, {
      props: {
        canSeeInternal: false,
        entries: [
          entry({
            id: 'r1',
            type: 'resolution',
            from_status: null,
            to_status: 'resuelto',
            body: 'Primera solución.',
            created_at: '2026-11-02T10:05:00Z',
          }),
          entry({
            id: 'reopen',
            from_status: 'resuelto',
            to_status: 'en_progreso',
            created_at: '2026-11-03T09:00:00Z',
          }),
          entry({
            id: 'r2',
            type: 'resolution',
            from_status: null,
            to_status: 'resuelto',
            body: 'Segunda solución.',
            created_at: '2026-11-03T10:00:00Z',
          }),
        ],
      },
    })

    const items = wrapper.findAll('[data-entry-type]')
    expect(items.map((item) => item.attributes('data-entry-type'))).toEqual([
      'resolution',
      'status_change',
      'resolution',
    ])

    const historical = wrapper.findAll('[data-historical-resolution="true"]')
    expect(historical).toHaveLength(1)
    expect(items[0]?.find('[data-historical-resolution="true"]').exists()).toBe(true)
    expect(items[2]?.find('[data-historical-resolution="true"]').exists()).toBe(false)
    expect(wrapper.text()).toContain('Primera solución.')
    expect(wrapper.text()).toContain('Segunda solución.')
  })

  it('oculta los comentarios internos cuando canSeeInternal es false', () => {
    const wrapper = mount(TicketTimeline, {
      props: {
        canSeeInternal: false,
        entries: [
          entry({
            id: 'i1',
            type: 'internal_comment',
            from_status: null,
            to_status: null,
            body: 'Nota privada.',
            is_internal: true,
          }),
        ],
      },
    })

    expect(wrapper.text()).not.toContain('Nota privada.')
    expect(wrapper.find('[data-entry-type="internal_comment"]').exists()).toBe(false)
  })

  it('muestra la etiqueta Interno cuando canSeeInternal es true', () => {
    const wrapper = mount(TicketTimeline, {
      props: {
        canSeeInternal: true,
        entries: [
          entry({
            id: 'i1',
            type: 'internal_comment',
            from_status: null,
            to_status: null,
            body: 'Nota privada.',
            is_internal: true,
          }),
        ],
      },
    })

    expect(wrapper.text()).toContain('Interno')
    expect(wrapper.text()).toContain('Nota privada.')
  })

  it('muestra el estado vacío y el de carga', () => {
    const empty = mount(TicketTimeline, {
      props: { canSeeInternal: false, entries: [] },
    })
    expect(empty.find('[role="status"]').text()).toContain(
      'Todavía no hay actividad en este ticket.',
    )

    const loading = mount(TicketTimeline, {
      props: { canSeeInternal: false, entries: [], loading: true },
    })
    expect(loading.find('[role="status"]').text()).toContain(
      'Cargando la línea temporal…',
    )
  })

  it('muestra la reasignación con responsables, motivo en texto plano y orden cronológico', () => {
    const wrapper = mount(TicketTimeline, {
      props: {
        canSeeInternal: false,
        entries: [
          entry({
            id: 'ac1',
            type: 'assignee_change',
            from_status: null,
            to_status: null,
            change_kind: 'reassignment',
            previous_assignee: {
              id: 'u1',
              name: 'Técnica Anterior',
              role: 'tecnico',
              team: 'Soporte',
              escalation_level: 'nivel_1',
              escalation_level_label: 'Nivel 1',
            },
            new_assignee: {
              id: 'u2',
              name: 'Técnico Nuevo',
              role: 'tecnico',
              team: 'Soporte',
              escalation_level: 'nivel_1',
              escalation_level_label: 'Nivel 1',
            },
            body: '<b>Motivo no interpretado</b>',
            created_at: '2026-11-04T10:00:00Z',
          }),
          entry({
            id: 'sc2',
            type: 'status_change',
            from_status: 'abierto',
            to_status: 'en_progreso',
            created_at: '2026-11-04T10:05:00Z',
          }),
        ],
      },
    })

    const items = wrapper.findAll('[data-entry-type]')
    expect(items.map((item) => item.attributes('data-entry-type'))).toEqual([
      'assignee_change',
      'status_change',
    ])
    expect(items[0]?.text()).toContain('Cambio de responsable')
    expect(items[0]?.text()).toContain('Reasignación')
    expect(items[0]?.text()).toContain(
      'Técnica Asignada reasignó el ticket de Técnica Anterior a Técnico Nuevo.',
    )
    expect(items[0]?.text()).toContain('<b>Motivo no interpretado</b>')
    expect(wrapper.find('b').exists()).toBe(false)
  })

  it('distingue el escalado con niveles y el subtipo correcto', () => {
    const wrapper = mount(TicketTimeline, {
      props: {
        canSeeInternal: false,
        entries: [
          entry({
            id: 'ac2',
            type: 'assignee_change',
            from_status: null,
            to_status: null,
            change_kind: 'escalation',
            previous_assignee: {
              id: 'u1',
              name: 'Técnica Nivel 1',
              role: 'tecnico',
              team: 'Soporte',
              escalation_level: 'nivel_1',
              escalation_level_label: 'Nivel 1',
            },
            new_assignee: {
              id: 'u4',
              name: 'Técnica Nivel 2',
              role: 'tecnico',
              team: 'Soporte',
              escalation_level: 'nivel_2',
              escalation_level_label: 'Nivel 2',
            },
            from_escalation_level: 'nivel_1',
            from_escalation_level_label: 'Nivel 1',
            to_escalation_level: 'nivel_2',
            to_escalation_level_label: 'Nivel 2',
            body: 'Requiere especialista.',
          }),
        ],
      },
    })

    const item = wrapper.find('[data-entry-type="assignee_change"]')
    expect(item.text()).toContain('Escalado a Nivel 2')
    expect(item.text()).not.toContain('Reasignación')
    expect(item.text()).toContain(
      'Técnica Asignada escaló el ticket de Técnica Nivel 1 (Nivel 1) a Técnica Nivel 2 (Nivel 2).',
    )
    expect(item.text()).toContain('Requiere especialista.')
  })

  it('no ofrece botones de edición ni borrado', () => {
    const wrapper = mount(TicketTimeline, {
      props: { canSeeInternal: true, entries: [entry({})] },
    })

    expect(wrapper.findAll('button')).toHaveLength(0)
  })
})
