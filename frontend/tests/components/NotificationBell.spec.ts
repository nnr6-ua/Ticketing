import { flushPromises, mount } from '@vue/test-utils'
import axe from 'axe-core'
import { createPinia, setActivePinia } from 'pinia'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { ApiClientError } from '@/api/client'
import NotificationBell from '@/components/notifications/NotificationBell.vue'
import {
  getNotifications,
  markNotificationRead,
} from '@/services/notifications'
import { useNotificationsStore } from '@/stores/notifications'
import type { Notification, NotificationListResponse } from '@/types/notifications'

const push = vi.fn()

vi.mock('vue-router', () => ({
  useRouter: () => ({ push }),
}))

vi.mock('@/services/notifications', () => ({
  getNotifications: vi.fn(),
  markNotificationRead: vi.fn(),
}))

const getMock = vi.mocked(getNotifications)
const markMock = vi.mocked(markNotificationRead)

function notification(overrides: Partial<Notification> = {}): Notification {
  return {
    id: 'n1',
    type: 'ticket_reassigned',
    ticket_id: 't1',
    ticket_number: 'TK-000501',
    ticket_title: 'No puedo acceder a la VPN',
    previous_assignee_name: 'Técnica Anterior',
    is_read: false,
    created_at: '2026-11-04T10:00:00Z',
    read_at: null,
    ...overrides,
  }
}

function listResponse(
  items: Notification[] = [notification()],
  unreadCount = 1,
): NotificationListResponse {
  return {
    items,
    unread_count: unreadCount,
    pagination: {
      page: 1,
      page_size: 20,
      total_items: items.length,
      total_pages: 1,
      has_next: false,
      has_previous: false,
    },
  }
}

let pinia: ReturnType<typeof createPinia>

function mountBell() {
  return mount(NotificationBell, {
    attachTo: document.body,
    global: { plugins: [pinia] },
  })
}

async function settle(): Promise<void> {
  await flushPromises()
  await flushPromises()
}

describe('NotificationBell', () => {
  beforeEach(() => {
    pinia = createPinia()
    setActivePinia(pinia)
    getMock.mockReset()
    markMock.mockReset()
    push.mockReset()
    getMock.mockResolvedValue(listResponse())
  })

  afterEach(() => {
    useNotificationsStore(pinia).reset()
  })

  it('muestra el contador y la etiqueta accesible', async () => {
    const wrapper = mountBell()
    await useNotificationsStore(pinia).refresh()
    await settle()

    const button = wrapper.find('button')
    expect(button.attributes('aria-label')).toBe('Notificaciones, 1 sin leer')
    expect(button.attributes('aria-expanded')).toBe('false')
    expect(wrapper.text()).toContain('1')
  })

  it('abre el desplegable, carga las notificaciones y las anuncia', async () => {
    const wrapper = mountBell()
    await wrapper.find('button').trigger('click')
    await settle()

    expect(getMock).toHaveBeenCalled()
    const panel = wrapper.find('#notification-panel')
    expect(panel.exists()).toBe(true)
    expect(panel.text()).toContain('Ticket reasignado')
    expect(panel.text()).toContain('TK-000501')
    expect(panel.text()).toContain('Anterior responsable: Técnica Anterior')
    expect(panel.text()).toContain('No leída')
    expect(wrapper.find('button').attributes('aria-expanded')).toBe('true')
  })

  it('marca como leída, navega al ticket y cierra el desplegable', async () => {
    markMock.mockResolvedValue({
      changed: true,
      message: null,
      notification: notification({ is_read: true, read_at: '2026-11-04T10:01:00Z' }),
    })
    const wrapper = mountBell()
    await wrapper.find('button').trigger('click')
    await settle()

    await wrapper.find('#notification-panel button').trigger('click')
    await settle()

    expect(markMock).toHaveBeenCalledWith('n1')
    expect(push).toHaveBeenCalledWith('/tickets/t1')
    expect(wrapper.find('#notification-panel').exists()).toBe(false)
    expect(useNotificationsStore(pinia).unreadCount).toBe(0)
  })

  it('cierra con Escape y devuelve el foco al botón', async () => {
    const wrapper = mountBell()
    const button = wrapper.find('button')
    await button.trigger('click')
    await settle()
    expect(wrapper.find('#notification-panel').exists()).toBe(true)

    document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' }))
    await settle()

    expect(wrapper.find('#notification-panel').exists()).toBe(false)
    expect(document.activeElement).toBe(button.element)
  })

  it('muestra el error con reintento sin bloquear la navegación', async () => {
    getMock.mockRejectedValueOnce(
      new ApiClientError('server', 'boom', 500, 'internal_error'),
    )
    const wrapper = mountBell()
    await wrapper.find('button').trigger('click')
    await settle()

    const alert = wrapper.find('#notification-panel [role="alert"]')
    expect(alert.text()).toContain('No se pudieron cargar las notificaciones')

    getMock.mockResolvedValueOnce(listResponse())
    await alert.find('button').trigger('click')
    await settle()

    expect(wrapper.find('#notification-panel').text()).toContain('Ticket reasignado')
  })

  it('no tiene violaciones críticas de accesibilidad', async () => {
    document.documentElement.lang = 'es'
    const wrapper = mountBell()
    await wrapper.find('button').trigger('click')
    await settle()

    const results = await axe.run(wrapper.element, {
      rules: { 'color-contrast': { enabled: false } },
    })
    expect(results.violations.filter((v) => v.impact === 'critical')).toEqual([])
  })
})
