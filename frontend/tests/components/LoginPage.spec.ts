import { flushPromises, mount } from '@vue/test-utils'
import { afterEach, describe, expect, it, vi } from 'vitest'

const harness = vi.hoisted(() => {
  const registeredGuards: Array<(to: { meta: Record<string, unknown>; fullPath: string }) => unknown> = []
  return {
    replace: vi.fn(),
    routeQuery: {} as Record<string, string | undefined>,
    setAccessToken: vi.fn(),
    session: { role: null as string | null },
    registeredGuards,
    createRouter: vi.fn((config: { routes: unknown[] }) => ({
      ...config,
      beforeEach: (guard: (to: { meta: Record<string, unknown>; fullPath: string }) => unknown) => {
        registeredGuards.push(guard)
      },
    })),
    createWebHistory: vi.fn(() => ({})),
  }
})
const { replace, routeQuery, setAccessToken } = harness

vi.mock('vue-router', () => ({
  useRoute: () => ({ query: harness.routeQuery }),
  useRouter: () => ({ replace: harness.replace }),
  createRouter: harness.createRouter,
  createWebHistory: harness.createWebHistory,
}))

vi.mock('@/auth/session', () => ({
  getStoredUserRole: () => harness.session.role,
  setStoredUserRole: vi.fn(),
}))

vi.mock('@/api/devAuth', () => ({ devLogin: vi.fn() }))
vi.mock('@/api/client', () => ({
  ApiClientError: class ApiClientError extends Error {},
  setAccessToken: harness.setAccessToken,
}))

import { devLogin } from '@/api/devAuth'
import { landingForRole } from '@/router/landing'
import '@/router'
import LoginPage from '@/views/LoginPage.vue'

const devLoginMock = vi.mocked(devLogin)

function loginAs(role: string) {
  devLoginMock.mockResolvedValue({
    access_token: 'token',
    token_type: 'bearer',
    expires_in: 3600,
    user: {
      id: 'user-1',
      email: 'usuario@example.com',
      name: 'Usuario',
      role,
    },
  })
}

async function submitAs(email: string) {
  const wrapper = mount(LoginPage)
  await wrapper.find('#dev-user').setValue(email)
  await wrapper.find('form').trigger('submit')
  await flushPromises()
  return wrapper
}

afterEach(() => {
  for (const key of Object.keys(routeQuery)) {
    delete routeQuery[key]
  }
  harness.session.role = null
})

describe('LoginPage · entrada según rol', () => {
  it('redirige a mis tickets cuando el rol es usuario', async () => {
    loginAs('usuario')

    await submitAs('usuario@example.com')

    expect(setAccessToken).toHaveBeenCalledWith('token')
    expect(replace).toHaveBeenCalledWith('/mis-tickets')
  })

  it('redirige a la cola de trabajo para técnicos y supervisores', async () => {
    loginAs('tecnico')

    await submitAs('tecnico.a@example.com')

    expect(replace).toHaveBeenCalledWith('/cola-de-trabajo')
  })

  it('ofrece acceso de administración y protege su ruta', async () => {
    loginAs('admin')
    const wrapper = mount(LoginPage)

    expect(wrapper.get('option[value="admin@example.com"]').text()).toContain(
      'Administración',
    )
    await wrapper.find('#dev-user').setValue('admin@example.com')
    await wrapper.find('form').trigger('submit')
    await flushPromises()

    expect(replace).toHaveBeenCalledWith('/admin/configuracion')
    expect(landingForRole('admin')).toBe('/admin/configuracion')

    const guard = harness.registeredGuards.at(-1)!
    const target = {
      meta: { requiresAdmin: true },
      fullPath: '/admin/configuracion',
    }
    harness.session.role = 'admin'
    expect(guard(target)).toBe(true)
    harness.session.role = 'usuario'
    expect(guard(target)).toEqual({
      name: 'login',
      query: { redirect: '/admin/configuracion' },
    })
  })

  it('respeta el redirect explícito por encima del rol', async () => {
    loginAs('usuario')
    routeQuery.redirect = '/tickets/abc'

    await submitAs('usuario@example.com')

    expect(replace).toHaveBeenCalledWith('/tickets/abc')
  })
})
