import { mount, type VueWrapper } from '@vue/test-utils'
import axe from 'axe-core'
import { afterEach, describe, expect, it, vi } from 'vitest'

import AdminConfigurationPage from '@/views/AdminConfigurationPage.vue'
import type {
  CategoryAdmin,
  ConfigHistoryResponse,
  PriorityAdmin,
  SlaMatrixResponse,
} from '@/types/adminConfiguration'

const { store } = vi.hoisted(() => ({
  store: {
    categories: [] as CategoryAdmin[],
    priorities: [] as PriorityAdmin[],
    matrix: null as SlaMatrixResponse | null,
    history: null as ConfigHistoryResponse | null,
    historyFilters: { page: 1, page_size: 25 },
    loading: false,
    saving: false,
    error: null,
    conflict: null,
    loadAll: vi.fn().mockResolvedValue(undefined),
    reloadAll: vi.fn().mockResolvedValue(undefined),
    loadHistory: vi.fn().mockResolvedValue(undefined),
    createCategory: vi.fn(),
    updateCategory: vi.fn(),
    deleteCategory: vi.fn(),
    createPriority: vi.fn(),
    updatePriority: vi.fn(),
    deletePriority: vi.fn(),
    saveMatrix: vi.fn(),
    clearConflict: vi.fn(),
  },
}))

vi.mock('@/stores/adminConfiguration', () => ({
  useAdminConfigurationStore: () => store,
}))

vi.mock('vue-router', () => ({
  useRoute: () => ({ query: {} }),
  useRouter: () => ({ replace: vi.fn() }),
}))

const mounted: VueWrapper[] = []

function attach(wrapper: VueWrapper): VueWrapper {
  mounted.push(wrapper)
  return wrapper
}

async function criticalViolations(wrapper: VueWrapper) {
  const results = await axe.run(wrapper.element, {
    rules: {
      // jsdom no calcula estilos reales; el contraste se revisa en T067.
      'color-contrast': { enabled: false },
    },
  })
  return results.violations.filter((violation) => violation.impact === 'critical')
}

afterEach(() => {
  while (mounted.length > 0) mounted.pop()?.unmount()
})

describe('Accesibilidad de la configuración administrativa', () => {
  it('la página y sus pestañas no tienen violaciones críticas', async () => {
    document.documentElement.lang = 'es'
    store.categories = [
      {
        id: 'c1',
        name: 'Red',
        description: 'Incidencias de conectividad',
        keywords: ['vpn'],
        is_active: true,
        is_default: true,
        is_system: false,
        sort_order: 1,
        revision: 1,
        ticket_count: 3,
        rule_count: 1,
        can_delete: false,
      },
    ]
    store.priorities = [
      {
        id: 'p1',
        name: 'Crítica',
        level: 1,
        color: '#dc2626',
        base_hours: '4.00',
        keywords: ['caída'],
        is_active: true,
        is_default: true,
        is_system: false,
        sort_order: 1,
        revision: 1,
        ticket_count: 2,
        rule_count: 1,
        can_delete: false,
      },
    ]
    store.matrix = {
      configuration_version: {
        id: 'v1',
        version: 1,
        created_at: '2026-11-17T09:00:00Z',
        created_by: null,
      },
      items: [
        {
          id: 'r1',
          category: { id: 'c1', name: 'Red' },
          priority: {
            id: 'p1',
            name: 'Crítica',
            level: 1,
            color: '#dc2626',
            base_hours: '4.00',
          },
          hours: '2.00',
          valid_from_version: 1,
          configuration_version_id: 'v1',
          created_at: '2026-11-17T09:00:00Z',
          created_by: { id: 'u1', name: 'Admin', email: 'admin@example.com' },
        },
      ],
      combinations: {
        categories: [{ id: 'c1', name: 'Red' }],
        priorities: [
          {
            id: 'p1',
            name: 'Crítica',
            level: 1,
            color: '#dc2626',
            base_hours: '4.00',
          },
        ],
      },
    }
    store.history = {
      items: [
        {
          id: 'a1',
          configuration_version: {
            id: 'v1',
            version: 1,
            created_at: '2026-11-17T09:00:00Z',
            created_by: null,
          },
          entity_type: 'category',
          entity_id: 'c1',
          action: 'create',
          actor: { id: 'u1', name: 'Admin', email: 'admin@example.com' },
          occurred_at: '2026-11-17T09:00:00Z',
          previous_values: null,
          new_values: { name: 'Red' },
          summary: 'Alta de categoría',
        },
      ],
      pagination: {
        page: 1,
        page_size: 25,
        total_items: 1,
        total_pages: 1,
        has_next: false,
        has_previous: false,
      },
    }

    const wrapper = attach(
      mount(AdminConfigurationPage, { attachTo: document.body }),
    )

    expect(await criticalViolations(wrapper)).toEqual([])

    const tabIds = ['priorities', 'matrix', 'history']
    for (const id of tabIds) {
      await wrapper.get(`#tab-${id}`).trigger('click')
      expect(await criticalViolations(wrapper)).toEqual([])
    }
  })
})
