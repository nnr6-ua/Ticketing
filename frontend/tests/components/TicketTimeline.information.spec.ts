import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import TicketTimeline from '@/components/tickets/TicketTimeline.vue'
import type { TimelineEntry } from '@/types/ticketWorkflow'

function entry(overrides: Partial<TimelineEntry>): TimelineEntry {
  return {
    id: 'entry-1',
    type: 'information_request',
    from_status: null,
    to_status: null,
    body: null,
    is_internal: false,
    author: { id: 'u1', name: 'Laura Técnica', role: 'tecnico' },
    created_at: '2026-11-13T10:00:00Z',
    reply_to_id: null,
    ...overrides,
  }
}

describe('TicketTimeline (información)', () => {
  it('muestra petición y respuesta como entradas independientes', () => {
    const wrapper = mount(TicketTimeline, {
      props: {
        canSeeInternal: false,
        entries: [
          entry({
            id: 'request',
            body: '¿Qué navegador usas?',
          }),
          entry({
            id: 'response',
            type: 'user_response',
            body: 'Uso Chrome 131.',
            author: { id: 'u2', name: 'Usuario Creador', role: 'usuario' },
            reply_to_id: 'request',
            created_at: '2026-11-13T10:30:00Z',
          }),
        ],
      },
    })

    const items = wrapper.findAll('[data-entry-type]')
    expect(items).toHaveLength(2)
    expect(items[0]?.attributes('data-entry-type')).toBe('information_request')
    expect(items[1]?.attributes('data-entry-type')).toBe('user_response')
    expect(wrapper.text()).toContain('Petición de información')
    expect(wrapper.text()).toContain('Respuesta del usuario')
    expect(wrapper.text()).toContain('Laura Técnica')
    expect(wrapper.text()).toContain('Usuario Creador')
    expect(wrapper.text()).toContain('¿Qué navegador usas?')
    expect(wrapper.text()).toContain('Uso Chrome 131.')
  })

  it('no agrupa ni cita los mensajes y conserva pre-wrap', () => {
    const wrapper = mount(TicketTimeline, {
      props: {
        canSeeInternal: false,
        entries: [
          entry({ id: 'request', body: 'Línea 1\nLínea 2' }),
          entry({
            id: 'response',
            type: 'user_response',
            body: 'Respuesta\nmultilínea',
            reply_to_id: 'request',
          }),
        ],
      },
    })

    const bodies = wrapper.findAll('p.whitespace-pre-wrap')
    expect(bodies).toHaveLength(2)
    expect(bodies[0]?.text()).toContain('Línea 1')
    expect(bodies[1]?.text()).toContain('Respuesta')
    expect(wrapper.find('blockquote').exists()).toBe(false)
  })

  it('no interpreta HTML en peticiones ni respuestas', () => {
    const wrapper = mount(TicketTimeline, {
      props: {
        canSeeInternal: false,
        entries: [
          entry({ id: 'request', body: '<b>Petición</b>' }),
          entry({ id: 'response', type: 'user_response', body: '<i>Respuesta</i>' }),
        ],
      },
    })

    expect(wrapper.text()).toContain('<b>Petición</b>')
    expect(wrapper.text()).toContain('<i>Respuesta</i>')
    expect(wrapper.find('b').exists()).toBe(false)
    expect(wrapper.find('i').exists()).toBe(false)
  })
})
