import { computed, ref } from 'vue'
import { defineStore } from 'pinia'
import type { LocationQueryRaw } from 'vue-router'

import { ApiClientError, isAbortError } from '@/api/client'
import {
  fetchSlaDashboard,
  fetchSlaDashboardOptions,
} from '@/api/slaDashboard'
import router from '@/router'
import type {
  SlaDashboardData,
  SlaDashboardFilters,
  SlaDashboardMeta,
  SlaDashboardOptions,
} from '@/types/slaDashboard'

export const DEFAULT_FILTERS: SlaDashboardFilters = {
  desde: null,
  hasta: null,
  categorias: [],
  prioridades: [],
}

const POLL_INTERVAL_MS = 60_000
const DATE_RE = /^\d{4}-\d{2}-\d{2}$/
const UUID_RE =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i

function firstString(value: unknown): string | undefined {
  if (typeof value === 'string') {
    return value
  }
  if (Array.isArray(value) && typeof value[0] === 'string') {
    return value[0]
  }
  return undefined
}

function parseCsv(value: unknown): string[] {
  const raw = firstString(value)
  if (!raw) {
    return []
  }
  return raw
    .split(',')
    .map((part) => part.trim())
    .filter(Boolean)
}

function parseDate(value: unknown): string | null {
  const raw = firstString(value)
  if (!raw || !DATE_RE.test(raw)) {
    return null
  }
  return raw
}

function normalizeCategories(values: string[]): string[] {
  const normalized: string[] = []
  for (const value of values) {
    if (value === 'sin_categoria' || UUID_RE.test(value)) {
      if (!normalized.includes(value)) {
        normalized.push(value)
      }
    }
  }
  return normalized
}

function normalizePriorities(values: number[]): number[] {
  return [
    ...new Set(
      values.filter(
        (value) => Number.isInteger(value) && value >= 1 && value <= 4,
      ),
    ),
  ].sort((left, right) => left - right)
}

export function isValidDateRange(
  desde: string | null,
  hasta: string | null,
): boolean {
  return !desde || !hasta || desde <= hasta
}

function isoDate(value: Date): string {
  return value.toISOString().slice(0, 10)
}

function shiftDays(iso: string, days: number): string {
  const [year, month, day] = iso.split('-').map(Number)
  const date = new Date(Date.UTC(year, month - 1, day))
  date.setUTCDate(date.getUTCDate() + days)
  return isoDate(date)
}

function daysBetween(from: string, to: string): number {
  const [fromYear, fromMonth, fromDay] = from.split('-').map(Number)
  const [toYear, toMonth, toDay] = to.split('-').map(Number)
  return Math.round(
    (Date.UTC(toYear, toMonth - 1, toDay) -
      Date.UTC(fromYear, fromMonth - 1, fromDay)) /
      86_400_000,
  )
}

/** Traduce un error del cliente a un mensaje es-ES del dashboard. */
export function mapSlaDashboardError(caught: unknown): ApiClientError {
  if (caught instanceof ApiClientError) {
    if (caught.code === 'invalid_date_range') {
      return new ApiClientError(
        'invalid',
        'La fecha inicial no puede ser posterior a la fecha final.',
        caught.status,
        caught.code,
      )
    }
    if (caught.kind === 'forbidden') {
      return new ApiClientError(
        'forbidden',
        'No tienes permiso para acceder a este dashboard.',
        403,
        caught.code,
      )
    }
    if (caught.kind === 'unauthorized') {
      return new ApiClientError(
        'unauthorized',
        'Tu sesión ha caducado. Inicia sesión de nuevo.',
        401,
        caught.code,
      )
    }
    if (caught.kind === 'invalid') {
      return new ApiClientError(
        'invalid',
        caught.message || 'Revisa los filtros e inténtalo de nuevo.',
        caught.status,
        caught.code,
      )
    }
    return new ApiClientError(
      caught.kind,
      'No se pudo cargar el dashboard. Inténtalo de nuevo.',
      caught.status,
      caught.code,
    )
  }

  return new ApiClientError(
    'network',
    'No se pudo cargar el dashboard. Inténtalo de nuevo.',
  )
}

export const useSlaDashboardStore = defineStore('slaDashboard', () => {
  const data = ref<SlaDashboardData | null>(null)
  const meta = ref<SlaDashboardMeta | null>(null)
  const options = ref<SlaDashboardOptions | null>(null)
  const filters = ref<SlaDashboardFilters>({
    ...DEFAULT_FILTERS,
    categorias: [],
    prioridades: [],
  })
  const loading = ref(false)
  const updating = ref(false)
  const error = ref<ApiClientError | null>(null)
  const stale = ref(false)
  const lastFetchedAt = ref<number | null>(null)

  let controller: AbortController | null = null
  let optionsController: AbortController | null = null
  let requestSeq = 0
  let pollTimer: ReturnType<typeof setInterval> | null = null
  let listenersAttached = false

  const effectiveFilters = computed<SlaDashboardFilters>(
    () => meta.value?.filters ?? filters.value,
  )

  const hasData = computed(() => data.value !== null)

  const isForbidden = computed(() => error.value?.kind === 'forbidden')
  const isUnauthorized = computed(() => error.value?.kind === 'unauthorized')

  const hasDimensionFilters = computed(
    () =>
      filters.value.categorias.length > 0 ||
      filters.value.prioridades.length > 0,
  )

  const hasActiveFilters = computed(
    () =>
      hasDimensionFilters.value ||
      filters.value.desde !== null ||
      filters.value.hasta !== null,
  )

  const emptyVariant = computed<'periodo' | 'filtros' | null>(() => {
    if (!data.value || !meta.value || meta.value.has_tickets) {
      return null
    }
    // «periodo» solo corresponde a la configuración por defecto: cualquier
    // filtro activo, incluidas las fechas personalizadas, es «filtros».
    return hasActiveFilters.value ? 'filtros' : 'periodo'
  })

  const hasOnlyNoSla = computed(() => {
    if (!data.value || data.value.summary.ticket_count === 0) {
      return false
    }
    return data.value.summary.no_sla_count === data.value.summary.ticket_count
  })

  const hasNoOverdue = computed(
    () => (data.value?.ranking.overdue_total ?? 0) === 0,
  )

  function currentQuery(): Record<string, string> {
    const query: Record<string, string> = {}
    if (filters.value.desde) {
      query.desde = filters.value.desde
    }
    if (filters.value.hasta) {
      query.hasta = filters.value.hasta
    }
    if (filters.value.categorias.length) {
      query.categorias = filters.value.categorias.join(',')
    }
    if (filters.value.prioridades.length) {
      query.prioridades = filters.value.prioridades.join(',')
    }
    return query
  }

  function sameQuery(
    left: Record<string, unknown>,
    right: Record<string, unknown>,
  ): boolean {
    const keys = new Set([...Object.keys(left), ...Object.keys(right)])
    for (const key of keys) {
      if (String(left[key] ?? '') !== String(right[key] ?? '')) {
        return false
      }
    }
    return true
  }

  function readFromUrl(): void {
    const query = router.currentRoute.value.query
    filters.value = {
      desde: parseDate(query.desde),
      hasta: parseDate(query.hasta),
      categorias: normalizeCategories(parseCsv(query.categorias)),
      prioridades: normalizePriorities(
        parseCsv(query.prioridades).map((part) => Number.parseInt(part, 10)),
      ),
    }
  }

  function syncUrl(): void {
    const current = router.currentRoute.value
    const next: LocationQueryRaw = { ...current.query }
    delete next.desde
    delete next.hasta
    delete next.categorias
    delete next.prioridades
    Object.assign(next, currentQuery())

    if (!sameQuery(current.query, next as Record<string, unknown>)) {
      void router.replace({ name: 'sla-dashboard', query: next })
    }
  }

  async function fetchDashboard(
    options_: { silent?: boolean } = {},
  ): Promise<void> {
    const silent = options_.silent ?? false
    const sequence = ++requestSeq
    controller?.abort()
    controller = new AbortController()

    if (!silent && data.value === null) {
      loading.value = true
    } else {
      updating.value = true
    }
    error.value = null

    try {
      const response = await fetchSlaDashboard(
        { ...filters.value },
        controller.signal,
      )
      if (sequence !== requestSeq) {
        return
      }
      data.value = response.data
      meta.value = response.meta
      stale.value = false
      lastFetchedAt.value = Date.now()
    } catch (caught) {
      if (isAbortError(caught) || sequence !== requestSeq) {
        return
      }
      const mapped = mapSlaDashboardError(caught)
      error.value = mapped
      if (mapped.kind === 'unauthorized') {
        const redirect = router.currentRoute.value.fullPath
        void router.replace({ name: 'login', query: { redirect } })
        return
      }
      if (mapped.kind === 'forbidden') {
        // Un 403 niega el acceso incluso si había una instantánea previa:
        // se conserva el error y se retiran todos los agregados visibles.
        data.value = null
        meta.value = null
        stale.value = false
        lastFetchedAt.value = null
        return
      }
      if (data.value !== null) {
        stale.value = true
      }
    } finally {
      if (sequence === requestSeq) {
        loading.value = false
        updating.value = false
      }
    }
  }

  async function fetchOptions(): Promise<void> {
    optionsController?.abort()
    optionsController = new AbortController()
    try {
      options.value = await fetchSlaDashboardOptions(
        {
          desde: filters.value.desde,
          hasta: filters.value.hasta,
        },
        optionsController.signal,
      )
    } catch (caught) {
      // Las opciones son auxiliares: si fallan se conserva la última lista.
      if (isAbortError(caught)) {
        return
      }
    }
  }

  async function load(): Promise<void> {
    readFromUrl()
    stale.value = false
    await Promise.all([fetchDashboard(), fetchOptions()])
  }

  async function refresh(): Promise<void> {
    await Promise.all([fetchDashboard({ silent: true }), fetchOptions()])
  }

  function setFilters(next: SlaDashboardFilters): boolean {
    const normalized: SlaDashboardFilters = {
      desde: next.desde && DATE_RE.test(next.desde) ? next.desde : null,
      hasta: next.hasta && DATE_RE.test(next.hasta) ? next.hasta : null,
      categorias: normalizeCategories(next.categorias),
      prioridades: normalizePriorities(next.prioridades),
    }

    if (!isValidDateRange(normalized.desde, normalized.hasta)) {
      return false
    }

    filters.value = normalized
    syncUrl()
    void Promise.all([
      fetchDashboard({ silent: data.value !== null }),
      fetchOptions(),
    ])
    return true
  }

  function resetFilters(): void {
    filters.value = {
      ...DEFAULT_FILTERS,
      categorias: [],
      prioridades: [],
    }
    syncUrl()
    void Promise.all([fetchDashboard({ silent: data.value !== null }), fetchOptions()])
  }

  /** Amplía el periodo vigente en ambos extremos sin perder los demás filtros. */
  function expandDateRange(): void {
    const current =
      filters.value.desde && filters.value.hasta
        ? filters.value
        : effectiveFilters.value
    const hoy = isoDate(new Date())
    const hasta = current.hasta ?? hoy
    const desde = current.desde ?? shiftDays(hasta, -29)
    const span = Math.max(daysBetween(desde, hasta) + 1, 1)
    const growth = Math.max(Math.floor(span / 2), 1)

    filters.value = {
      desde: shiftDays(desde, -growth),
      hasta: shiftDays(hasta, growth),
      categorias: [...filters.value.categorias],
      prioridades: [...filters.value.prioridades],
    }
    syncUrl()
    void Promise.all([
      fetchDashboard({ silent: data.value !== null }),
      fetchOptions(),
    ])
  }

  function handleFocus(): void {
    if (document.visibilityState !== 'hidden') {
      void refresh()
    }
  }

  function handleVisibilityChange(): void {
    if (document.visibilityState === 'visible') {
      void refresh()
    }
  }

  function startPolling(): void {
    if (pollTimer !== null) {
      return
    }
    pollTimer = setInterval(() => {
      if (document.visibilityState === 'hidden') {
        return
      }
      if (loading.value || updating.value) {
        return
      }
      void refresh()
    }, POLL_INTERVAL_MS)

    if (!listenersAttached) {
      window.addEventListener('focus', handleFocus)
      document.addEventListener('visibilitychange', handleVisibilityChange)
      listenersAttached = true
    }
  }

  function stopPolling(): void {
    if (pollTimer !== null) {
      clearInterval(pollTimer)
      pollTimer = null
    }
    if (listenersAttached) {
      window.removeEventListener('focus', handleFocus)
      document.removeEventListener('visibilitychange', handleVisibilityChange)
      listenersAttached = false
    }
  }

  function start(): void {
    void load()
    startPolling()
  }

  function stop(): void {
    stopPolling()
    controller?.abort()
    controller = null
    optionsController?.abort()
    optionsController = null
  }

  return {
    // estado
    data,
    meta,
    options,
    filters,
    loading,
    updating,
    error,
    stale,
    lastFetchedAt,
    // getters
    effectiveFilters,
    hasData,
    isForbidden,
    isUnauthorized,
    hasDimensionFilters,
    hasActiveFilters,
    emptyVariant,
    hasOnlyNoSla,
    hasNoOverdue,
    // acciones
    load,
    refresh,
    setFilters,
    resetFilters,
    expandDateRange,
    readFromUrl,
    syncUrl,
    startPolling,
    stopPolling,
    start,
    stop,
  }
})
