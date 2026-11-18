import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { ApiClientError } from '@/api/client'
import { useAdminConfigurationStore } from '@/stores/adminConfiguration'
import type {
  CategoryAdmin,
  ConfigHistoryResponse,
  PriorityAdmin,
  SlaMatrixResponse,
} from '@/types/adminConfiguration'

const { service, router } = vi.hoisted(() => ({
  service: {
    listCategories: vi.fn(),
    createCategory: vi.fn(),
    updateCategory: vi.fn(),
    deleteCategory: vi.fn(),
    listPriorities: vi.fn(),
    createPriority: vi.fn(),
    updatePriority: vi.fn(),
    deletePriority: vi.fn(),
    getSlaMatrix: vi.fn(),
    saveSlaBatch: vi.fn(),
    retireSlaRule: vi.fn(),
    getConfigHistory: vi.fn(),
  },
  router: {
    replace: vi.fn(),
    currentRoute: { value: { fullPath: '/admin/configuracion' } },
  },
}))

vi.mock('@/services/adminConfiguration', () => service)
vi.mock('@/router', () => ({ default: router }))
vi.mock('@/router/landing', () => ({
  landingForRole: vi.fn(() => '/cola-de-trabajo'),
}))
vi.mock('@/auth/session', () => ({
  getStoredUserRole: vi.fn(() => 'admin'),
}))

const category: CategoryAdmin = {
  id: 'c1',
  name: 'Red',
  description: null,
  keywords: [],
  is_active: true,
  is_default: false,
  is_system: false,
  sort_order: 1,
  revision: 1,
  ticket_count: 0,
  rule_count: 0,
  can_delete: true,
}

const priority: PriorityAdmin = {
  id: 'p1',
  name: 'Alta',
  level: 2,
  color: '#ea580c',
  base_hours: '8.00',
  keywords: [],
  is_active: true,
  is_default: false,
  is_system: false,
  sort_order: 1,
  revision: 1,
  ticket_count: 0,
  rule_count: 0,
  can_delete: true,
}

const matrix: SlaMatrixResponse = {
  configuration_version: {
    id: 'v2',
    version: 2,
    created_at: '2026-11-17T09:00:00Z',
    created_by: null,
  },
  items: [],
  combinations: {
    categories: [{ id: 'c1', name: 'Red' }],
    priorities: [
      {
        id: 'p1',
        name: 'Alta',
        level: 2,
        color: '#ea580c',
        base_hours: '8.00',
      },
    ],
  },
}

const history: ConfigHistoryResponse = {
  items: [],
  pagination: {
    page: 1,
    page_size: 25,
    total_items: 0,
    total_pages: 0,
    has_next: false,
    has_previous: false,
  },
}

beforeEach(() => {
  setActivePinia(createPinia())
  vi.clearAllMocks()
})

describe('adminConfiguration store', () => {
  it('carga catálogos y matriz', async () => {
    service.listCategories.mockResolvedValue([category])
    service.listPriorities.mockResolvedValue([priority])
    service.getSlaMatrix.mockResolvedValue(matrix)
    const store = useAdminConfigurationStore()

    await store.loadAll()

    expect(store.categories).toEqual([category])
    expect(store.priorities).toEqual([priority])
    expect(store.matrix).toEqual(matrix)
    expect(store.loading).toBe(false)
  })

  it('expone conflicto sin aplicar actualizaciones parciales', async () => {
    service.updateCategory.mockRejectedValue(
      new ApiClientError(
        'conflict',
        'La configuración ha cambiado. Recarga y vuelve a intentarlo.',
        409,
        'stale_configuration',
      ),
    )
    const store = useAdminConfigurationStore()
    store.categories = [category]

    await expect(
      store.updateCategory('c1', { expected_revision: 1, name: 'Otra' }),
    ).rejects.toBeInstanceOf(ApiClientError)

    expect(store.categories).toEqual([category])
    expect(store.conflict).toContain('La configuración ha cambiado')
    expect(store.error?.code).toBe('stale_configuration')
    expect(store.saving).toBe(false)
  })

  it('guarda la matriz y recarga la versión resultante', async () => {
    service.saveSlaBatch.mockResolvedValue({
      configuration_version: matrix.configuration_version,
      items: [],
    })
    service.getSlaMatrix.mockResolvedValue(matrix)
    const store = useAdminConfigurationStore()

    await store.saveMatrix([
      {
        operation: 'upsert',
        category_id: 'c1',
        priority_id: 'p1',
        hours: '2.00',
        expected_rule_id: null,
      },
    ])

    expect(service.saveSlaBatch).toHaveBeenCalled()
    expect(store.matrix).toEqual(matrix)
    expect(store.saving).toBe(false)
  })

  it('normaliza los filtros del histórico y conserva page_size', async () => {
    service.getConfigHistory.mockResolvedValue(history)
    const store = useAdminConfigurationStore()

    await store.loadHistory({ from: '2026-11-01', page: 2 })

    expect(store.historyFilters).toEqual({
      from: '2026-11-01',
      page: 2,
      page_size: 25,
    })
    expect(service.getConfigHistory).toHaveBeenCalledWith(store.historyFilters)
    expect(store.history).toEqual(history)
  })

  it('redirige al login ante una sesión no válida', async () => {
    service.listCategories.mockRejectedValue(
      new ApiClientError('unauthorized', 'Sesión caducada', 401),
    )
    const store = useAdminConfigurationStore()

    await expect(store.loadAll()).rejects.toBeInstanceOf(ApiClientError)

    expect(router.replace).toHaveBeenCalledWith({
      name: 'login',
      query: { redirect: '/admin/configuracion' },
    })
  })
})
