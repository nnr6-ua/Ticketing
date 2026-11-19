import { mount, type VueWrapper } from '@vue/test-utils'
import axe from 'axe-core'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { ApiClientError } from '@/api/client'
import AdminTabs from '@/components/admin/AdminTabs.vue'
import AdminConfigurationPage from '@/views/AdminConfigurationPage.vue'
import type {
  CategoryAdmin,
  ConfigHistoryResponse,
  PriorityAdmin,
  SlaMatrixResponse,
} from '@/types/adminConfiguration'

const { store, routeQuery } = vi.hoisted(() => ({
  routeQuery: {} as Record<string, string>,
  store: {
    categories: [] as CategoryAdmin[],
    priorities: [] as PriorityAdmin[],
    matrix: null as SlaMatrixResponse | null,
    history: null as ConfigHistoryResponse | null,
    historyFilters: { page: 1, page_size: 25 },
    loading: false,
    saving: false,
    error: null as ApiClientError | null,
    conflict: null as string | null,
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
    retireRule: vi.fn().mockResolvedValue(undefined),
    clearConflict: vi.fn(),
  },
}))

vi.mock('@/stores/adminConfiguration', () => ({
  useAdminConfigurationStore: () => store,
}))

vi.mock('vue-router', () => ({
  useRoute: () => ({ query: routeQuery }),
  useRouter: () => ({ replace: vi.fn() }),
  onBeforeRouteLeave: vi.fn(),
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
  routeQuery.tab = ''
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
            category: { id: 'c1', name: 'Red', is_active: true },
            priority: {
              id: 'p1',
              name: 'Crítica',
              level: 1,
              color: '#dc2626',
              base_hours: '4.00',
              is_active: true,
            },
            hours: '2.00',
            valid_from_version: 1,
            configuration_version_id: 'v1',
            created_at: '2026-11-17T09:00:00Z',
            created_by: { id: 'u1', name: 'Admin', email: 'admin@example.com' },
          },
        ],
        combinations: {
          categories: [{ id: 'c1', name: 'Red', is_active: true }],
          priorities: [
            {
              id: 'p1',
              name: 'Crítica',
              level: 1,
              color: '#dc2626',
              base_hours: '4.00',
              is_active: true,
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
  }, 20000)

  it('conecta la retirada de reglas inactivas con el store', async () => {
    store.matrix = {
      configuration_version: {
        id: 'v2',
        version: 2,
        created_at: '2026-11-17T09:00:00Z',
        created_by: null,
      },
        items: [
          {
            id: 'r1',
            category: { id: 'c1', name: 'Red', is_active: true },
            priority: {
              id: 'p1',
              name: 'Alta',
              level: 2,
              color: '#ea580c',
              base_hours: '8.00',
              is_active: true,
            },
          hours: '2.00',
          valid_from_version: 2,
          configuration_version_id: 'v2',
          created_at: '2026-11-17T09:00:00Z',
          created_by: { id: 'u1', name: 'Admin', email: 'admin@example.com' },
        },
      ],
      combinations: { categories: [], priorities: [] },
    }
    store.retireRule.mockClear()

    const wrapper = attach(
      mount(AdminConfigurationPage, { attachTo: document.body }),
    )
    await wrapper.get('#tab-matrix').trigger('click')
    await wrapper
      .get('button[aria-label="Retirar regla de Red y Alta"]')
      .trigger('click')

    expect(store.retireRule).toHaveBeenCalledWith('r1')
  })
})

describe('Estados de AdminConfigurationPage', () => {
  beforeEach(() => {
    store.loading = false
    store.saving = false
    store.error = null
    store.conflict = null
    store.categories = []
    store.priorities = []
    store.matrix = null
    store.history = null
    store.loadAll.mockClear()
    store.reloadAll.mockClear()
    store.loadHistory.mockClear()
    routeQuery.tab = ''
  })

  it('muestra esqueletos durante la carga inicial', () => {
    store.loading = true
    const wrapper = attach(
      mount(AdminConfigurationPage, { attachTo: document.body }),
    )

    expect(wrapper.findAll('.grid.gap-3 > .animate-pulse')).toHaveLength(2)
  })

  it('muestra el error del servidor en role="alert"', () => {
    store.error = new ApiClientError(
      'server',
      'No se pudo cargar la configuración.',
      500,
    )
    const wrapper = attach(
      mount(AdminConfigurationPage, { attachTo: document.body }),
    )

    expect(wrapper.get('[role="alert"]').text()).toContain(
      'No se pudo cargar la configuración.',
    )
  })

  it('muestra el conflicto de versión con recarga', async () => {
    store.conflict = 'Otro administrador cambió la configuración.'
    const wrapper = attach(
      mount(AdminConfigurationPage, { attachTo: document.body }),
    )

    expect(wrapper.get('[role="alert"]').text()).toContain(
      'Otro administrador cambió la configuración.',
    )
    await wrapper.get('[role="alert"] button').trigger('click')
    expect(store.reloadAll).toHaveBeenCalledTimes(1)
  })

  it('muestra «Solo administración» cuando el rol no es válido', () => {
    store.error = new ApiClientError('forbidden', 'Acceso denegado.', 403)
    const wrapper = attach(
      mount(AdminConfigurationPage, { attachTo: document.body }),
    )

    expect(wrapper.text()).toContain('Solo administración')
    expect(wrapper.find('#tab-categories').exists()).toBe(false)
  })

  it('carga el histórico al enlazar directamente con ?tab=history', () => {
    routeQuery.tab = 'history'
    const wrapper = attach(
      mount(AdminConfigurationPage, { attachTo: document.body }),
    )

    expect(wrapper.get('#tab-history').attributes('aria-selected')).toBe('true')
    expect(store.loadHistory).toHaveBeenCalledWith(store.historyFilters)
  })
})

describe('AdminTabs navegación por teclado', () => {
  const tabs = [
    { id: 'categories', label: 'Categorías' },
    { id: 'priorities', label: 'Prioridades' },
    { id: 'matrix', label: 'Matriz SLA' },
    { id: 'history', label: 'Histórico' },
  ]

  afterEach(() => {
    document.body.innerHTML = ''
  })

  it('mueve selección y foco con flechas, Home y End', async () => {
    const wrapper = mount(AdminTabs, {
      attachTo: document.body,
      props: { tabs, modelValue: 'categories' },
    })

    await wrapper.get('#tab-categories').trigger('keydown', { key: 'ArrowRight' })
    expect(wrapper.emitted('update:modelValue')?.at(-1)).toEqual(['priorities'])
    expect(document.activeElement?.id).toBe('tab-priorities')

    await wrapper.setProps({ modelValue: 'priorities' })
    expect(wrapper.get('#tab-priorities').attributes('aria-selected')).toBe('true')

    await wrapper.get('#tab-priorities').trigger('keydown', { key: 'End' })
    expect(wrapper.emitted('update:modelValue')?.at(-1)).toEqual(['history'])
    expect(document.activeElement?.id).toBe('tab-history')

    await wrapper.setProps({ modelValue: 'history' })
    await wrapper.get('#tab-history').trigger('keydown', { key: 'Home' })
    expect(wrapper.emitted('update:modelValue')?.at(-1)).toEqual(['categories'])

    await wrapper.setProps({ modelValue: 'categories' })
    await wrapper.get('#tab-categories').trigger('keydown', { key: 'ArrowLeft' })
    expect(wrapper.emitted('update:modelValue')?.at(-1)).toEqual(['history'])
    expect(document.activeElement?.id).toBe('tab-history')
  })
})
