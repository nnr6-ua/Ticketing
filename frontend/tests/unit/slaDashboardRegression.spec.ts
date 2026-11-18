import { flushPromises, mount, RouterLinkStub } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { describe, expect, it, vi } from 'vitest'

import * as slaApi from '@/api/slaDashboard'
import AppHeader from '@/components/layout/AppHeader.vue'
import router from '@/router'
import { useWorkQueueStore } from '@/stores/workQueue'

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
    getAccessToken: vi.fn(() => null),
    getStoredUserRole: vi.fn(() => 'tecnico'),
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

describe('No regresión de HU-04/HU-05/HU-06', () => {
  it('las rutas existentes siguen resolviendo sin rol de supervisor', () => {
    expect(router.resolve('/cola-de-trabajo').name).toBe('work-queue')
    expect(router.resolve('/tickets/abc').name).toBe('ticket-detail')
    expect(router.resolve('/login').name).toBe('login')

    for (const path of ['/cola-de-trabajo', '/tickets/abc', '/login']) {
      expect(router.resolve(path).meta.requiresRoles).toBeUndefined()
    }
  })

  it('la ruta del dashboard declara los roles de supervisor y administrador', () => {
    const route = router.resolve('/dashboard-sla')
    expect(route.name).toBe('sla-dashboard')
    expect(route.meta.requiresRoles).toEqual(['supervisor', 'admin'])
  })

  it('el wrapper del dashboard no expone métodos de escritura', () => {
    expect(Object.keys(slaApi).sort()).toEqual([
      'fetchSlaDashboard',
      'fetchSlaDashboardOptions',
    ])
  })

  it('la cola de trabajo conserva su estado y acciones', () => {
    setActivePinia(createPinia())
    const store = useWorkQueueStore()

    expect(typeof store.fetchQueue).toBe('function')
    expect(typeof store.start).toBe('function')
    expect(typeof store.stop).toBe('function')
    expect(typeof store.setStatusFilter).toBe('function')
    expect(store.items).toEqual([])
  })

  it('AppHeader mantiene «Mesa de ayuda» y la campana para un técnico', async () => {
    const pinia = createPinia()
    setActivePinia(pinia)

    const wrapper = mount(AppHeader, {
      global: {
        plugins: [pinia],
        stubs: { RouterLink: RouterLinkStub },
      },
    })
    await flushPromises()

    expect(wrapper.text()).toContain('Mesa de ayuda')
    expect(
      wrapper.find('button[aria-controls="notification-panel"]').exists(),
    ).toBe(true)
    expect(wrapper.find('[data-testid="sla-dashboard-link"]').exists()).toBe(
      false,
    )

    wrapper.unmount()
  })
})
