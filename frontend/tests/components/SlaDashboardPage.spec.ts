import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { ApiClientError } from '@/api/client'
import {
  fetchSlaDashboard,
  fetchSlaDashboardOptions,
} from '@/api/slaDashboard'
import SlaDashboardPage from '@/views/SlaDashboardPage.vue'
import {
  makeMatrixRow,
  makeMeta,
  makeMetrics,
  makeOptions,
  makeResponse,
  makeTotalsEntry,
} from '../fixtures/slaDashboard'

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

let pinia: ReturnType<typeof createPinia>

function mountPage() {
  return mount(SlaDashboardPage, {
    global: { plugins: [pinia] },
  })
}

describe('SlaDashboardPage', () => {
  beforeEach(() => {
    pinia = createPinia()
    setActivePinia(pinia)
    mocks.route.query = {}
    dashboardMock.mockReset()
    optionsMock.mockReset()
    dashboardMock.mockResolvedValue(makeResponse())
    optionsMock.mockResolvedValue(makeOptions())
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('dispara una única carga inicial al montar', async () => {
    const wrapper = mountPage()
    await flushPromises()

    expect(dashboardMock).toHaveBeenCalledTimes(1)
    expect(optionsMock).toHaveBeenCalledTimes(1)
    expect(wrapper.text()).toContain(
      'Dashboard de cumplimiento de SLA',
    )

    wrapper.unmount()
  })

  it('compone resumen, matriz, leyenda y ranking', async () => {
    const wrapper = mountPage()
    await flushPromises()

    expect(wrapper.find('[data-testid="sla-summary"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="compliance-matrix"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="semaphore-legend"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="technician-ranking"]').exists()).toBe(true)
    expect(wrapper.text()).toContain('90,0 %')
    expect(wrapper.text()).toContain('70,0 %')

    wrapper.unmount()
  })

  it('muestra la matriz y el aviso sin SLA cuando todos los tickets carecen de SLA', async () => {
    const sinSla = {
      ticket_count: 4,
      no_sla_count: 4,
      attended_with_sla: 0,
      on_time: 0,
      compliance_pct: null,
      avg_response_seconds: null,
      overdue_count: 0,
      semaphore: 'sin_datos' as const,
    }
    dashboardMock.mockResolvedValue(
      makeResponse({
        data: {
          summary: makeMetrics(sinSla),
          matrix: [
            makeMatrixRow({
              ...sinSla,
              category_id: null,
              category_name: 'Sin categoría',
              category_is_active: null,
            }),
          ],
          priority_totals: [
            makeTotalsEntry({ ...sinSla }),
          ],
          category_totals: [
            makeTotalsEntry({
              ...sinSla,
              scope: 'category',
              priority_level: null,
              priority_name: null,
              priority_is_active: null,
              category_id: null,
              category_name: 'Sin categoría',
              category_is_active: null,
            }),
          ],
          ranking: { technicians: [], unassigned: null, overdue_total: 0 },
        },
      }),
    )

    const wrapper = mountPage()
    await flushPromises()

    // La matriz conserva filas y celdas con «Sin datos» neutro…
    const matrix = wrapper.find('[data-testid="compliance-matrix"]')
    expect(matrix.exists()).toBe(true)
    expect(matrix.findAll('[data-testid="matrix-cell"]').length).toBeGreaterThan(0)
    expect(matrix.text()).toContain('Sin datos')
    expect(matrix.text()).toContain('Sin categoría')

    // …y el aviso informativo se suma como complemento, sin sustituirla.
    const notice = wrapper.find('[data-testid="sla-dashboard-empty"]')
    expect(notice.exists()).toBe(true)
    expect(notice.attributes('data-variant')).toBe('sin-sla')
    expect(wrapper.find('[data-testid="sla-summary"]').text()).toContain('Sin SLA')

    wrapper.unmount()
  })

  it('muestra el esqueleto mientras carga sin datos', async () => {
    dashboardMock.mockReturnValue(new Promise(() => {}))
    optionsMock.mockReturnValue(new Promise(() => {}))

    const wrapper = mountPage()
    await flushPromises()

    const skeleton = wrapper.find('[data-testid="sla-dashboard-skeleton"]')
    expect(skeleton.exists()).toBe(true)
    expect(skeleton.attributes('aria-busy')).toBe('true')
    expect(wrapper.text()).toContain('Cargando dashboard…')

    wrapper.unmount()
  })

  it('el reintento tras un error fatal muestra el skeleton mientras carga', async () => {
    dashboardMock.mockRejectedValueOnce(
      new ApiClientError('server', 'boom', 500),
    )
    const wrapper = mountPage()
    await flushPromises()

    expect(wrapper.find('[data-testid="sla-dashboard-error"]').exists()).toBe(
      true,
    )
    const retry = wrapper
      .findAll('button')
      .find((button) => button.text() === 'Reintentar')
    expect(retry).toBeDefined()

    dashboardMock.mockReturnValueOnce(new Promise(() => {}))
    await retry!.trigger('click')
    await flushPromises()

    expect(wrapper.find('[data-testid="sla-dashboard-skeleton"]').exists()).toBe(
      true,
    )
    expect(wrapper.find('[data-testid="sla-dashboard-empty"]').exists()).toBe(
      false,
    )
    expect(wrapper.find('[data-testid="sla-dashboard-error"]').exists()).toBe(
      false,
    )
    expect(wrapper.find('[data-testid="sla-summary"]').exists()).toBe(false)

    wrapper.unmount()
  })

  it('el reintento fatal restaura el error diferenciado si vuelve a fallar', async () => {
    dashboardMock
      .mockRejectedValueOnce(new ApiClientError('server', 'boom', 500))
      .mockRejectedValueOnce(new ApiClientError('server', 'boom again', 500))
    const wrapper = mountPage()
    await flushPromises()

    const retry = wrapper
      .findAll('button')
      .find((button) => button.text() === 'Reintentar')
    await retry!.trigger('click')
    await flushPromises()

    const error = wrapper.find('[data-testid="sla-dashboard-error"]')
    expect(error.exists()).toBe(true)
    expect(error.attributes('data-variant')).toBe('full')
    expect(wrapper.text()).toContain(
      'No se pudo cargar el dashboard. Inténtalo de nuevo.',
    )
    expect(wrapper.find('[data-testid="sla-dashboard-empty"]').exists()).toBe(
      false,
    )

    wrapper.unmount()
  })

  it('la acción «Ampliar fechas» ensancha el rango en lugar de restablecerlo', async () => {
    mocks.route.query = {}
    dashboardMock.mockResolvedValueOnce(
      makeResponse({
        meta: makeMeta({ has_tickets: false }),
      }),
    )
    const wrapper = mountPage()
    await flushPromises()

    const empty = wrapper.find('[data-testid="sla-dashboard-empty"]')
    expect(empty.attributes('data-variant')).toBe('periodo')
    await empty.find('button').trigger('click')
    await flushPromises()

    const lastCall = dashboardMock.mock.calls.at(-1)?.[0]
    if (!lastCall?.desde || !lastCall.hasta) {
      throw new Error('La petición no incluyó el rango ampliado')
    }
    // El rango por defecto de meta es 2026-10-17 … 2026-11-15.
    expect(lastCall.desde < '2026-10-17').toBe(true)
    expect(lastCall.hasta > '2026-11-15').toBe(true)
    expect(mocks.replace).toHaveBeenCalled()

    wrapper.unmount()
  })

  it('muestra la hora de última actualización en Europe/Madrid', async () => {
    const wrapper = mountPage()
    await flushPromises()

    expect(wrapper.find('[data-testid="sla-last-updated"]').text()).toBe(
      'Última actualización: 15/11/2026 09:34',
    )

    wrapper.unmount()
  })

  it('no expone formularios ni acciones de escritura', async () => {
    const wrapper = mountPage()
    await flushPromises()

    expect(wrapper.find('form').exists()).toBe(false)
    const buttonLabels = wrapper.findAll('button').map((node) => node.text())
    expect(buttonLabels).toEqual(
      expect.arrayContaining(['Actualizar', 'Aplicar', 'Restablecer']),
    )
    expect(buttonLabels.some((label) => /guardar|crear|eliminar/i.test(label))).toBe(false)

    wrapper.unmount()
  })
})
