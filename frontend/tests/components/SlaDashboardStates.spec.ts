import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import {
  fetchSlaDashboard,
  fetchSlaDashboardOptions,
} from '@/api/slaDashboard'
import DashboardEmptyState from '@/components/sla-dashboard/DashboardEmptyState.vue'
import DashboardErrorState from '@/components/sla-dashboard/DashboardErrorState.vue'
import SlaDashboardPage from '@/views/SlaDashboardPage.vue'
import { makeMeta, makeOptions, makeResponse } from '../fixtures/slaDashboard'

const mocks = vi.hoisted(() => ({
  route: { name: 'sla-dashboard', fullPath: '/dashboard-sla', query: {} },
  replace: vi.fn(async () => {}),
}))

vi.mock('@/router', () => ({
  default: {
    currentRoute: { value: mocks.route },
    replace: mocks.replace,
  },
}))

vi.mock('@/api/slaDashboard', () => ({
  fetchSlaDashboard: vi.fn(),
  fetchSlaDashboardOptions: vi.fn(),
}))

const dashboardMock = vi.mocked(fetchSlaDashboard)
const optionsMock = vi.mocked(fetchSlaDashboardOptions)

describe('DashboardEmptyState', () => {
  it('distingue periodo sin tickets y filtros sin resultados', () => {
    const periodo = mount(DashboardEmptyState, {
      props: { variant: 'periodo' },
    })
    const filtros = mount(DashboardEmptyState, {
      props: { variant: 'filtros' },
    })

    expect(periodo.attributes('data-variant')).toBe('periodo')
    expect(periodo.attributes('role')).toBe('status')
    expect(periodo.text()).toContain(
      'No hay tickets en el periodo seleccionado',
    )
    expect(filtros.attributes('data-variant')).toBe('filtros')
    expect(filtros.text()).toContain(
      'No hay resultados para los filtros seleccionados',
    )
    expect(periodo.text()).not.toBe(filtros.text())
  })

  it('distingue el periodo sin SLA y sin vencidos', () => {
    const sinSla = mount(DashboardEmptyState, {
      props: { variant: 'sin-sla' },
    })
    const sinVencidos = mount(DashboardEmptyState, {
      props: { variant: 'sin-vencidos' },
    })

    expect(sinSla.text()).toContain(
      'No hay tickets con SLA en el periodo seleccionado',
    )
    expect(sinVencidos.text()).toContain(
      'No hay tickets vencidos en el periodo seleccionado',
    )
    expect(sinSla.find('button').exists()).toBe(false)
    expect(sinVencidos.find('button').exists()).toBe(false)
  })

  it('ofrece acciones adecuadas y las emite', async () => {
    const onAction = vi.fn()
    const periodo = mount(DashboardEmptyState, {
      props: { variant: 'periodo', onAction },
    })
    const filtros = mount(DashboardEmptyState, {
      props: { variant: 'filtros' },
    })

    expect(periodo.find('button').text()).toBe('Ampliar fechas')
    await periodo.find('button').trigger('click')
    expect(periodo.emitted('action')).toHaveLength(1)
    expect(onAction).toHaveBeenCalledTimes(1)

    expect(filtros.find('button').text()).toBe('Limpiar filtros')
    await filtros.find('button').trigger('click')
    expect(filtros.emitted('action')).toHaveLength(1)
  })

  it('nunca presenta una matriz de ceros', () => {
    const wrapper = mount(DashboardEmptyState, {
      props: { variant: 'periodo' },
    })

    expect(wrapper.find('table').exists()).toBe(false)
    expect(wrapper.text()).not.toContain('0,0 %')
  })
})

describe('Acciones de los estados vacíos en la página', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    mocks.route.query = { desde: '2026-11-01', hasta: '2026-11-10' }
    mocks.replace.mockClear()
    dashboardMock.mockReset()
    optionsMock.mockReset()
    dashboardMock.mockResolvedValue(makeResponse())
    optionsMock.mockResolvedValue(makeOptions())
  })

  it('«Ampliar fechas» crece en ambos extremos del periodo', async () => {
    mocks.route.query = {}
    dashboardMock.mockResolvedValueOnce(
      makeResponse({
        meta: makeMeta({ has_tickets: false }),
      }),
    )
    const wrapper = mount(SlaDashboardPage, {
      global: { plugins: [createPinia()] },
    })
    await flushPromises()

    const empty = wrapper.find('[data-testid="sla-dashboard-empty"]')
    expect(empty.attributes('data-variant')).toBe('periodo')
    await empty.find('button').trigger('click')
    await flushPromises()

    const queried = dashboardMock.mock.calls.at(-1)?.[0]
    if (!queried?.desde || !queried.hasta) {
      throw new Error('La petición no incluyó el rango ampliado')
    }
    // El rango por defecto de meta es 2026-10-17 … 2026-11-15.
    expect(queried.desde < '2026-10-17').toBe(true)
    expect(queried.hasta > '2026-11-15').toBe(true)

    wrapper.unmount()
  })

  it('un rango de fechas personalizado sin tickets ofrece «Limpiar filtros»', async () => {
    dashboardMock.mockResolvedValueOnce(
      makeResponse({
        meta: makeMeta({
          filters: {
            desde: '2026-11-01',
            hasta: '2026-11-10',
            categorias: [],
            prioridades: [],
          },
          has_tickets: false,
        }),
      }),
    )
    const wrapper = mount(SlaDashboardPage, {
      global: { plugins: [createPinia()] },
    })
    await flushPromises()

    const empty = wrapper.find('[data-testid="sla-dashboard-empty"]')
    expect(empty.attributes('data-variant')).toBe('filtros')
    expect(empty.find('button').text()).toBe('Limpiar filtros')

    await empty.find('button').trigger('click')
    await flushPromises()

    expect(dashboardMock.mock.calls.at(-1)?.[0]).toMatchObject({
      desde: null,
      hasta: null,
    })

    wrapper.unmount()
  })

  it('«Limpiar filtros» restablece el rango por defecto', async () => {
    mocks.route.query = {
      desde: '2026-11-01',
      hasta: '2026-11-10',
      categorias: 'sin_categoria',
    }
    dashboardMock.mockResolvedValueOnce(
      makeResponse({
        meta: makeMeta({
          filters: {
            desde: '2026-11-01',
            hasta: '2026-11-10',
            categorias: ['sin_categoria'],
            prioridades: [],
          },
          has_tickets: false,
        }),
      }),
    )
    const wrapper = mount(SlaDashboardPage, {
      global: { plugins: [createPinia()] },
    })
    await flushPromises()

    const empty = wrapper.find('[data-testid="sla-dashboard-empty"]')
    expect(empty.attributes('data-variant')).toBe('filtros')
    await empty.find('button').trigger('click')
    await flushPromises()

    expect(dashboardMock.mock.calls.at(-1)?.[0]).toMatchObject({
      desde: null,
      hasta: null,
    })

    wrapper.unmount()
  })
})

describe('DashboardErrorState', () => {
  it('muestra el error de carga con reintento', async () => {
    const onRetry = vi.fn()
    const wrapper = mount(DashboardErrorState, { props: { onRetry } })

    expect(wrapper.attributes('data-variant')).toBe('full')
    expect(wrapper.attributes('role')).toBe('alert')
    expect(wrapper.text()).toContain('No se pudo cargar el dashboard')
    expect(wrapper.text()).toContain(
      'No se pudo cargar el dashboard. Inténtalo de nuevo.',
    )

    await wrapper.find('button').trigger('click')
    expect(wrapper.emitted('retry')).toHaveLength(1)
    expect(onRetry).toHaveBeenCalledTimes(1)
  })

  it('avisa de la desactualización conservando los datos previos', async () => {
    const wrapper = mount(DashboardErrorState, {
      props: { variant: 'warning' },
    })

    expect(wrapper.attributes('data-variant')).toBe('warning')
    expect(wrapper.attributes('role')).toBe('status')
    expect(wrapper.text()).toContain(
      'No se pudieron actualizar los datos. Se muestran los últimos datos disponibles.',
    )
    expect(wrapper.text()).not.toContain('No se pudo cargar el dashboard')
  })

  it('muestra el estado forbidden sin métricas ni reintento', () => {
    const wrapper = mount(DashboardErrorState, {
      props: { variant: 'forbidden', message: 'ignorado' },
    })

    expect(wrapper.attributes('data-variant')).toBe('forbidden')
    expect(wrapper.attributes('role')).toBe('alert')
    expect(wrapper.text()).toContain(
      'No tienes permiso para acceder a este dashboard.',
    )
    expect(wrapper.find('button').exists()).toBe(false)
    expect(wrapper.text()).not.toContain('%')
  })
})
