import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import SemaphoreLegend from '@/components/sla-dashboard/SemaphoreLegend.vue'

describe('SemaphoreLegend', () => {
  it('explica las cuatro bandas con texto, color e icono de lucide por banda', () => {
    const wrapper = mount(SemaphoreLegend, {
      props: { thresholds: { green_pct: 90, amber_pct: 70 } },
    })

    expect(wrapper.findAll('[data-band]')).toHaveLength(4)
    expect(wrapper.text()).toContain('En objetivo')
    expect(wrapper.text()).toContain('En riesgo')
    expect(wrapper.text()).toContain('Fuera de objetivo')
    expect(wrapper.text()).toContain('Sin datos')

    const expectedIcons: Record<string, string> = {
      verde: 'lucide-circle-check-icon',
      ambar: 'lucide-triangle-alert-icon',
      rojo: 'lucide-octagon-alert-icon',
      sin_datos: 'lucide-circle-minus-icon',
    }
    const rendered = new Set<string>()
    for (const [band, iconClass] of Object.entries(expectedIcons)) {
      const icons = wrapper.findAll(`[data-band="${band}"] svg`)
      expect(icons).toHaveLength(1)
      expect(icons[0].attributes('aria-hidden')).toBe('true')
      expect(icons[0].classes().join(' ')).toContain(iconClass)
      rendered.add(icons[0].html())
    }
    expect(rendered.size).toBe(4)
  })

  it('usa los umbrales recibidos y no valores fijos', () => {
    const wrapper = mount(SemaphoreLegend, {
      props: { thresholds: { green_pct: 95, amber_pct: 75 } },
    })

    expect(wrapper.text()).toContain('95,0 %')
    expect(wrapper.text()).toContain('75,0 %')
    expect(wrapper.text()).not.toContain('90,0 %')
    expect(wrapper.text()).not.toContain('70,0 %')
  })
})
