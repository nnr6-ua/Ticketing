import { RouterLinkStub, mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import WorkQueueTable from '@/components/work-queue/WorkQueueTable.vue'
import type { WorkQueueItem } from '@/types/workQueue'

function makeItem(overrides: Partial<WorkQueueItem> = {}): WorkQueueItem {
  return {
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
    ...overrides,
  }
}

function mountTable(items: WorkQueueItem[]) {
  return mount(WorkQueueTable, {
    props: { items, nowMs: 1_000_000, dataNowMs: 1_000_000 },
    global: { stubs: { RouterLink: RouterLinkStub } },
  })
}

describe('WorkQueueTable', () => {
  it('renderiza una tabla semántica con caption oculto y seis columnas', () => {
    const wrapper = mountTable([makeItem()])

    expect(wrapper.find('table').exists()).toBe(true)
    const caption = wrapper.find('caption')
    expect(caption.exists()).toBe(true)
    expect(caption.classes()).toContain('sr-only')
    expect(caption.text()).toContain('Cola de trabajo priorizada')

    const headers = wrapper.findAll('th').map((th) => th.text())
    expect(headers).toEqual([
      'Ticket',
      'Título',
      'Categoría',
      'Prioridad',
      'Estado',
      'SLA',
    ])
    expect(wrapper.findAll('th').every((th) => th.attributes('scope') === 'col')).toBe(
      true,
    )
  })

  it('muestra los cinco datos exigidos en cada fila', () => {
    const wrapper = mountTable([makeItem()])
    const row = wrapper.find('[data-testid="work-queue-row"]')

    expect(row.text()).toContain('TK-000001')
    expect(row.text()).toContain('No puedo acceder a la VPN desde casa')
    expect(row.text()).toContain('Red')
    expect(row.text()).toContain('Crítica')
    expect(row.text()).toContain('Abierto')
    expect(row.text()).toContain('Próximo a vencer · 1 h')
  })

  it('enlaza el número y el título al detalle del ticket', () => {
    const wrapper = mountTable([makeItem({ id: 'abc-123' })])
    const links = wrapper.findAllComponents(RouterLinkStub)

    expect(links).toHaveLength(2)
    expect(links[0].props('to')).toBe('/tickets/abc-123')
    expect(links[1].props('to')).toBe('/tickets/abc-123')
    expect(links[1].attributes('title')).toBe(
      'No puedo acceder a la VPN desde casa',
    )
  })

  it('trunca el título largo sin perder el texto completo', () => {
    const longTitle = 'Título muy largo '.repeat(20).trim()
    const wrapper = mountTable([makeItem({ title: longTitle })])
    const links = wrapper.findAllComponents(RouterLinkStub)

    expect(links[1].classes()).toContain('truncate')
    expect(links[1].attributes('title')).toBe(longTitle)
    expect(links[1].text()).toBe(longTitle)
  })

  it('muestra "Sin categoría" cuando el ticket no tiene categoría', () => {
    const wrapper = mountTable([makeItem({ category: null })])

    expect(wrapper.find('[data-testid="work-queue-row"]').text()).toContain(
      'Sin categoría',
    )
  })

  it('marca las prioridades inactivas sin romper el orden ni la alineación', () => {
    const wrapper = mountTable([
      makeItem({
        id: 't2',
        number: 'TK-000002',
        priority: {
          id: 'p2',
          name: 'Alta',
          level: 2,
          color: null,
          is_active: false,
        },
      }),
    ])

    const row = wrapper.find('[data-testid="work-queue-row"]')
    expect(row.text()).toContain('Alta')
    expect(row.text()).toContain('(inactiva)')
  })
})
