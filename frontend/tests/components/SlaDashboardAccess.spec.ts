import { flushPromises, mount, RouterLinkStub } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import {
  ApiClientError,
  getAccessToken,
  getStoredUserRole,
} from '@/api/client'
import {
  fetchSlaDashboard,
  fetchSlaDashboardOptions,
} from '@/api/slaDashboard'
import AppHeader from '@/components/layout/AppHeader.vue'
import router from '@/router'
import AccessForbiddenPage from '@/views/AccessForbiddenPage.vue'
import SlaDashboardPage from '@/views/SlaDashboardPage.vue'
import { useSlaDashboardStore } from '@/stores/slaDashboard'
import { makeOptions, makeResponse } from '../fixtures/slaDashboard'

vi.mock('vue-router', async () => {
  const actual = await vi.importActual<typeof import('vue-router')>(
    'vue-router',
  )
  return { ...actual, useRouter: () => ({ push: vi.fn() }) }
})

vi.mock('@/api/client', async () => {
  const actual = await vi.importActual<typeof import('@/api/client')>(
    '@/api/client',
  )
  return {
    ...actual,
    getAccessToken: vi.fn(),
    getStoredUserRole: vi.fn(),
  }
})

vi.mock('@/services/notifications', () => ({
  getNotifications: vi.fn(async () => ({
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
  })),
  markNotificationRead: vi.fn(),
}))

vi.mock('@/api/slaDashboard', () => ({
  fetchSlaDashboard: vi.fn(),
  fetchSlaDashboardOptions: vi.fn(),
}))

const tokenMock = vi.mocked(getAccessToken)
const roleMock = vi.mocked(getStoredUserRole)
const dashboardMock = vi.mocked(fetchSlaDashboard)
const optionsMock = vi.mocked(fetchSlaDashboardOptions)

function mountHeader() {
  const pinia = createPinia()
  setActivePinia(pinia)
  return mount(AppHeader, {
    global: {
      plugins: [pinia],
      stubs: { RouterLink: RouterLinkStub },
    },
  })
}

describe('Acceso al dashboard de SLA', () => {
  beforeEach(async () => {
    tokenMock.mockReset()
    roleMock.mockReset()
    dashboardMock.mockReset()
    optionsMock.mockReset()
    optionsMock.mockResolvedValue(makeOptions())
    await router.replace('/login')
  })

  it('sin token el guard redirige a login conservando el destino', async () => {
    tokenMock.mockReturnValue(null)

    await router.push('/dashboard-sla')
    await router.isReady()

    expect(router.currentRoute.value.name).toBe('login')
    expect(router.currentRoute.value.query.redirect).toBe('/dashboard-sla')
  })

  it('con token de supervisor o administrador el guard permite entrar', async () => {
    for (const role of ['supervisor', 'admin']) {
      tokenMock.mockReturnValue('token')
      roleMock.mockReturnValue(role)

      await router.push('/dashboard-sla')
      await router.isReady()

      expect(router.currentRoute.value.name).toBe('sla-dashboard')
    }
  })

  it('con token de técnico o usuario el guard bloquea la vista y muestra forbidden sin métricas', async () => {
    for (const role of ['tecnico', 'usuario']) {
      tokenMock.mockReturnValue('token')
      roleMock.mockReturnValue(role)
      dashboardMock.mockReset()

      await router.push('/dashboard-sla')
      await router.isReady()

      expect(router.currentRoute.value.name).toBe('forbidden')
      expect(router.currentRoute.value.name).not.toBe('sla-dashboard')
      expect(dashboardMock).not.toHaveBeenCalled()

      const wrapper = mount(AccessForbiddenPage)
      const forbidden = wrapper.find('[data-testid="sla-dashboard-error"]')
      expect(forbidden.exists()).toBe(true)
      expect(forbidden.attributes('data-variant')).toBe('forbidden')
      expect(wrapper.text()).toContain(
        'No tienes permiso para acceder a este dashboard.',
      )
      expect(wrapper.find('[data-testid="sla-summary"]').exists()).toBe(false)
      wrapper.unmount()
    }
  })

  it('con token cuyo rol no se puede decodificar el guard también bloquea', async () => {
    tokenMock.mockReturnValue('token')
    roleMock.mockReturnValue(null)

    await router.push('/dashboard-sla')
    await router.isReady()

    expect(router.currentRoute.value.name).toBe('forbidden')
  })

  it('técnicos y usuarios no ven el enlace «Dashboard SLA»', () => {
    for (const role of ['tecnico', 'usuario']) {
      tokenMock.mockReturnValue('token')
      roleMock.mockReturnValue(role)
      const wrapper = mountHeader()

      expect(wrapper.text()).toContain('Mesa de ayuda')
      expect(wrapper.find('[data-testid="sla-dashboard-link"]').exists()).toBe(
        false,
      )
      expect(
        wrapper.find('button[aria-controls="notification-panel"]').exists(),
      ).toBe(true)
      wrapper.unmount()
    }
  })

  it('supervisores y administradores ven el enlace', () => {
    for (const role of ['supervisor', 'admin']) {
      tokenMock.mockReturnValue('token')
      roleMock.mockReturnValue(role)
      const wrapper = mountHeader()

      const link = wrapper.find('[data-testid="sla-dashboard-link"]')
      expect(link.exists()).toBe(true)
      expect(link.text()).toBe('Dashboard SLA')
      wrapper.unmount()
    }
  })

  it('el acceso directo con rol no autorizado muestra forbidden sin métricas', async () => {
    tokenMock.mockReturnValue('token')
    roleMock.mockReturnValue('tecnico')
    dashboardMock.mockRejectedValue(
      new ApiClientError(
        'forbidden',
        'No tienes permiso para acceder a este dashboard.',
        403,
      ),
    )
    const pinia = createPinia()
    setActivePinia(pinia)

    const wrapper = mount(SlaDashboardPage, {
      global: { plugins: [pinia] },
    })
    await flushPromises()

    const forbidden = wrapper.find('[data-testid="sla-dashboard-error"]')
    expect(forbidden.exists()).toBe(true)
    expect(forbidden.attributes('data-variant')).toBe('forbidden')
    expect(wrapper.text()).toContain(
      'No tienes permiso para acceder a este dashboard.',
    )
    expect(wrapper.find('[data-testid="sla-summary"]').exists()).toBe(false)

    wrapper.unmount()
  })

  it('un 403 durante el sondeo retira los agregados ya visibles', async () => {
    tokenMock.mockReturnValue('token')
    roleMock.mockReturnValue('supervisor')
    dashboardMock.mockResolvedValueOnce(makeResponse())
    const pinia = createPinia()
    setActivePinia(pinia)

    const wrapper = mount(SlaDashboardPage, { global: { plugins: [pinia] } })
    await flushPromises()
    expect(wrapper.find('[data-testid="sla-summary"]').exists()).toBe(true)

    dashboardMock.mockRejectedValueOnce(
      new ApiClientError('forbidden', 'sin permiso', 403),
    )
    await useSlaDashboardStore().refresh()
    await flushPromises()

    const forbidden = wrapper.find('[data-testid="sla-dashboard-error"]')
    expect(forbidden.exists()).toBe(true)
    expect(forbidden.attributes('data-variant')).toBe('forbidden')
    expect(wrapper.text()).toContain(
      'No tienes permiso para acceder a este dashboard.',
    )
    expect(wrapper.find('[data-testid="sla-dashboard-filters"]').exists()).toBe(false)
    expect(wrapper.find('[data-testid="sla-summary"]').exists()).toBe(false)
    expect(wrapper.find('[data-testid="compliance-matrix"]').exists()).toBe(false)
    expect(wrapper.find('[data-testid="technician-ranking"]').exists()).toBe(false)
    expect(wrapper.text()).not.toContain('Última actualización:')
    expect(wrapper.find('[data-testid="sla-dashboard-skeleton"]').exists()).toBe(
      false,
    )

    wrapper.unmount()
  })

  it('un 403 del backend prevalece sobre el rol cosmético del token', async () => {
    tokenMock.mockReturnValue('token')
    roleMock.mockReturnValue('supervisor')
    const { ApiClientError: ErrorClass } = await import('@/api/client')
    dashboardMock.mockRejectedValue(
      new ErrorClass('forbidden', 'sin permiso', 403),
    )
    const pinia = createPinia()
    setActivePinia(pinia)

    const wrapper = mount(SlaDashboardPage, {
      global: { plugins: [pinia] },
    })
    await flushPromises()

    expect(
      wrapper.find('[data-testid="sla-dashboard-error"]').attributes(
        'data-variant',
      ),
    ).toBe('forbidden')
    expect(wrapper.find('[data-testid="sla-summary"]').exists()).toBe(false)

    wrapper.unmount()
  })
})
