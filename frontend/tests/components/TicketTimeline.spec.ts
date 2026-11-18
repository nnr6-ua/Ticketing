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

  it('muestra las resoluciones sin etiquetas no solicitadas tras una reapertura', () => {
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
        ],
      },
    })

    const items = wrapper.findAll('[data-entry-type]')
    expect(items.map((item) => item.attributes('data-entry-type'))).toEqual([
      'resolution',
      'status_change',
    ])
    expect(wrapper.findAll('[data-historical-resolution="true"]')).toHaveLength(0)
    expect(wrapper.text()).not.toContain('Histórica')
    expect(wrapper.text()).toContain('Primera solución.')
  })

  it('identifica los comentarios públicos como comentarios con autor y fecha', () => {
    const wrapper = mount(TicketTimeline, {
      props: {
        canSeeInternal: false,
        entries: [
          entry({
            id: 'public',
            type: 'internal_comment',
            from_status: null,
            to_status: null,
            body: 'Comentario público del técnico.',
            is_internal: false,
          }),
        ],
      },
    })

    expect(wrapper.text()).toContain('Comentario')
    expect(wrapper.text()).not.toContain('Interno')
    expect(wrapper.text()).toContain('Comentario público del técnico.')
    expect(wrapper.text()).toContain('Técnica Asignada')
    expect(wrapper.find('time').text()).toContain('11:16')
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

  it('muestra «Sistema» cuando una entrada no tiene autor registrado', () => {
    const wrapper = mount(TicketTimeline, {
      props: {
        canSeeInternal: false,
        entries: [entry({ author: undefined as never })],
      },
    })

    expect(wrapper.text()).toContain('Sistema')
  })

  it('no ofrece botones de edición ni borrado', () => {
    const wrapper = mount(TicketTimeline, {
      props: { canSeeInternal: true, entries: [entry({})] },
    })

    expect(wrapper.findAll('button')).toHaveLength(0)
  })

  it('navega entre páginas emitiendo page-change', async () => {
    const wrapper = mount(TicketTimeline, {
      props: {
        canSeeInternal: false,
        entries: [entry({})],
        pagination: {
          page: 1,
          page_size: 1,
          total_items: 3,
          total_pages: 3,
          has_next: true,
          has_previous: false,
        },
      },
    })

    const buttons = wrapper.findAll('button')
    expect(buttons).toHaveLength(2)
    expect(buttons[0]?.attributes('disabled')).toBeDefined()
    expect(buttons[1]?.attributes('disabled')).toBeUndefined()
    expect(wrapper.text()).toContain('Página 1 de 3')

    await buttons[1]?.trigger('click')
    expect(wrapper.emitted('page-change')).toEqual([[2]])
  })

  it('permite cambiar el tamaño de página emitiendo page-size-change', async () => {
    const wrapper = mount(TicketTimeline, {
      props: {
        canSeeInternal: false,
        entries: [entry({})],
        pagination: {
          page: 1,
          page_size: 50,
          total_items: 3,
          total_pages: 1,
          has_next: false,
          has_previous: false,
        },
      },
    })

    const select = wrapper.find('#timeline-page-size')
    expect(select.exists()).toBe(true)
    expect((select.element as HTMLSelectElement).value).toBe('50')

    await select.setValue('25')
    expect(wrapper.emitted('page-size-change')).toEqual([[25]])
  })

  it('permite volver a la página anterior y oculta los controles sin entradas', async () => {
    const wrapper = mount(TicketTimeline, {
      props: {
        canSeeInternal: false,
        entries: [entry({})],
        pagination: {
          page: 2,
          page_size: 1,
          total_items: 3,
          total_pages: 3,
          has_next: true,
          has_previous: true,
        },
      },
    })

    const buttons = wrapper.findAll('button')
    await buttons[0]?.trigger('click')
    expect(wrapper.emitted('page-change')).toEqual([[1]])

    const empty = mount(TicketTimeline, {
      props: {
        canSeeInternal: false,
        entries: [],
        pagination: {
          page: 1,
          page_size: 50,
          total_items: 0,
          total_pages: 0,
          has_next: false,
          has_previous: false,
        },
      },
    })
    expect(empty.findAll('button')).toHaveLength(0)
  })
})
