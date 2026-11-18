import { flushPromises, mount, type VueWrapper } from '@vue/test-utils'
import axe from 'axe-core'
import { createPinia, setActivePinia } from 'pinia'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import ComplianceMatrix from '@/components/sla-dashboard/ComplianceMatrix.vue'
import DashboardEmptyState from '@/components/sla-dashboard/DashboardEmptyState.vue'
import DashboardErrorState from '@/components/sla-dashboard/DashboardErrorState.vue'
import SemaphoreBadge from '@/components/sla-dashboard/SemaphoreBadge.vue'
import SemaphoreLegend from '@/components/sla-dashboard/SemaphoreLegend.vue'
import SlaDashboardFilters from '@/components/sla-dashboard/SlaDashboardFilters.vue'
import TechnicianRanking from '@/components/sla-dashboard/TechnicianRanking.vue'
import SlaDashboardPage from '@/views/SlaDashboardPage.vue'
import { SEMAPHORE_BADGE_CLASS } from '@/utils/slaStyles'
import { makeOptions, makeResponse } from '../fixtures/slaDashboard'

vi.mock('@/router', () => ({
  default: {
    currentRoute: {
      value: { name: 'sla-dashboard', fullPath: '/dashboard-sla', query: {} },
    },
    replace: vi.fn(async () => {}),
  },
}))

vi.mock('@/api/slaDashboard', () => ({
  fetchSlaDashboard: vi.fn(),
  fetchSlaDashboardOptions: vi.fn(),
}))

const mounted: VueWrapper[] = []

function attach(wrapper: VueWrapper): VueWrapper {
  mounted.push(wrapper)
  return wrapper
}

async function blockingViolations(wrapper: VueWrapper) {
  const results = await axe.run(wrapper.element, {
    rules: {
      // jsdom no calcula estilos ni colores reales; la equivalencia de
      // contraste se verifica de forma ejecutable más abajo sobre los mapas
      // estáticos de Tailwind (SEMAPHORE_BADGE_CLASS).
      'color-contrast': { enabled: false },
    },
  })
  return results.violations.filter((violation) =>
    ['serious', 'moderate', 'critical'].includes(violation.impact ?? ''),
  )
}

/** Tokens de color de Tailwind usados por el semáforo, en hexadecimal. */
const TAILWIND_HEX: Record<string, string> = {
  'emerald-50': '#ecfdf5',
  'emerald-800': '#065f46',
  'amber-100': '#fef3c7',
  'amber-900': '#78350f',
  'red-100': '#fee2e2',
  'red-800': '#991b1b',
  'slate-100': '#f1f5f9',
  'slate-700': '#334155',
}

function srgbChannel(value: number): number {
  const channel = value / 255
  return channel <= 0.03928
    ? channel / 12.92
    : ((channel + 0.055) / 1.055) ** 2.4
}

function relativeLuminance(hex: string): number {
  const normalized = hex.replace('#', '')
  const [red, green, blue] = [0, 2, 4].map((index) =>
    Number.parseInt(normalized.slice(index, index + 2), 16),
  )
  return (
    0.2126 * srgbChannel(red) +
    0.7152 * srgbChannel(green) +
    0.0722 * srgbChannel(blue)
  )
}

function contrastRatio(foreground: string, background: string): number {
  const first = relativeLuminance(foreground)
  const second = relativeLuminance(background)
  const lighter = Math.max(first, second)
  const darker = Math.min(first, second)
  return (lighter + 0.05) / (darker + 0.05)
}

function colorToken(className: string, prefix: 'bg' | 'text'): string {
  const token = className
    .split(/\s+/)
    .find((part) => part.startsWith(`${prefix}-`))
  return token?.slice(prefix.length + 1) ?? ''
}

afterEach(() => {
  while (mounted.length > 0) {
    mounted.pop()?.unmount()
  }
})

describe('Contraste WCAG 2.1 AA del semáforo', () => {
  it('los pares texto/fondo de las cuatro bandas superan 4,5:1', () => {
    for (const semaphore of ['verde', 'ambar', 'rojo', 'sin_datos'] as const) {
      const className = SEMAPHORE_BADGE_CLASS[semaphore]
      const backgroundToken = colorToken(className, 'bg')
      const foregroundToken = colorToken(className, 'text')

      expect(backgroundToken).not.toBe('')
      expect(foregroundToken).not.toBe('')

      const background = TAILWIND_HEX[backgroundToken]
      const foreground = TAILWIND_HEX[foregroundToken]
      expect(background).toBeDefined()
      expect(foreground).toBeDefined()

      expect(contrastRatio(foreground, background)).toBeGreaterThanOrEqual(4.5)
    }
  })
})

describe('Accesibilidad del dashboard de SLA (axe-core)', () => {
  beforeEach(async () => {
    document.documentElement.lang = 'es'
    setActivePinia(createPinia())
    const { fetchSlaDashboard, fetchSlaDashboardOptions } = await import(
      '@/api/slaDashboard'
    )
    vi.mocked(fetchSlaDashboard).mockResolvedValue(makeResponse())
    vi.mocked(fetchSlaDashboardOptions).mockResolvedValue(makeOptions())
  })

  it('la página completa no tiene violaciones graves, moderadas ni críticas', async () => {
    const wrapper = attach(
      mount(SlaDashboardPage, {
        attachTo: document.body,
        global: { plugins: [createPinia()] },
      }),
    )
    await flushPromises()

    expect(await blockingViolations(wrapper)).toEqual([])
  })

  it('los filtros no tienen violaciones graves, moderadas ni críticas', async () => {
    const wrapper = attach(
      mount(SlaDashboardFilters, {
        attachTo: document.body,
        props: {
          filters: { desde: '2026-10-17', hasta: '2026-11-15', categorias: [], prioridades: [] },
          options: makeOptions(),
        },
      }),
    )

    expect(await blockingViolations(wrapper)).toEqual([])
  })

  it('la matriz no tiene violaciones graves, moderadas ni críticas', async () => {
    const response = makeResponse()
    const wrapper = attach(
      mount(ComplianceMatrix, {
        attachTo: document.body,
        props: {
          matrix: response.data.matrix,
          priorityTotals: response.data.priority_totals,
          categoryTotals: response.data.category_totals,
          summary: response.data.summary,
        },
      }),
    )

    expect(await blockingViolations(wrapper)).toEqual([])
  })

  it('el semáforo y su leyenda no tienen violaciones graves, moderadas ni críticas', async () => {
    for (const semaphore of ['verde', 'ambar', 'rojo', 'sin_datos'] as const) {
      const wrapper = attach(
        mount(SemaphoreBadge, {
          attachTo: document.body,
          props: {
            semaphore,
            pct: semaphore === 'sin_datos' ? null : 87.5,
          },
        }),
      )
      expect(await blockingViolations(wrapper)).toEqual([])
      wrapper.unmount()
      mounted.pop()
    }

    const legend = attach(
      mount(SemaphoreLegend, {
        attachTo: document.body,
        props: { thresholds: { green_pct: 90, amber_pct: 70 } },
      }),
    )
    expect(await blockingViolations(legend)).toEqual([])
  })

  it('el ranking no tiene violaciones graves, moderadas ni críticas', async () => {
    const wrapper = attach(
      mount(TechnicianRanking, {
        attachTo: document.body,
        props: { ranking: makeResponse().data.ranking },
      }),
    )

    expect(await blockingViolations(wrapper)).toEqual([])
  })

  it('los estados vacíos y de error no tienen violaciones graves, moderadas ni críticas', async () => {
    for (const variant of ['periodo', 'filtros', 'sin-sla', 'sin-vencidos'] as const) {
      const wrapper = attach(
        mount(DashboardEmptyState, {
          attachTo: document.body,
          props: { variant },
        }),
      )
      expect(await blockingViolations(wrapper)).toEqual([])
      wrapper.unmount()
      mounted.pop()
    }

    for (const variant of ['full', 'warning', 'forbidden'] as const) {
      const wrapper = attach(
        mount(DashboardErrorState, {
          attachTo: document.body,
          props: { variant },
        }),
      )
      expect(await blockingViolations(wrapper)).toEqual([])
      wrapper.unmount()
      mounted.pop()
    }
  })
})
