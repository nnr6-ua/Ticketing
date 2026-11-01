import { computed, ref } from 'vue'
import { defineStore } from 'pinia'
import type { LocationQueryRaw } from 'vue-router'

import { ApiClientError, isAbortError } from '@/api/client'
import { fetchWorkQueue } from '@/api/workQueue'
import router from '@/router'
import type {
  AppliedFilters,
  AvailableFilters,
  Counts,
  Pagination,
  PriorityFilterOption,
  StatusFilterOption,
  TicketStatus,
  WorkQueueError,
  WorkQueueItem,
} from '@/types/workQueue'

export const DEFAULT_STATUSES: TicketStatus[] = [
  'abierto',
  'en_progreso',
  'pendiente_usuario',
]

export const ALL_STATUSES: TicketStatus[] = [
  'abierto',
  'en_progreso',
  'pendiente_usuario',
  'resuelto',
  'cerrado',
]

const DEFAULT_PAGE_SIZE = 25
const POLL_INTERVAL_MS = 60_000
const FILTER_DEBOUNCE_MS = 250

const STATUS_LABELS: Record<TicketStatus, string> = {
  abierto: 'Abierto',
  en_progreso: 'En progreso',
  pendiente_usuario: 'Pendiente de usuario',
  resuelto: 'Resuelto',
  cerrado: 'Cerrado',
}

const FINAL_STATUSES: TicketStatus[] = ['resuelto', 'cerrado']

export function defaultStatusOptions(): StatusFilterOption[] {
  return ALL_STATUSES.map((value) => ({
    value,
    label: STATUS_LABELS[value],
    is_final: FINAL_STATUSES.includes(value),
  }))
}

function emptyPagination(pageSize = DEFAULT_PAGE_SIZE): Pagination {
  return {
    page: 1,
    page_size: pageSize,
    total_items: 0,
    total_pages: 0,
    has_next: false,
    has_previous: false,
  }
}

function uniqueStatuses(values: TicketStatus[]): TicketStatus[] {
  const valid = values.filter((value) => ALL_STATUSES.includes(value))
  return ALL_STATUSES.filter((status) => valid.includes(status))
}

function uniquePriorities(values: number[]): number[] {
  return [...new Set(values.filter((value) => value >= 1 && value <= 4))].sort(
    (left, right) => left - right,
  )
}

function sameStatuses(left: TicketStatus[], right: TicketStatus[]): boolean {
  if (left.length !== right.length) {
    return false
  }
  const sortedLeft = [...left].sort()
  const sortedRight = [...right].sort()
  return sortedLeft.every((value, index) => value === sortedRight[index])
}

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

function mapError(caught: unknown): WorkQueueError {
  if (caught instanceof ApiClientError) {
    if (caught.kind === 'unauthorized') {
      return {
        kind: 'unauthorized',
        status: caught.status,
        code: caught.code,
        message: 'La sesión no es válida o ha caducado.',
      }
    }
    if (caught.kind === 'forbidden') {
      return {
        kind: 'forbidden',
        status: caught.status,
        code: caught.code,
        message: 'Esta vista está disponible solo para técnicos.',
      }
    }
    if (caught.kind === 'invalid') {
      return {
        kind: 'invalid',
        status: caught.status,
        code: caught.code,
        message: caught.message,
      }
    }
    return {
      kind: caught.kind,
      status: caught.status,
      code: caught.code,
      message: 'No se pudo cargar tu cola de trabajo.',
    }
  }
  return {
    kind: 'network',
    message: 'No se pudo cargar tu cola de trabajo.',
  }
}

export const useWorkQueueStore = defineStore('workQueue', () => {
  const items = ref<WorkQueueItem[]>([])
  const pagination = ref<Pagination>(emptyPagination())
  const counts = ref<Counts>({ active: 0, finalized: 0 })
  const availableFilters = ref<AvailableFilters>({
    statuses: defaultStatusOptions(),
    priorities: [] as PriorityFilterOption[],
    default_statuses: [...DEFAULT_STATUSES],
  })
  const appliedFilters = ref<AppliedFilters>({
    status: [...DEFAULT_STATUSES],
    priority: [],
    is_default: true,
  })
  const loading = ref(false)
  const refreshing = ref(false)
  const error = ref<WorkQueueError | null>(null)
  const lastUpdatedAt = ref<number | null>(null)
  const serverTime = ref<string | null>(null)
  const pageSize = ref(DEFAULT_PAGE_SIZE)
  const initialized = ref(false)

  let controller: AbortController | null = null
  let requestSeq = 0
  let debounceTimer: ReturnType<typeof setTimeout> | null = null
  let pollTimer: ReturnType<typeof setInterval> | null = null
  let listenersAttached = false
  let removeAfterEach: (() => void) | null = null

  const isDefaultFilter = computed(
    () =>
      appliedFilters.value.priority.length === 0 &&
      sameStatuses(appliedFilters.value.status, DEFAULT_STATUSES),
  )

  const hasActiveFilters = computed(() => !isDefaultFilter.value)

  const activeFilterCount = computed(() => {
    const statusCount = sameStatuses(appliedFilters.value.status, DEFAULT_STATUSES)
      ? 0
      : appliedFilters.value.status.length
    return statusCount + appliedFilters.value.priority.length
  })

  const isEmptyQueue = computed(
    () =>
      counts.value.active === 0 &&
      counts.value.finalized === 0 &&
      !hasActiveFilters.value,
  )

  const hasOnlyFinalized = computed(
    () =>
      counts.value.active === 0 &&
      counts.value.finalized > 0 &&
      !hasActiveFilters.value,
  )

  const isNoResults = computed(
    () => hasActiveFilters.value && pagination.value.total_items === 0,
  )

  const degraded = computed(() => error.value !== null && items.value.length > 0)

  function currentQuery(): Record<string, string> {
    const query: Record<string, string> = {}
    if (!isDefaultFilter.value) {
      query.estado = appliedFilters.value.status.join(',')
    }
    if (appliedFilters.value.priority.length > 0) {
      query.prioridad = appliedFilters.value.priority.join(',')
    }
    if (pagination.value.page > 1) {
      query.pagina = String(pagination.value.page)
    }
    if (pageSize.value !== DEFAULT_PAGE_SIZE) {
      query.page_size = String(pageSize.value)
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

    const statusCandidates = parseCsv(query.estado) as TicketStatus[]
    const statuses = uniqueStatuses(statusCandidates)
    appliedFilters.value.status =
      statuses.length > 0 ? statuses : [...DEFAULT_STATUSES]

    const priorities = parseCsv(query.prioridad)
      .map((part) => Number.parseInt(part, 10))
      .filter((level) => Number.isInteger(level) && level >= 1 && level <= 4)
    appliedFilters.value.priority = uniquePriorities(priorities)

    const pageRaw = Number.parseInt(firstString(query.pagina) ?? '1', 10)
    pagination.value.page =
      Number.isFinite(pageRaw) && pageRaw >= 1 ? pageRaw : 1

    const sizeRaw = Number.parseInt(firstString(query.page_size) ?? '', 10)
    pageSize.value =
      Number.isFinite(sizeRaw) && sizeRaw >= 1 && sizeRaw <= 100
        ? sizeRaw
        : DEFAULT_PAGE_SIZE

    appliedFilters.value.is_default = isDefaultFilter.value
  }

  function syncUrl(): void {
    const current = router.currentRoute.value
    const next: LocationQueryRaw = { ...current.query }
    delete next.estado
    delete next.prioridad
    delete next.pagina
    delete next.page_size
    Object.assign(next, currentQuery())

    if (!sameQuery(current.query, next as Record<string, unknown>)) {
      void router.replace({ name: 'work-queue', query: next })
    }
  }

  async function fetchQueue(options: { silent?: boolean } = {}): Promise<void> {
    const silent = options.silent ?? false
    const sequence = ++requestSeq
    controller?.abort()
    controller = new AbortController()

    const hadItems = items.value.length > 0
    if (!silent && !hadItems) {
      loading.value = true
    } else {
      refreshing.value = true
    }
    error.value = null

    const requestedPage = pagination.value.page

    try {
      const response = await fetchWorkQueue(
        {
          status: isDefaultFilter.value ? undefined : appliedFilters.value.status,
          priority: appliedFilters.value.priority,
          page: requestedPage,
          page_size: pageSize.value,
        },
        controller.signal,
      )

      if (sequence !== requestSeq) {
        return
      }

      items.value = response.items
      pagination.value = response.pagination
      counts.value = response.counts
      availableFilters.value = response.available_filters
      appliedFilters.value = {
        status: [...response.applied_filters.status],
        priority: [...response.applied_filters.priority],
        is_default: response.applied_filters.is_default,
      }
      pageSize.value = response.pagination.page_size
      serverTime.value = response.meta.server_time
      lastUpdatedAt.value = Date.now()

      if (response.pagination.page !== requestedPage) {
        syncUrl()
      }
    } catch (caught) {
      if (isAbortError(caught) || sequence !== requestSeq) {
        return
      }
      // Si ya había datos se conservan; la vista muestra un aviso discreto.
      error.value = mapError(caught)
      if (error.value.kind === 'unauthorized') {
        // No dejar datos de una sesión anterior visibles tras un 401.
        items.value = []
        counts.value = { active: 0, finalized: 0 }
        lastUpdatedAt.value = null
      }
    } finally {
      if (sequence === requestSeq) {
        loading.value = false
        refreshing.value = false
      }
    }
  }

  function scheduleFetch(): void {
    if (debounceTimer !== null) {
      clearTimeout(debounceTimer)
    }
    debounceTimer = setTimeout(() => {
      debounceTimer = null
      void fetchQueue({ silent: true })
    }, FILTER_DEBOUNCE_MS)
  }

  function afterFilterChange(): void {
    appliedFilters.value.is_default = isDefaultFilter.value
    pagination.value.page = 1
    syncUrl()
    scheduleFetch()
  }

  function setStatusFilter(statuses: TicketStatus[]): void {
    const normalized = uniqueStatuses(statuses)
    appliedFilters.value.status =
      normalized.length > 0 ? normalized : [...DEFAULT_STATUSES]
    afterFilterChange()
  }

  function setPriorityFilter(levels: number[]): void {
    appliedFilters.value.priority = uniquePriorities(levels)
    afterFilterChange()
  }

  function clearFilters(): void {
    appliedFilters.value = {
      status: [...DEFAULT_STATUSES],
      priority: [],
      is_default: true,
    }
    pagination.value.page = 1
    syncUrl()
    void fetchQueue({ silent: true })
  }

  function setPage(page: number): void {
    const target = Math.max(1, Math.floor(page))
    if (target === pagination.value.page) {
      return
    }
    pagination.value.page = target
    syncUrl()
    void fetchQueue({ silent: true })
  }

  function handleFocus(): void {
    if (document.visibilityState !== 'hidden') {
      void fetchQueue({ silent: true })
    }
  }

  function handleVisibilityChange(): void {
    if (document.visibilityState === 'visible') {
      void fetchQueue({ silent: true })
    }
  }

  function startPolling(): void {
    if (pollTimer !== null) {
      return
    }
    pollTimer = setInterval(() => {
      if (document.visibilityState !== 'hidden') {
        void fetchQueue({ silent: true })
      }
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

  function handleRouteChange(): void {
    const before = currentQuery()
    readFromUrl()
    const after = currentQuery()
    if (!sameQuery(before, after)) {
      void fetchQueue({ silent: true })
    }
  }

  async function initialize(): Promise<void> {
    // Cada entrada a la vista relee la URL y recarga la cola. Así, tras
    // autenticarse de nuevo después de un 401, la vista se recupera sin
    // necesidad de recargar la página completa.
    if (error.value?.kind === 'unauthorized') {
      error.value = null
    }
    initialized.value = true
    readFromUrl()
    await fetchQueue()
  }

  function start(): void {
    void initialize()
    startPolling()
    if (removeAfterEach === null) {
      removeAfterEach = router.afterEach((to, from) => {
        if (to.name === 'work-queue' && from.name === 'work-queue') {
          handleRouteChange()
        }
      })
    }
  }

  function stop(): void {
    stopPolling()
    if (removeAfterEach !== null) {
      removeAfterEach()
      removeAfterEach = null
    }
    if (debounceTimer !== null) {
      clearTimeout(debounceTimer)
      debounceTimer = null
    }
    controller?.abort()
    controller = null
  }

  return {
    // estado
    items,
    pagination,
    counts,
    availableFilters,
    appliedFilters,
    loading,
    refreshing,
    error,
    lastUpdatedAt,
    serverTime,
    pageSize,
    initialized,
    // getters
    isDefaultFilter,
    hasActiveFilters,
    activeFilterCount,
    isEmptyQueue,
    hasOnlyFinalized,
    isNoResults,
    degraded,
    // acciones
    fetchQueue,
    setStatusFilter,
    setPriorityFilter,
    clearFilters,
    setPage,
    initialize,
    readFromUrl,
    syncUrl,
    startPolling,
    stopPolling,
    handleRouteChange,
    start,
    stop,
  }
})
