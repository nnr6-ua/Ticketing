import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import SlaSummary from '@/components/sla-dashboard/SlaSummary.vue'
import { makeMetrics } from '../fixtures/slaDashboard'

describe('SlaSummary', () => {
  it('muestra las seis cifras del resumen global', () => {
    const wrapper = mount(SlaSummary, {
      props: { summary: makeMetrics() },
    })

    expect(wrapper.text()).toContain('Tickets considerados')
    expect(wrapper.text()).toContain('Atendidos con SLA')
    expect(wrapper.text()).toContain('Cumplimiento')
    expect(wrapper.text()).toContain('Tiempo medio')
    expect(wrapper.text()).toContain('Vencidos')
    expect(wrapper.text()).toContain('Sin SLA')
  })

  it('formatea el porcentaje y la duración en es-ES', () => {
    const wrapper = mount(SlaSummary, {
      props: {
        summary: makeMetrics({
          compliance_pct: 87.5,
          avg_response_seconds: 4 * 3600 + 12 * 60,
        }),
      },
    })

    expect(wrapper.text()).toContain('87,5 %')
    expect(wrapper.text()).toContain('4 h 12 min')
    expect(wrapper.text()).toContain('En riesgo')
  })

  it('usa «Sin datos» cuando no hay métricas de cumplimiento ni media', () => {
    const wrapper = mount(SlaSummary, {
      props: {
        summary: makeMetrics({
          compliance_pct: null,
          avg_response_seconds: null,
          semaphore: 'sin_datos',
          attended_with_sla: 0,
          on_time: 0,
          no_sla_count: 10,
        }),
      },
    })

    expect(wrapper.findAll('.sr-only').map((node) => node.text())).toContain(
      'Sin datos',
    )
    expect(wrapper.text()).toContain('Sin datos')
  })

  it('formatea los recuentos enteros con separador de miles es-ES', () => {
    const wrapper = mount(SlaSummary, {
      props: {
        summary: makeMetrics({
          ticket_count: 10000,
          no_sla_count: 12500,
          attended_with_sla: 18750,
          overdue_count: 12000,
        }),
      },
    })

    expect(wrapper.text()).toContain('10.000')
    expect(wrapper.text()).toContain('18.750')
    expect(wrapper.text()).toContain('12.500')
    expect(wrapper.text()).toContain('12.000')
  })

  it('es una vista de solo lectura sin acciones de edición', () => {
    const wrapper = mount(SlaSummary, {
      props: { summary: makeMetrics() },
    })

    expect(wrapper.find('button').exists()).toBe(false)
    expect(wrapper.find('form').exists()).toBe(false)
    expect(wrapper.find('input').exists()).toBe(false)
  })
})
