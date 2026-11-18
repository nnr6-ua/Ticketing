import { flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { ApiClientError } from '@/api/client'
import {
  fetchSlaDashboard,
  fetchSlaDashboardOptions,
} from '@/api/slaDashboard'
import {
  DEFAULT_FILTERS,
  mapSlaDashboardError,
  useSlaDashboardStore,
} from '@/stores/slaDashboard'
import { makeMeta, makeOptions, makeResponse } from '../fixtures/slaDashboard'

const mocks = vi.hoisted(() => {
  const route: {
    name: string
    fullPath: string
    query: Record<string, unknown>
  } = {
    name: 'sla-dashboard',
    fullPath: '/dashboard-sla',
    query: {},
  }
  const replace = vi.fn(async (location: { query?: Record<string, unknown> }) => {
    if (location?.query) {
      route.query = { ...location.query }
    }
  })
  return { route, replace }
})

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

function setVisibility(state: DocumentVisibilityState): void {
  Object.defineProperty(document, 'visibilityState', {
    configurable: true,
    get: () => state,
  })
}

describe('useSlaDashboardStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    mocks.route.name = 'sla-dashboard'
    mocks.route.fullPath = '/dashboard-sla'
    mocks.route.query = {}
    mocks.replace.mockClear()
    dashboardMock.mockReset()
    optionsMock.mockReset()
    dashboardMock.mockResolvedValue(makeResponse())
    optionsMock.mockResolvedValue(makeOptions())
    setVisibility('visible')
  })

  afterEach(() => {
    vi.useRealTimers()
    setVisibility('visible')
  })

  it('load() puebla data, meta, options y lastFetchedAt', async () => {
    const store = useSlaDashboardStore()

    await store.load()

    expect(store.data?.summary.ticket_count).toBe(10)
    expect(store.meta?.timezone).toBe('Europe/Madrid')
    expect(store.meta?.thresholds).toEqual({ green_pct: 90, amber_pct: 70 })
    expect(store.options?.categories).toHaveLength(2)
    expect(store.lastFetchedAt).not.toBeNull()
    expect(store.loading).toBe(false)
    expect(store.error).toBeNull()
  })

  it('refresh() reutiliza los filtros vigentes', async () => {
    mocks.route.query = {
      desde: '2026-11-01',
      hasta: '2026-11-10',
      categorias: 'sin_categoria',
      prioridades: '1,2',
    }
    const store = useSlaDashboardStore()
    await store.load()

    await store.refresh()

    expect(dashboardMock.mock.calls.at(-1)?.[0]).toEqual({
      desde: '2026-11-01',
      hasta: '2026-11-10',
      categorias: ['sin_categoria'],
      prioridades: [1, 2],
    })
  })

  it('no cambia el estado cuando la respuesta se aborta', async () => {
    dashboardMock.mockRejectedValueOnce(
      new DOMException('aborted', 'AbortError'),
    )
    const store = useSlaDashboardStore()

    await store.load()

    expect(store.data).toBeNull()
    expect(store.error).toBeNull()
    expect(store.loading).toBe(false)
  })

  it('un error inicial deja error sin datos ni métricas a cero', async () => {
    dashboardMock.mockRejectedValueOnce(
      new ApiClientError('server', 'boom', 500),
    )
    const store = useSlaDashboardStore()

    await store.load()

    expect(store.error?.kind).toBe('server')
    expect(store.data).toBeNull()
    expect(store.meta).toBeNull()
  })

  it('mapError traduce los códigos y tipos de error a es-ES', () => {
    expect(
      mapSlaDashboardError(
        new ApiClientError('invalid', 'x', 422, 'invalid_date_range'),
      ).message,
    ).toBe('La fecha inicial no puede ser posterior a la fecha final.')
    expect(
      mapSlaDashboardError(new ApiClientError('forbidden', 'x', 403)).message,
    ).toBe('No tienes permiso para acceder a este dashboard.')
    expect(
      mapSlaDashboardError(new ApiClientError('unauthorized', 'x', 401)).message,
    ).toBe('Tu sesión ha caducado. Inicia sesión de nuevo.')
    expect(
      mapSlaDashboardError(new ApiClientError('network', 'x')).message,
    ).toBe('No se pudo cargar el dashboard. Inténtalo de nuevo.')
    expect(
      mapSlaDashboardError(new ApiClientError('server', 'x', 500)).message,
    ).toBe('No se pudo cargar el dashboard. Inténtalo de nuevo.')
  })

  it('lee los filtros válidos de la URL y descarta los inválidos', () => {
    mocks.route.query = {
      desde: '2026-11-01',
      hasta: 'no-es-fecha',
      categorias: 'sin_categoria,no-es-uuid',
      prioridades: '2,9,1',
    }
    const store = useSlaDashboardStore()

    store.readFromUrl()

    expect(store.filters.desde).toBe('2026-11-01')
    expect(store.filters.hasta).toBeNull()
    expect(store.filters.categorias).toEqual(['sin_categoria'])
    expect(store.filters.prioridades).toEqual([1, 2])
  })

  it('setFilters escribe la URL y consulta con los filtros', async () => {
    const store = useSlaDashboardStore()

    const applied = store.setFilters({
      desde: '2026-11-01',
      hasta: '2026-11-10',
      categorias: [],
      prioridades: [3],
    })
    await flushPromises()

    expect(applied).toBe(true)
    expect(store.filters).toEqual({
      desde: '2026-11-01',
      hasta: '2026-11-10',
      categorias: [],
      prioridades: [3],
    })
    expect(mocks.route.query.desde).toBe('2026-11-01')
    expect(mocks.route.query.hasta).toBe('2026-11-10')
    expect(mocks.route.query.prioridades).toBe('3')
    expect(dashboardMock.mock.calls.at(-1)?.[0]).toMatchObject({
      desde: '2026-11-01',
      hasta: '2026-11-10',
      prioridades: [3],
    })
  })

  it('setFilters con rango inválido no consulta y conserva los filtros previos', async () => {
    mocks.route.query = { desde: '2026-11-01', hasta: '2026-11-10' }
    const store = useSlaDashboardStore()
    await store.load()
    const callsBefore = dashboardMock.mock.calls.length

    const applied = store.setFilters({
      desde: '2026-11-20',
      hasta: '2026-11-01',
      categorias: [],
      prioridades: [],
    })
    await flushPromises()

    expect(applied).toBe(false)
    expect(dashboardMock.mock.calls).toHaveLength(callsBefore)
    expect(store.filters.desde).toBe('2026-11-01')
    expect(store.filters.hasta).toBe('2026-11-10')
  })

  it('resetFilters vuelve a la configuración por defecto', async () => {
    mocks.route.query = { desde: '2026-11-01', prioridades: '2' }
    const store = useSlaDashboardStore()
    await store.load()

    store.resetFilters()
    await flushPromises()

    expect(store.filters).toEqual({
      ...DEFAULT_FILTERS,
      categorias: [],
      prioridades: [],
    })
    expect(mocks.route.query.desde).toBeUndefined()
    expect(mocks.route.query.prioridades).toBeUndefined()
    expect(dashboardMock.mock.calls.at(-1)?.[0]).toMatchObject({
      desde: null,
      hasta: null,
    })
  })

  it('expandDateRange amplía el rango vigente y conserva el resto de filtros', async () => {
    mocks.route.query = {
      desde: '2026-11-01',
      hasta: '2026-11-10',
      categorias: 'sin_categoria',
      prioridades: '2',
    }
    const store = useSlaDashboardStore()
    await store.load()

    store.expandDateRange()
    await flushPromises()

    expect(store.filters.desde! < '2026-11-01').toBe(true)
    expect(store.filters.hasta! > '2026-11-10').toBe(true)
    expect(store.filters.categorias).toEqual(['sin_categoria'])
    expect(store.filters.prioridades).toEqual([2])
    expect(mocks.route.query.desde).toBe(store.filters.desde)
    expect(mocks.route.query.hasta).toBe(store.filters.hasta)
    expect(dashboardMock.mock.calls.at(-1)?.[0]).toMatchObject({
      desde: store.filters.desde,
      hasta: store.filters.hasta,
      categorias: ['sin_categoria'],
      prioridades: [2],
    })
  })

  it('un rango de fechas personalizado sin tickets se presenta como «filtros»', async () => {
    mocks.route.query = { desde: '2026-11-01', hasta: '2026-11-10' }
    dashboardMock.mockResolvedValue(
      makeResponse({
        meta: makeMeta({
          has_tickets: false,
          filters: {
            desde: '2026-11-01',
            hasta: '2026-11-10',
            categorias: [],
            prioridades: [],
          },
        }),
      }),
    )
    const store = useSlaDashboardStore()
    await store.load()

    expect(store.emptyVariant).toBe('filtros')
  })

  it('sin filtros activos y sin tickets el estado vacío es «periodo»', async () => {
    dashboardMock.mockResolvedValue(
      makeResponse({ meta: makeMeta({ has_tickets: false }) }),
    )
    const store = useSlaDashboardStore()
    await store.load()

    expect(store.emptyVariant).toBe('periodo')
  })

  it('toma los valores efectivos de meta.filters', async () => {
    const store = useSlaDashboardStore()
    await store.load()

    expect(store.effectiveFilters).toEqual(store.meta?.filters)
  })

  it('sondea cada 60 s sin solapar peticiones', async () => {
    vi.useFakeTimers()
    const store = useSlaDashboardStore()

    store.startPolling()
    expect(dashboardMock).not.toHaveBeenCalled()

    await vi.advanceTimersByTimeAsync(60_000)
    expect(dashboardMock).toHaveBeenCalledTimes(1)

    await vi.advanceTimersByTimeAsync(60_000)
    expect(dashboardMock).toHaveBeenCalledTimes(2)

    store.stopPolling()
    await vi.advanceTimersByTimeAsync(60_000)
    expect(dashboardMock).toHaveBeenCalledTimes(2)
  })

  it('pausa el sondeo con la pestaña oculta', async () => {
    vi.useFakeTimers()
    setVisibility('hidden')
    const store = useSlaDashboardStore()

    store.startPolling()
    await vi.advanceTimersByTimeAsync(60_000)

    expect(dashboardMock).not.toHaveBeenCalled()
    store.stopPolling()
  })

  it('refresca al recuperar foco y visibilidad', async () => {
    const store = useSlaDashboardStore()
    store.startPolling()

    window.dispatchEvent(new Event('focus'))
    await flushPromises()
    expect(dashboardMock).toHaveBeenCalledTimes(1)

    document.dispatchEvent(new Event('visibilitychange'))
    await flushPromises()
    expect(dashboardMock).toHaveBeenCalledTimes(2)

    store.stopPolling()
  })

  it('conserva los datos y marca stale si falla una actualización', async () => {
    const store = useSlaDashboardStore()
    await store.load()
    expect(store.data).not.toBeNull()

    dashboardMock.mockRejectedValueOnce(
      new ApiClientError('server', 'boom', 500),
    )
    await store.refresh()

    expect(store.stale).toBe(true)
    expect(store.data?.summary.ticket_count).toBe(10)
    expect(store.error?.kind).toBe('server')
  })

  it('un forbidden durante una actualización borra los agregados y conserva el error', async () => {
    const store = useSlaDashboardStore()
    await store.load()
    expect(store.data).not.toBeNull()

    dashboardMock.mockRejectedValueOnce(
      new ApiClientError(
        'forbidden',
        'No tienes permiso para acceder a este dashboard.',
        403,
      ),
    )
    await store.refresh()

    expect(store.error?.kind).toBe('forbidden')
    expect(store.error?.message).toBe(
      'No tienes permiso para acceder a este dashboard.',
    )
    expect(store.data).toBeNull()
    expect(store.meta).toBeNull()
    expect(store.stale).toBe(false)
    expect(store.isForbidden).toBe(true)
  })

  it('redirige a login con redirect ante un 401 durante el sondeo', async () => {
    mocks.route.fullPath = '/dashboard-sla?desde=2026-11-01'
    dashboardMock.mockRejectedValueOnce(
      new ApiClientError('unauthorized', 'caducado', 401),
    )
    const store = useSlaDashboardStore()

    await store.load()

    expect(mocks.replace).toHaveBeenCalledWith({
      name: 'login',
      query: { redirect: '/dashboard-sla?desde=2026-11-01' },
    })
    expect(store.error?.kind).toBe('unauthorized')
    expect(store.data).toBeNull()
  })

  it('start() carga y stop() aborta y detiene el sondeo', async () => {
    const store = useSlaDashboardStore()

    store.start()
    await flushPromises()
    expect(dashboardMock).toHaveBeenCalledTimes(1)

    store.stop()
    expect(store.loading).toBe(false)
  })
})
