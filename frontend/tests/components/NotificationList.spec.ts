import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import NotificationList from '@/components/notifications/NotificationList.vue'
import type { Notification } from '@/types/notifications'

function notification(overrides: Partial<Notification> = {}): Notification {
  return {
    id: 'n1',
    type: 'ticket_reassigned',
    ticket_id: 't1',
    ticket_number: 'TK-000501',
    ticket_title: 'No puedo acceder a la VPN',
    previous_assignee_name: 'Técnica Anterior',
    is_read: false,
    created_at: '2026-11-04T09:30:00Z',
    read_at: null,
    ...overrides,
  }
}

describe('NotificationList', () => {
  it('distingue las no leídas con texto y muestra los datos del ticket', () => {
    const wrapper = mount(NotificationList, {
      props: {
        items: [
          notification(),
          notification({
            id: 'n2',
            type: 'ticket_escalated',
            is_read: true,
            read_at: '2026-11-04T10:00:00Z',
          }),
        ],
      },
    })

    const items = wrapper.findAll('li')
    expect(items).toHaveLength(2)
    expect(items[0]?.text()).toContain('Ticket reasignado')
    expect(items[0]?.text()).toContain('No leída')
    expect(items[1]?.text()).toContain('Ticket escalado')
    expect(items[1]?.text()).not.toContain('No leída')
    expect(wrapper.text()).toContain('Anterior responsable: Técnica Anterior')
    expect(wrapper.find('time').attributes('datetime')).toBe(
      '2026-11-04T09:30:00Z',
    )
    // 09:30 UTC = 10:30 en Madrid (CET).
    expect(wrapper.find('time').text()).toMatch(/10:30/)
  })

  it('emite select con la notificación pulsada', async () => {
    const item = notification()
    const wrapper = mount(NotificationList, { props: { items: [item] } })

    await wrapper.find('li button').trigger('click')

    expect(wrapper.emitted('select')).toEqual([[item]])
  })

  it('muestra el estado vacío y el de carga', () => {
    const empty = mount(NotificationList, { props: { items: [] } })
    expect(empty.text()).toContain('No tienes notificaciones.')

    const loading = mount(NotificationList, {
      props: { items: [], loading: true },
    })
    expect(loading.find('[role="status"]').text()).toContain(
      'Cargando notificaciones…',
    )
  })

  it('muestra el error con reintento', async () => {
    const wrapper = mount(NotificationList, {
      props: { items: [], error: 'No se pudieron cargar las notificaciones.' },
    })

    const alert = wrapper.find('[role="alert"]')
    expect(alert.text()).toContain('No se pudieron cargar las notificaciones.')
    await alert.find('button').trigger('click')
    expect(wrapper.emitted('retry')).toHaveLength(1)
  })

  it('renderiza el contenido como texto plano', () => {
    const wrapper = mount(NotificationList, {
      props: {
        items: [notification({ ticket_title: '<b>Título</b>' })],
      },
    })

    expect(wrapper.text()).toContain('<b>Título</b>')
    expect(wrapper.find('b').exists()).toBe(false)
  })
})
