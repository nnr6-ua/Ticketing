import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import ComplianceMatrix from '@/components/sla-dashboard/ComplianceMatrix.vue'
import {
  makeMatrixRow,
  makeMetrics,
  makeTotalsEntry,
} from '../fixtures/slaDashboard'

const redId = '11111111-1111-4111-8111-111111111111'

const matrixProps = {
  matrix: [
    makeMatrixRow({
      priority_level: 1,
      priority_name: 'Crítica',
      category_id: redId,
      category_name: 'Red',
      compliance_pct: 90,
      semaphore: 'verde',
    }),
    makeMatrixRow({
      priority_level: 2,
      priority_name: 'Alta',
      category_id: null,
      category_name: 'Sin categoría',
      category_is_active: null,
      compliance_pct: null,
      semaphore: 'sin_datos',
    }),
  ],
  priorityTotals: [
    makeTotalsEntry({ priority_level: 1, priority_name: 'Crítica' }),
    makeTotalsEntry({
      priority_level: 2,
      priority_name: 'Alta',
      priority_is_active: false,
    }),
  ],
  categoryTotals: [
    makeTotalsEntry({
      scope: 'category' as const,
      priority_level: null,
      priority_name: null,
      priority_is_active: null,
      category_id: redId,
      category_name: 'Red',
      category_is_active: true,
    }),
    makeTotalsEntry({
      scope: 'category' as const,
      priority_level: null,
      priority_name: null,
      priority_is_active: null,
      category_id: null,
      category_name: 'Sin categoría',
      category_is_active: null,
    }),
  ],
  summary: makeMetrics(),
}

describe('ComplianceMatrix', () => {
  it('ordena las filas por prioridad y las columnas alfabéticamente', () => {
    const wrapper = mount(ComplianceMatrix, { props: matrixProps })

    const rows = wrapper.findAll('tbody tr')
    expect(rows.map((row) => row.attributes('data-priority-level'))).toEqual([
      '1',
      '2',
    ])

    const headers = wrapper
      .findAll('thead th[scope="col"]')
      .map((th) => th.text())
    expect(headers).toEqual(['Prioridad', 'Red', 'Sin categoría', 'Total'])
  })

  it('solo pinta celdas con datos y deja vacías las combinaciones sin tickets', () => {
    const wrapper = mount(ComplianceMatrix, { props: matrixProps })

    expect(wrapper.findAll('[data-testid="matrix-cell"]')).toHaveLength(7)
    // Dos combinaciones sin datos: Crítica × Sin categoría y Alta × Red.
    const placeholders = wrapper
      .findAll('tbody span[aria-hidden="true"]')
      .filter((node) => node.text() === '—')
    expect(placeholders).toHaveLength(2)
  })

  it('mantiene totales por fila, por columna y global siempre visibles', () => {
    const wrapper = mount(ComplianceMatrix, { props: matrixProps })

    const footer = wrapper.find('tfoot')
    expect(footer.exists()).toBe(true)
    expect(footer.findAll('[data-testid="matrix-cell"]')).toHaveLength(3)
    expect(wrapper.findAll('tbody tr').every((row) => row.find('[data-testid="matrix-cell"]').exists())).toBe(true)
  })

  it('propaga el sufijo «(inactiva)» de prioridades y categorías', () => {
    const wrapper = mount(ComplianceMatrix, {
      props: {
        ...matrixProps,
        priorityTotals: [
          makeTotalsEntry({ priority_level: 2, priority_name: 'Alta', priority_is_active: false }),
        ],
        categoryTotals: [
          makeTotalsEntry({
            scope: 'category' as const,
            priority_level: null,
            priority_name: null,
            priority_is_active: null,
            category_id: redId,
            category_name: 'Red',
            category_is_active: false,
          }),
        ],
        matrix: [makeMatrixRow({ priority_level: 2, priority_name: 'Alta', category_id: redId, category_name: 'Red' })],
      },
    })

    expect(wrapper.text()).toContain('Alta (inactiva)')
    expect(wrapper.text()).toContain('Red (inactiva)')
  })

  it('formatea los recuentos de las celdas con separador de miles es-ES', () => {
    const wrapper = mount(ComplianceMatrix, {
      props: {
        ...matrixProps,
        matrix: [
          makeMatrixRow({
            priority_level: 1,
            category_id: redId,
            category_name: 'Red',
            ticket_count: 10000,
            overdue_count: 10250,
          }),
        ],
      },
    })

    const cell = wrapper.find('[data-testid="matrix-cell"]')
    expect(cell.text()).toContain('10.000 tickets')
    expect(cell.text()).toContain('10.250')
  })

  it('incluye caption y cabeceras con scope', () => {
    const wrapper = mount(ComplianceMatrix, { props: matrixProps })

    expect(wrapper.find('caption').exists()).toBe(true)
    const headers = wrapper.findAll('th')
    expect(headers.length).toBeGreaterThan(0)
    expect(headers.every((th) => th.attributes('scope') !== undefined)).toBe(true)
  })

  it('no muestra filas de ceros ni acciones de edición', () => {
    const wrapper = mount(ComplianceMatrix, { props: matrixProps })

    expect(wrapper.findAll('tbody tr')).toHaveLength(2)
    expect(wrapper.find('button').exists()).toBe(false)
    expect(wrapper.find('input').exists()).toBe(false)
  })
})
