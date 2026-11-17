import { flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { ApiClientError, setAccessToken } from '@/api/client'
import {
  getNotifications,
  markNotificationRead,
} from '@/services/notifications'
import { useNotificationsStore } from '@/stores/notifications'
import type { Notification, NotificationListResponse } from '@/types/notifications'

vi.mock('@/services/notifications', () => ({
  getNotifications: vi.fn(),
  markNotificationRead: vi.fn(),
}))

const actualClient = await vi.importActual<typeof import('@/api/client')>(
  '@/api/client',
)
vi.mock('@/api/client', async () => {
  const actual = await vi.importActual<typeof import('@/api/client')>(
    '@/api/client',
  )
  return { ...actual, setAccessToken: vi.fn() }
})

const getMock = vi.mocked(getNotifications)
const markMock = vi.mocked(markNotificationRead)
const setTokenMock = vi.mocked(setAccessToken)
void actualClient

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

let visibility: DocumentVisibilityState

function setVisibility(value: DocumentVisibilityState): void {
  visibility = value
  Object.defineProperty(document, 'visibilityState', {
    configurable: true,
    get: () => visibility,
  })
}

describe('useNotificationsStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    getMock.mockReset()
    markMock.mockReset()
    setTokenMock.mockReset()
    getMock.mockResolvedValue(listResponse())
    setVisibility('visible')
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('refresh toma el contador del servidor y no lo calcula en cliente', async () => {
    getMock.mockResolvedValue(
      listResponse([notification(), notification({ id: 'n2' })], 7),
    )
    const store = useNotificationsStore()

    await store.refresh()

    expect(store.items).toHaveLength(2)
    expect(store.unreadCount).toBe(7)
    expect(store.loading).toBe(false)
    expect(store.error).toBeNull()
  })

  it('startPolling es idempotente y consulta cada 15 s', async () => {
    vi.useFakeTimers()
    const store = useNotificationsStore()

    store.startPolling()
    store.startPolling()
    await flushPromises()

    expect(getMock).toHaveBeenCalledTimes(1)

    await vi.advanceTimersByTimeAsync(15_000)
    await flushPromises()
    expect(getMock).toHaveBeenCalledTimes(2)

    store.reset()
  })

  it('pausa el sondeo con la pestaña oculta y refresca al recuperar foco', async () => {
    vi.useFakeTimers()
    const store = useNotificationsStore()
    store.startPolling()
    await flushPromises()
    expect(getMock).toHaveBeenCalledTimes(1)

    setVisibility('hidden')
    await vi.advanceTimersByTimeAsync(15_000)
    await flushPromises()
    expect(getMock).toHaveBeenCalledTimes(1)

    setVisibility('visible')
    window.dispatchEvent(new Event('focus'))
    await flushPromises()
    expect(getMock).toHaveBeenCalledTimes(2)

    store.reset()
  })

  it('descarta respuestas fuera de orden', async () => {
    let resolveFirst!: (value: NotificationListResponse) => void
    getMock.mockReturnValueOnce(
      new Promise<NotificationListResponse>((resolve) => {
        resolveFirst = resolve
      }),
    )
    const store = useNotificationsStore()

    const first = store.refresh()
    getMock.mockResolvedValueOnce(
      listResponse([notification({ id: 'new' })], 3),
    )
    const second = store.refresh()
    await second

    resolveFirst(listResponse([notification({ id: 'old' })], 1))
    await first
    await flushPromises()

    expect(store.items[0]?.id).toBe('new')
    expect(store.unreadCount).toBe(3)
  })

  it('marca como leída y descuenta el contador solo si no lo estaba', async () => {
    markMock.mockResolvedValue({
      changed: true,
      message: null,
      notification: notification({ is_read: true, read_at: '2026-11-04T10:01:00Z' }),
    })
    const store = useNotificationsStore()
    await store.refresh()

    await store.markRead('n1')

    expect(markMock).toHaveBeenCalledWith('n1')
    expect(store.items[0]?.is_read).toBe(true)
    expect(store.unreadCount).toBe(0)

    await store.markRead('n1')
    expect(store.unreadCount).toBe(0)
  })

  it('ante notification_not_found muestra el aviso y recarga la bandeja', async () => {
    markMock.mockRejectedValue(
      new ApiClientError('server', 'no existe', 404, 'notification_not_found'),
    )
    const store = useNotificationsStore()
    await store.refresh()

    await store.markRead('n1')

    expect(store.error).toBe('No se ha encontrado la notificación.')
    expect(getMock).toHaveBeenCalledTimes(2)
  })

  it('un 401 limpia la bandeja y detiene el sondeo', async () => {
    vi.useFakeTimers()
    const store = useNotificationsStore()
    store.startPolling()
    await flushPromises()
    expect(store.unreadCount).toBe(1)

    getMock.mockRejectedValue(
      new ApiClientError('unauthorized', 'sesión', 401, 'not_authenticated'),
    )
    await vi.advanceTimersByTimeAsync(15_000)
    await flushPromises()

    expect(store.items).toEqual([])
    expect(store.unreadCount).toBe(0)
    expect(setTokenMock).toHaveBeenCalledWith(null)

    const calls = getMock.mock.calls.length
    await vi.advanceTimersByTimeAsync(30_000)
    await flushPromises()
    expect(getMock.mock.calls.length).toBe(calls)
  })

  it('toggle abre y refresca si han pasado más de 15 s', async () => {
    vi.useFakeTimers()
    const store = useNotificationsStore()
    await store.refresh()
    expect(getMock).toHaveBeenCalledTimes(1)

    await vi.advanceTimersByTimeAsync(16_000)
    store.toggle()

    expect(store.open).toBe(true)
    await flushPromises()
    expect(getMock).toHaveBeenCalledTimes(2)

    store.close()
    expect(store.open).toBe(false)
  })
})
