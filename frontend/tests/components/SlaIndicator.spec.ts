import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import SlaIndicator from '@/components/work-queue/SlaIndicator.vue'
import type { SlaOutcome, SlaState } from '@/types/workQueue'

function mountIndicator(
  state: SlaState,
  remainingSeconds: number | null,
  outcome: SlaOutcome = null,
  breachDelaySeconds: number | null = null,
) {
  return mount(SlaIndicator, {
    props: { state, remainingSeconds, outcome, breachDelaySeconds },
  })
}

describe('SlaIndicator', () => {
  it('muestra el estado vencido en rojo, con icono y texto', () => {
    const wrapper = mountIndicator('overdue', -(2 * 3600))

    expect(wrapper.text()).toBe('Vencido hace 2 h')
    expect(wrapper.attributes('data-sla-state')).toBe('overdue')
    expect(wrapper.classes()).toContain('bg-red-100')
    expect(wrapper.find('svg').exists()).toBe(true)
  })

  it('muestra el estado próximo a vencer en ámbar', () => {
    const wrapper = mountIndicator('at_risk', 10 * 60)

    expect(wrapper.text()).toBe('Próximo a vencer · 10 min')
    expect(wrapper.attributes('data-sla-state')).toBe('at_risk')
    expect(wrapper.classes()).toContain('bg-amber-100')
  })

  it('muestra "Vence ahora" en el límite exacto sin marcarlo como vencido', () => {
    const wrapper = mountIndicator('at_risk', 0)

    expect(wrapper.text()).toBe('Vence ahora')
    expect(wrapper.attributes('data-sla-state')).toBe('at_risk')
  })

  it('muestra el estado dentro de plazo', () => {
    const wrapper = mountIndicator('on_time', 20 * 60)

    expect(wrapper.text()).toBe('Dentro de plazo · 20 min')
    expect(wrapper.attributes('data-sla-state')).toBe('on_time')
  })

  it('muestra "Sin SLA definido" sin alarma', () => {
    const wrapper = mountIndicator('no_sla', null)

    expect(wrapper.text()).toBe('Sin SLA definido')
    expect(wrapper.attributes('data-sla-state')).toBe('no_sla')
    expect(wrapper.classes()).toContain('bg-slate-100')
    expect(wrapper.classes()).not.toContain('bg-amber-100')
    expect(wrapper.classes()).not.toContain('bg-red-100')
  })

  it('no muestra cuenta atrás en un finalizado cumplido', () => {
    const wrapper = mountIndicator('finalized', null, 'met')

    expect(wrapper.text()).toBe('Dentro de plazo')
    expect(wrapper.attributes('data-sla-state')).toBe('finalized')
  })

  it('muestra el retraso estático de un finalizado incumplido', () => {
    const wrapper = mountIndicator('finalized', null, 'breached', 2 * 3600 + 5 * 60)

    expect(wrapper.text()).toBe('Incumplido hace 2 h 5 min')
    expect(wrapper.attributes('data-sla-state')).toBe('finalized')
  })

  it('muestra "Sin SLA definido" en un finalizado sin SLA', () => {
    const wrapper = mountIndicator('finalized', null, 'no_sla')

    expect(wrapper.text()).toBe('Sin SLA definido')
  })

  it('usa icono decorativo y texto visible, sin aria-live por tick', () => {
    const wrapper = mountIndicator('overdue', -60)

    const icon = wrapper.find('svg')
    expect(icon.exists()).toBe(true)
    expect(icon.attributes('aria-hidden')).toBe('true')
    expect(wrapper.attributes('aria-live')).toBeUndefined()
    expect(wrapper.find('span').text()).toContain('Vencido hace')
  })
})
