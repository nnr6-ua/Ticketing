import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import SemaphoreBadge from '@/components/sla-dashboard/SemaphoreBadge.vue'

describe('SemaphoreBadge', () => {
  it('muestra texto, icono, porcentaje y aria-label para verde', () => {
    const wrapper = mount(SemaphoreBadge, {
      props: { semaphore: 'verde', pct: 95 },
    })

    expect(wrapper.attributes('data-semaphore')).toBe('verde')
    expect(wrapper.attributes('role')).toBe('img')
    expect(wrapper.attributes('aria-label')).toBe(
      'Cumplimiento 95,0 %, en objetivo',
    )
    expect(wrapper.text()).toContain('En objetivo')
    expect(wrapper.text()).toContain('95,0 %')
    expect(wrapper.find('svg').exists()).toBe(true)
    expect(wrapper.classes().join(' ')).toContain('emerald')
  })

  it('muestra «En riesgo» en la banda ámbar', () => {
    const wrapper = mount(SemaphoreBadge, {
      props: { semaphore: 'ambar', pct: 70 },
    })

    expect(wrapper.text()).toContain('En riesgo')
    expect(wrapper.text()).toContain('70,0 %')
    expect(wrapper.find('svg').exists()).toBe(true)
    expect(wrapper.attributes('aria-label')).toBe(
      'Cumplimiento 70,0 %, en riesgo',
    )
    expect(wrapper.classes().join(' ')).toContain('amber')
  })

  it('muestra «Fuera de objetivo» en rojo', () => {
    const wrapper = mount(SemaphoreBadge, {
      props: { semaphore: 'rojo', pct: 69.9 },
    })

    expect(wrapper.text()).toContain('Fuera de objetivo')
    expect(wrapper.text()).toContain('69,9 %')
    expect(wrapper.find('svg').exists()).toBe(true)
    expect(wrapper.attributes('aria-label')).toBe(
      'Cumplimiento 69,9 %, fuera de objetivo',
    )
    expect(wrapper.classes().join(' ')).toContain('red')
  })

  it('usa el estado neutro «Sin datos» sin color de alarma', () => {
    const wrapper = mount(SemaphoreBadge, {
      props: { semaphore: 'sin_datos', pct: null },
    })

    expect(wrapper.attributes('data-semaphore')).toBe('sin_datos')
    expect(wrapper.text()).toContain('Sin datos')
    expect(wrapper.find('svg').exists()).toBe(true)
    expect(wrapper.attributes('aria-label')).toBe(
      'Cumplimiento sin datos, sin datos',
    )
    const classes = wrapper.classes().join(' ')
    expect(classes).toContain('slate')
    expect(classes).not.toContain('red')
    expect(classes).not.toContain('amber')
    expect(classes).not.toContain('emerald')
  })

  it('en variante compacta mantiene la etiqueta accesible', () => {
    const wrapper = mount(SemaphoreBadge, {
      props: { semaphore: 'verde', pct: 100, compact: true },
    })

    expect(wrapper.classes().join(' ')).toContain('text-xs')
    const hidden = wrapper.find('.sr-only')
    expect(hidden.exists()).toBe(true)
    expect(hidden.text()).toBe('En objetivo')
    expect(wrapper.attributes('aria-label')).toBe(
      'Cumplimiento 100,0 %, en objetivo',
    )
  })
})
