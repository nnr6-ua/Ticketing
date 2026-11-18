import { flushPromises, mount } from '@vue/test-utils'
import { afterEach, describe, expect, it, vi } from 'vitest'

const { replace, routeQuery, setAccessToken } = vi.hoisted(() => ({
  replace: vi.fn(),
  routeQuery: {} as Record<string, string | undefined>,
  setAccessToken: vi.fn(),
}))

vi.mock('vue-router', () => ({
  useRoute: () => ({ query: routeQuery }),
  useRouter: () => ({ replace }),
}))

vi.mock('@/api/devAuth', () => ({ devLogin: vi.fn() }))
vi.mock('@/api/client', () => ({
  ApiClientError: class ApiClientError extends Error {},
  setAccessToken,
}))

import { devLogin } from '@/api/devAuth'
import { isAllowedRedirect, landingForRole } from '@/router/landing'
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

  it('respeta el redirect explícito por encima del rol', async () => {
    loginAs('usuario')
    routeQuery.redirect = '/tickets/abc'

    await submitAs('usuario@example.com')

    expect(replace).toHaveBeenCalledWith('/tickets/abc')
  })

  it('ignora un redirect a la cola cuando el rol es solicitante', async () => {
    loginAs('usuario')
    routeQuery.redirect = '/cola-de-trabajo'

    await submitAs('usuario@example.com')

    expect(replace).toHaveBeenCalledWith('/mis-tickets')
  })
})

describe('destino inicial por rol', () => {
  it('no envía a la cola cuando el rol es desconocido o falta', () => {
    expect(landingForRole(null)).toBe('/login')
    expect(landingForRole('otro')).toBe('/login')
    expect(landingForRole('usuario')).toBe('/mis-tickets')
    expect(landingForRole('tecnico')).toBe('/cola-de-trabajo')
  })

  it('solo admite redirects compatibles con el rol', () => {
    expect(isAllowedRedirect('/cola-de-trabajo', 'usuario')).toBe(false)
    expect(isAllowedRedirect('/cola-de-trabajo', 'tecnico')).toBe(true)
    expect(isAllowedRedirect('/admin/configuracion', 'usuario')).toBe(false)
    expect(isAllowedRedirect('/admin/configuracion', 'admin')).toBe(true)
    expect(isAllowedRedirect('/tickets/abc', 'usuario')).toBe(true)
    expect(isAllowedRedirect('//externo', 'usuario')).toBe(false)
  })
})
