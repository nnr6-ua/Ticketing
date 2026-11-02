import { RouterLinkStub, mount, type VueWrapper } from '@vue/test-utils'
import axe from 'axe-core'
import { afterEach, describe, expect, it } from 'vitest'

import WorkQueueEmptyState from '@/components/work-queue/WorkQueueEmptyState.vue'
import WorkQueueErrorState from '@/components/work-queue/WorkQueueErrorState.vue'
import WorkQueueFilters from '@/components/work-queue/WorkQueueFilters.vue'
import WorkQueuePagination from '@/components/work-queue/WorkQueuePagination.vue'
import WorkQueueTable from '@/components/work-queue/WorkQueueTable.vue'
import { DEFAULT_STATUSES } from '@/stores/workQueue'
import type {
  PriorityFilterOption,
  StatusFilterOption,
  WorkQueueItem,
} from '@/types/workQueue'

const statusOptions: StatusFilterOption[] = [
  { value: 'abierto', label: 'Abierto', is_final: false },
  { value: 'en_progreso', label: 'En progreso', is_final: false },
  { value: 'pendiente_usuario', label: 'Pendiente de usuario', is_final: false },
  { value: 'resuelto', label: 'Resuelto', is_final: true },
  { value: 'cerrado', label: 'Cerrado', is_final: true },
]

const priorityOptions: PriorityFilterOption[] = [
  { id: 'p1', name: 'Crítica', level: 1, color: '#dc2626', is_active: true },
  { id: 'p2', name: 'Alta', level: 2, color: '#ea580c', is_active: true },
]

const item: WorkQueueItem = {
  id: 't1',
  number: 'TK-000001',
  title: 'No puedo acceder a la VPN desde casa',
  category: { id: 'c1', name: 'Red', is_active: true },
  priority: {
    id: 'p1',
    name: 'Crítica',
    level: 1,
    color: '#dc2626',
    is_active: true,
  },
  status: 'abierto',
  status_label: 'Abierto',
  is_final: false,
  sla: {
    deadline: '2026-10-29T12:00:00Z',
    started_at: '2026-10-29T08:00:00Z',
    total_seconds: 14400,
    remaining_seconds: 3600,
    warning_threshold_seconds: 3600,
    state: 'at_risk',
    outcome: null,
    finalized_at: null,
    breach_delay_seconds: null,
  },
  links: { self: '/api/v1/tickets/t1' },
}

const mounted: VueWrapper[] = []

function attach(wrapper: VueWrapper): VueWrapper {
  mounted.push(wrapper)
  return wrapper
}

async function criticalViolations(wrapper: VueWrapper) {
  const results = await axe.run(wrapper.element, {
    rules: {
      // jsdom no calcula estilos ni colores reales; el contraste se verificó
      // sobre los mapas estáticos de Tailwind.
      'color-contrast': { enabled: false },
    },
  })
  return results.violations.filter((violation) => violation.impact === 'critical')
}

afterEach(() => {
  while (mounted.length > 0) {
    mounted.pop()?.unmount()
  }
})

describe('Accesibilidad (axe-core)', () => {
  it('la tabla de la cola no tiene violaciones críticas', async () => {
    document.documentElement.lang = 'es'
    const wrapper = attach(
      mount(WorkQueueTable, {
        attachTo: document.body,
        props: { items: [item], nowMs: 1_000_000, dataNowMs: 1_000_000 },
        global: { stubs: { RouterLink: RouterLinkStub } },
      }),
    )

    expect(await criticalViolations(wrapper)).toEqual([])
  })

  it('los filtros no tienen violaciones críticas', async () => {
    document.documentElement.lang = 'es'
    const wrapper = attach(
      mount(WorkQueueFilters, {
        attachTo: document.body,
        props: {
          statusOptions,
          priorityOptions,
          selectedStatuses: [...DEFAULT_STATUSES],
          selectedPriorities: [],
          resultCount: 3,
          disabled: false,
        },
      }),
    )

    expect(await criticalViolations(wrapper)).toEqual([])
  })

  it('los estados vacíos no tienen violaciones críticas', async () => {
    document.documentElement.lang = 'es'

    for (const variant of ['no_assignments', 'only_final', 'no_results'] as const) {
      const wrapper = attach(
        mount(WorkQueueEmptyState, {
          attachTo: document.body,
          props: { variant },
        }),
      )
      expect(await criticalViolations(wrapper)).toEqual([])
      wrapper.unmount()
      mounted.pop()
    }
  })

  it('los estados de error no tienen violaciones críticas', async () => {
    document.documentElement.lang = 'es'

    for (const variant of ['full', 'warning', 'forbidden'] as const) {
      const wrapper = attach(
        mount(WorkQueueErrorState, {
          attachTo: document.body,
          props: { variant },
        }),
      )
      expect(await criticalViolations(wrapper)).toEqual([])
      wrapper.unmount()
      mounted.pop()
    }
  })

  it('la paginación no tiene violaciones críticas', async () => {
    document.documentElement.lang = 'es'
    const wrapper = attach(
      mount(WorkQueuePagination, {
        attachTo: document.body,
        props: {
          pagination: {
            page: 2,
            page_size: 25,
            total_items: 60,
            total_pages: 3,
            has_next: true,
            has_previous: true,
          },
          disabled: false,
        },
      }),
    )

    expect(await criticalViolations(wrapper)).toEqual([])
  })
})
