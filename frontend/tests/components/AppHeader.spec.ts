import { flushPromises, mount, RouterLinkStub } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { getAccessToken } from '@/api/client'
import AppHeader from '@/components/layout/AppHeader.vue'
import { getNotifications } from '@/services/notifications'
import { useNotificationsStore } from '@/stores/notifications'
import type { NotificationListResponse } from '@/types/notifications'

vi.mock('vue-router', () => ({
  useRouter: () => ({ push: vi.fn() }),
}))

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
  return { ...actual, getAccessToken: vi.fn() }
})

const tokenMock = vi.mocked(getAccessToken)
const getMock = vi.mocked(getNotifications)
void actualClient

function emptyResponse(): NotificationListResponse {
  return {
    items: [],
    unread_count: 0,
    pagination: {
      page: 1,
      page_size: 20,
      total_items: 0,
      total_pages: 0,
      has_next: false,
      has_previous: false,
    },
  }
}

let pinia: ReturnType<typeof createPinia>

function mountHeader() {
  return mount(AppHeader, {
    global: {
      plugins: [pinia],
      stubs: { RouterLink: RouterLinkStub },
    },
  })
}

describe('AppHeader', () => {
  beforeEach(() => {
    pinia = createPinia()
    setActivePinia(pinia)
    tokenMock.mockReset()
    getMock.mockReset()
    getMock.mockResolvedValue(emptyResponse())
  })

  afterEach(() => {
    useNotificationsStore(pinia).reset()
  })

  it('monta la campana y arranca el sondeo solo con token', async () => {
    tokenMock.mockReturnValue('token')
    const store = useNotificationsStore(pinia)
    const startSpy = vi.spyOn(store, 'startPolling')

    const wrapper = mountHeader()
    await flushPromises()

    expect(wrapper.text()).toContain('Mesa de ayuda')
    expect(wrapper.find('button[aria-controls="notification-panel"]').exists()).toBe(
      true,
    )
    expect(startSpy).toHaveBeenCalledTimes(1)
    expect(getMock).toHaveBeenCalled()
    wrapper.unmount()
  })

  it('no arranca el sondeo sin token', async () => {
    tokenMock.mockReturnValue(null)
    const store = useNotificationsStore(pinia)
    const startSpy = vi.spyOn(store, 'startPolling')

    const wrapper = mountHeader()
    await flushPromises()

    expect(startSpy).not.toHaveBeenCalled()
    expect(getMock).not.toHaveBeenCalled()
    wrapper.unmount()
  })

  it('detiene el sondeo al desmontarse', async () => {
    tokenMock.mockReturnValue('token')
    const store = useNotificationsStore(pinia)
    const stopSpy = vi.spyOn(store, 'stopPolling')

    const wrapper = mountHeader()
    await flushPromises()
    wrapper.unmount()

    expect(stopSpy).toHaveBeenCalled()
  })
})
