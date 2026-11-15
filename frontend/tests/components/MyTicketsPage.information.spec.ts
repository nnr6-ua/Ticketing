import { flushPromises, mount } from '@vue/test-utils'
import { createMemoryHistory, createRouter } from 'vue-router'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { apiGet } from '@/api/client'
import MyTicketsPage from '@/views/MyTicketsPage.vue'
import type { MyTicketsResponse } from '@/types/myTickets'

vi.mock('@/api/client', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/api/client')>()
  return { ...actual, apiGet: vi.fn() }
})

const apiGetMock = vi.mocked(apiGet)

function response(): MyTicketsResponse {
  return {
    items: [
      {
        id: 't1',
        ticket_number: 'TK-000501',
        title: 'No arranca el portátil',
        status: 'pendiente_usuario',
        status_label: 'Pendiente de usuario',
        category: { id: 'c1', name: 'Hardware' },
        priority: { id: 'p1', name: 'Alta', level: 2, color: '#dc2626' },
        created_at: '2026-11-10T10:00:00Z',
        updated_at: '2026-11-13T10:00:00Z',
        awaiting_user_response: true,
        response_requested_at: '2026-11-13T10:00:00Z',
        reminder_active: true,
        reminder_due_at: '2026-11-15T10:00:00Z',
      },
      {
        id: 't2',
        ticket_number: 'TK-000502',
        title: 'Error al generar informe',
        status: 'en_progreso',
        status_label: 'En progreso',
        category: null,
        priority: { id: 'p1', name: 'Alta', level: 2, color: '#dc2626' },
        created_at: '2026-11-10T10:00:00Z',
        updated_at: '2026-11-13T10:00:00Z',
        awaiting_user_response: false,
        response_requested_at: null,
        reminder_active: false,
        reminder_due_at: null,
      },
    ],
  }
}

function makeRouter() {
  return createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/mis-tickets', name: 'my-tickets', component: MyTicketsPage },
      { path: '/tickets/new', name: 'ticket-create', component: { template: '<div />' } },
      { path: '/tickets/:id', name: 'ticket-detail', component: { template: '<div />' } },
      { path: '/login', name: 'login', component: { template: '<div />' } },
    ],
  })
}

describe('MyTicketsPage (información)', () => {
  beforeEach(() => {
    apiGetMock.mockReset()
    apiGetMock.mockResolvedValue(response())
  })

  it('muestra aviso y recordatorio solo en el ticket pendiente', async () => {
    const router = makeRouter()
    await router.push('/mis-tickets')
    await router.isReady()
    const wrapper = mount(MyTicketsPage, { global: { plugins: [router] } })
    await flushPromises()

    const items = wrapper.findAll('li')
    expect(items).toHaveLength(2)
    expect(items[0]?.text()).toContain('Esperando tu respuesta')
    expect(items[0]?.text()).toContain(
      'Pendiente desde hace más de 48 horas',
    )
    expect(items[1]?.text()).not.toContain('Esperando tu respuesta')
    expect(items[1]?.text()).not.toContain(
      'Pendiente desde hace más de 48 horas',
    )
  })
})
