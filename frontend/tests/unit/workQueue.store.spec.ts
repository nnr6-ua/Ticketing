import { flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { ApiClientError } from '@/api/client'
import { fetchWorkQueue } from '@/api/workQueue'
import { DEFAULT_STATUSES, useWorkQueueStore } from '@/stores/workQueue'
import type {
  AvailableFilters,
  WorkQueueResponse,
} from '@/types/workQueue'

const mocks = vi.hoisted(() => {
  const route: { name: string; query: Record<string, unknown> } = {
    name: 'work-queue',
    query: {},
  }
  const replace = vi.fn(async (location: { query?: Record<string, unknown> }) => {
    if (location?.query) {
      route.query = { ...location.query }
    }
  })
  const afterEach = vi.fn(() => () => {})
  return { route, replace, afterEach }
})

vi.mock('@/router', () => ({
  default: {
    currentRoute: { value: mocks.route },
    replace: mocks.replace,
    afterEach: mocks.afterEach,
  },
}))

vi.mock('@/api/workQueue', () => ({
  fetchWorkQueue: vi.fn(),
}))

const fetchMock = vi.mocked(fetchWorkQueue)

const availableFilters: AvailableFilters = {
  statuses: [
    { value: 'abierto', label: 'Abierto', is_final: false },
    { value: 'en_progreso', label: 'En progreso', is_final: false },
    {
      value: 'pendiente_usuario',
      label: 'Pendiente de usuario',
      is_final: false,
    },
    { value: 'resuelto', label: 'Resuelto', is_final: true },
    { value: 'cerrado', label: 'Cerrado', is_final: true },
  ],
  priorities: [
    { id: 'p1', name: 'Crítica', level: 1, color: '#dc2626', is_active: true },
    { id: 'p2', name: 'Alta', level: 2, color: '#ea580c', is_active: true },
  ],
  default_statuses: [...DEFAULT_STATUSES],
}

function makeResponse(
  overrides: Partial<WorkQueueResponse> = {},
): WorkQueueResponse {
  return {
    items: [],
    pagination: {
      page: 1,
      page_size: 25,
      total_items: 0,
      total_pages: 0,
      has_next: false,
      has_previous: false,
    },
    counts: { active: 0, finalized: 0 },
    available_filters: availableFilters,
    applied_filters: {
      status: [...DEFAULT_STATUSES],
      priority: [],
      is_default: true,
    },
    meta: {
      server_time: '2026-10-29T10:00:00Z',
      timezone: 'Europe/Madrid',
      warning_policy: {
        short_sla_threshold_minutes: 60,
        short_sla_ratio: 0.5,
        long_sla_minimum_minutes: 60,
        long_sla_ratio: 0.25,
      },
    },
    ...overrides,
  }
}

function makeItem(id: string, number: string) {
  return {
    id,
    number,
    title: `Ticket ${number}`,
    category: null,
    priority: {
      id: 'p1',
      name: 'Crítica',
      level: 1,
      color: '#dc2626',
      is_active: true,
    },
    status: 'abierto' as const,
    status_label: 'Abierto',
    is_final: false,
    sla: {
      deadline: '2026-10-29T12:00:00Z',
      started_at: '2026-10-29T08:00:00Z',
      total_seconds: 14400,
      remaining_seconds: 3600,
      warning_threshold_seconds: 3600,
      state: 'at_risk' as const,
      outcome: null,
      finalized_at: null,
      breach_delay_seconds: null,
    },
    links: { self: `/api/v1/tickets/${id}` },
  }
}

describe('useWorkQueueStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    mocks.route.name = 'work-queue'
    mocks.route.query = {}
    mocks.replace.mockClear()
    mocks.afterEach.mockClear()
    fetchMock.mockReset()
    fetchMock.mockResolvedValue(makeResponse())
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('carga la cola y guarda los datos de la respuesta', async () => {
    const response = makeResponse({
      items: [makeItem('t1', 'TK-000001')],
      pagination: {
        page: 1,
        page_size: 25,
        total_items: 1,
        total_pages: 1,
        has_next: false,
        has_previous: false,
      },
      counts: { active: 1, finalized: 0 },
    })
    fetchMock.mockResolvedValue(response)

    const store = useWorkQueueStore()
    await store.fetchQueue()

    expect(store.items).toHaveLength(1)
    expect(store.pagination.total_items).toBe(1)
    expect(store.counts).toEqual({ active: 1, finalized: 0 })
    expect(store.availableFilters).toEqual(availableFilters)
    expect(store.lastUpdatedAt).not.toBeNull()
    expect(store.loading).toBe(false)
    expect(store.error).toBeNull()
  })

  it('sondea cada 60 s mientras la pestaña está visible', async () => {
    vi.useFakeTimers()
    const store = useWorkQueueStore()

    store.startPolling()
    expect(fetchMock).not.toHaveBeenCalled()

    await vi.advanceTimersByTimeAsync(60_000)
    expect(fetchMock).toHaveBeenCalledTimes(1)

    await vi.advanceTimersByTimeAsync(60_000)
    expect(fetchMock).toHaveBeenCalledTimes(2)

    store.stopPolling()
    await vi.advanceTimersByTimeAsync(60_000)
    expect(fetchMock).toHaveBeenCalledTimes(2)
  })

  it('recarga al recuperar el foco de la ventana', async () => {
    const store = useWorkQueueStore()
    store.startPolling()
    expect(fetchMock).not.toHaveBeenCalled()

    window.dispatchEvent(new Event('focus'))
    await flushPromises()

    expect(fetchMock).toHaveBeenCalledTimes(1)
    store.stopPolling()
  })

  it('cancela la petición anterior con AbortController', async () => {
    const signals: Array<AbortSignal | undefined> = []
    fetchMock.mockImplementation((_params, signal) => {
      signals.push(signal)
      return Promise.resolve(makeResponse())
    })

    const store = useWorkQueueStore()
    await store.fetchQueue()
    await store.fetchQueue()

    expect(signals).toHaveLength(2)
    expect(signals[0]?.aborted).toBe(true)
    expect(signals[1]?.aborted).toBe(false)
  })

  it('ignora respuestas fuera de orden y conserva la última petición', async () => {
    let resolveFirst!: (value: WorkQueueResponse) => void
    let resolveSecond!: (value: WorkQueueResponse) => void

    fetchMock
      .mockImplementationOnce(
        () => new Promise<WorkQueueResponse>((resolve) => {
          resolveFirst = resolve
        }),
      )
      .mockImplementationOnce(
        () => new Promise<WorkQueueResponse>((resolve) => {
          resolveSecond = resolve
        }),
      )

    const store = useWorkQueueStore()
    const first = store.fetchQueue()
    const second = store.fetchQueue()

    resolveSecond(
      makeResponse({
        pagination: {
          page: 1,
          page_size: 25,
          total_items: 2,
          total_pages: 1,
          has_next: false,
          has_previous: false,
        },
      }),
    )
    await second
    resolveFirst(
      makeResponse({
        pagination: {
          page: 1,
          page_size: 25,
          total_items: 99,
          total_pages: 4,
          has_next: true,
          has_previous: false,
        },
      }),
    )
    await first

    expect(store.pagination.total_items).toBe(2)
  })

  it('mapea 401 a unauthorized', async () => {
    fetchMock.mockRejectedValue(
      new ApiClientError('unauthorized', 'caducado', 401, 'token_expired'),
    )
    const store = useWorkQueueStore()

    await store.fetchQueue()

    expect(store.error?.kind).toBe('unauthorized')
    expect(store.error?.status).toBe(401)
    expect(store.error?.message).toContain('sesión')
  })

  it('se recupera al volver a la vista tras un 401 y una sesión renovada', async () => {
    fetchMock.mockRejectedValueOnce(
      new ApiClientError('unauthorized', 'caducado', 401, 'token_expired'),
    )
    const store = useWorkQueueStore()

    await store.fetchQueue()
    expect(store.error?.kind).toBe('unauthorized')
    expect(store.items).toHaveLength(0)

    // Nueva sesión válida: al montar de nuevo la vista se limpia el error y
    // se recarga la cola aunque el store ya se hubiera inicializado.
    fetchMock.mockResolvedValueOnce(
      makeResponse({
        items: [makeItem('t1', 'TK-000001')],
        pagination: {
          page: 1,
          page_size: 25,
          total_items: 1,
          total_pages: 1,
          has_next: false,
          has_previous: false,
        },
        counts: { active: 1, finalized: 0 },
      }),
    )

    store.start()
    await flushPromises()

    expect(store.error).toBeNull()
    expect(store.items).toHaveLength(1)
    expect(fetchMock).toHaveBeenCalledTimes(2)

    store.stop()
  })

  it('relee la URL y recarga al volver a entrar en la vista', async () => {
    const store = useWorkQueueStore()
    await store.initialize()
    expect(fetchMock).toHaveBeenCalledTimes(1)

    mocks.route.query = { estado: 'resuelto', prioridad: '2' }
    await store.initialize()

    expect(fetchMock).toHaveBeenCalledTimes(2)
    const params = fetchMock.mock.calls[1]?.[0]
    expect(params?.status).toEqual(['resuelto'])
    expect(params?.priority).toEqual([2])
  })

  it('mapea 403 a forbidden', async () => {
    fetchMock.mockRejectedValue(
      new ApiClientError('forbidden', 'sin permiso', 403),
    )
    const store = useWorkQueueStore()

    await store.fetchQueue()

    expect(store.error?.kind).toBe('forbidden')
    expect(store.error?.message).toContain('técnicos')
  })

  it('mapea 500 a server y conserva los datos previos al refrescar', async () => {
    const store = useWorkQueueStore()
    fetchMock.mockResolvedValueOnce(
      makeResponse({ items: [makeItem('t1', 'TK-000001')] }),
    )
    await store.fetchQueue()
    expect(store.items).toHaveLength(1)

    fetchMock.mockRejectedValueOnce(
      new ApiClientError('server', 'boom', 500),
    )
    await store.fetchQueue({ silent: true })

    expect(store.error?.kind).toBe('server')
    expect(store.items).toHaveLength(1)
    expect(store.degraded).toBe(true)
  })

  it('lee los filtros válidos de la URL', () => {
    mocks.route.query = {
      estado: 'resuelto',
      prioridad: '2,1',
      pagina: '3',
      page_size: '10',
    }
    const store = useWorkQueueStore()

    store.readFromUrl()

    expect(store.appliedFilters.status).toEqual(['resuelto'])
    expect(store.appliedFilters.priority).toEqual([1, 2])
    expect(store.pagination.page).toBe(3)
    expect(store.pageSize).toBe(10)
    expect(store.hasActiveFilters).toBe(true)
  })

  it('descarta los valores de URL inválidos y aplica los valores por defecto', () => {
    mocks.route.query = {
      estado: 'desconocido',
      prioridad: '9,abc',
      pagina: '-2',
      page_size: '500',
    }
    const store = useWorkQueueStore()

    store.readFromUrl()

    expect(store.appliedFilters.status).toEqual(DEFAULT_STATUSES)
    expect(store.appliedFilters.priority).toEqual([])
    expect(store.pagination.page).toBe(1)
    expect(store.pageSize).toBe(25)
    expect(store.isDefaultFilter).toBe(true)
  })

  it('aplica debounce, reinicia la página y envía el filtro de estado', async () => {
    vi.useFakeTimers()
    const store = useWorkQueueStore()
    store.pagination = {
      page: 3,
      page_size: 25,
      total_items: 60,
      total_pages: 3,
      has_next: false,
      has_previous: true,
    }

    store.setStatusFilter(['resuelto'])
    expect(fetchMock).not.toHaveBeenCalled()

    await vi.advanceTimersByTimeAsync(250)

    expect(fetchMock).toHaveBeenCalledTimes(1)
    const params = fetchMock.mock.calls[0]?.[0]
    expect(params?.status).toEqual(['resuelto'])
    expect(params?.page).toBe(1)
    expect(mocks.route.query.estado).toBe('resuelto')
  })

  it('limpia los filtros y vuelve a los estados activos por defecto', async () => {
    mocks.route.query = { estado: 'resuelto', prioridad: '2' }
    const store = useWorkQueueStore()
    store.readFromUrl()
    expect(store.hasActiveFilters).toBe(true)

    store.clearFilters()
    await flushPromises()

    expect(store.appliedFilters.status).toEqual(DEFAULT_STATUSES)
    expect(store.appliedFilters.priority).toEqual([])
    expect(store.pagination.page).toBe(1)
    expect(store.isDefaultFilter).toBe(true)
    expect(mocks.route.query.estado).toBeUndefined()
  })

  it('distingue cola vacía, solo finalizados y sin resultados', () => {
    const store = useWorkQueueStore()
    expect(store.isEmptyQueue).toBe(true)
    expect(store.hasOnlyFinalized).toBe(false)
    expect(store.isNoResults).toBe(false)

    store.counts = { active: 0, finalized: 2 }
    expect(store.isEmptyQueue).toBe(false)
    expect(store.hasOnlyFinalized).toBe(true)

    store.appliedFilters = {
      status: ['resuelto'],
      priority: [],
      is_default: false,
    }
    store.pagination = {
      page: 1,
      page_size: 25,
      total_items: 0,
      total_pages: 0,
      has_next: false,
      has_previous: false,
    }
    expect(store.hasActiveFilters).toBe(true)
    expect(store.isNoResults).toBe(true)
    expect(store.hasOnlyFinalized).toBe(false)
  })
})
