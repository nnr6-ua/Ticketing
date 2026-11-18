import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import TechnicianRanking from '@/components/sla-dashboard/TechnicianRanking.vue'
import { makeRankingEntry } from '../fixtures/slaDashboard'

const ranking = {
  technicians: [
    makeRankingEntry(),
    makeRankingEntry({
      technician_id: '33333333-3333-4333-8333-333333333333',
      technician_name: 'Luis Pérez',
      team: 'Redes',
      is_active: false,
      overdue_count: 1,
      avg_delay_seconds: 3600,
    }),
  ],
  unassigned: makeRankingEntry({
    technician_id: null,
    technician_name: 'Sin asignar',
    team: null,
    is_active: null,
    overdue_count: 2,
    avg_delay_seconds: 7200,
  }),
  overdue_total: 6,
}

describe('TechnicianRanking', () => {
  it('muestra las columnas y respeta el orden recibido', () => {
    const wrapper = mount(TechnicianRanking, { props: { ranking } })

    const headers = wrapper.findAll('th[scope="col"]').map((th) => th.text())
    expect(headers).toEqual([
      'Posición',
      'Técnico',
      'Equipo',
      'Vencidos',
      'Retraso medio',
    ])

    const rows = wrapper.findAll('tbody tr')
    expect(rows).toHaveLength(3)
    expect(rows[0]?.text()).toContain('Ana Torres')
    expect(rows[0]?.text()).toContain('1')
    expect(rows[1]?.text()).toContain('Luis Pérez')
    expect(rows[2]?.text()).toContain('Sin asignar')
  })

  it('marca a los técnicos inactivos y separa la fila «Sin asignar»', () => {
    const wrapper = mount(TechnicianRanking, { props: { ranking } })

    const rows = wrapper.findAll('tbody tr')
    expect(rows[1]?.text()).toContain('(inactivo)')
    expect(rows[2]?.attributes('data-unassigned')).toBe('true')
    expect(rows[2]?.classes().join(' ')).toContain('bg-slate-50')
  })

  it('muestra el total de vencidos y el retraso medio formateado', () => {
    const wrapper = mount(TechnicianRanking, { props: { ranking } })

    expect(wrapper.text()).toContain('Total de vencidos:')
    expect(wrapper.text()).toContain('6')
    expect(wrapper.text()).toContain('2 h')
    expect(wrapper.text()).toContain('1 h')
  })

  it('formatea los recuentos de vencidos con separador de miles es-ES', () => {
    const wrapper = mount(TechnicianRanking, {
      props: {
        ranking: {
          technicians: [makeRankingEntry({ overdue_count: 10000 })],
          unassigned: null,
          overdue_total: 10000,
        },
      },
    })

    const row = wrapper.find('tbody tr')
    expect(row.text()).toContain('10.000')
    expect(wrapper.text()).toContain('Total de vencidos:')
    expect(wrapper.text()).toContain('10.000')
  })

  it('usa un estado vacío específico cuando no hay vencidos', () => {
    const wrapper = mount(TechnicianRanking, {
      props: {
        ranking: { technicians: [], unassigned: null, overdue_total: 0 },
      },
    })

    expect(wrapper.find('table').exists()).toBe(false)
    expect(wrapper.text()).toContain(
      'No hay tickets vencidos en el periodo seleccionado.',
    )
    expect(wrapper.find('[role="status"]').exists()).toBe(true)
  })

  it('incluye caption y cabeceras accesibles', () => {
    const wrapper = mount(TechnicianRanking, { props: { ranking } })

    expect(wrapper.find('caption').exists()).toBe(true)
    const headers = wrapper.findAll('th')
    expect(headers.length).toBeGreaterThan(0)
    expect(headers.every((th) => th.attributes('scope') !== undefined)).toBe(
      true,
    )
  })

  it('no expone correos ni tickets individuales', () => {
    const wrapper = mount(TechnicianRanking, { props: { ranking } })

    expect(wrapper.text()).not.toContain('@')
    expect(wrapper.text()).not.toContain('TK-')
  })
})
