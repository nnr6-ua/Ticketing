import { mount } from '@vue/test-utils'
import axe from 'axe-core'
import { describe, expect, it } from 'vitest'

import AssigneeSelector from '@/components/tickets/AssigneeSelector.vue'
import type { AssigneeRef } from '@/types/assigneeChange'

function candidate(overrides: Partial<AssigneeRef> = {}): AssigneeRef {
  return {
    id: 'u2',
    name: 'Técnico B',
    role: 'tecnico',
    team: 'Soporte',
    escalation_level: 'nivel_1',
    escalation_level_label: 'Nivel 1',
    ...overrides,
  }
}

const candidates = [
  candidate(),
  candidate({
    id: 'u3',
    name: 'Técnica C',
    team: null,
    escalation_level: 'nivel_2',
    escalation_level_label: 'Nivel 2',
  }),
]

describe('AssigneeSelector', () => {
  it('renderiza nombre, equipo y nivel de los candidatos del backend', () => {
    const wrapper = mount(AssigneeSelector, {
      props: { modelValue: null, candidates },
    })

    const options = wrapper.findAll('option')
    expect(options.map((option) => option.text())).toEqual([
      'Selecciona un compañero',
      'Técnico B · Soporte — Nivel 1',
      'Técnica C — Nivel 2',
    ])
    expect(wrapper.find('fieldset').exists()).toBe(true)
    expect(wrapper.find('legend').text()).toBe('Compañero destino')
    expect(wrapper.find('select').attributes('aria-required')).toBe('true')
  })

  it('emite el id seleccionado y null al limpiar la selección', async () => {
    const wrapper = mount(AssigneeSelector, {
      props: { modelValue: null, candidates },
    })

    await wrapper.find('select').setValue('u2')
    expect(wrapper.emitted('update:modelValue')).toEqual([['u2']])

    await wrapper.find('select').setValue('')
    expect(wrapper.emitted('update:modelValue')?.[1]).toEqual([null])
  })

  it('muestra el estado vacío sin renderizar el selector', () => {
    const wrapper = mount(AssigneeSelector, {
      props: { modelValue: null, candidates: [] },
    })

    expect(wrapper.text()).toContain(
      'No hay compañeros disponibles de tu equipo y nivel.',
    )
    expect(wrapper.find('select').exists()).toBe(false)
  })

  it('deshabilita el control durante un envío', () => {
    const wrapper = mount(AssigneeSelector, {
      props: { modelValue: 'u2', candidates, disabled: true },
    })

    expect(wrapper.find('select').attributes('disabled')).toBeDefined()
  })

  it('no tiene violaciones críticas de accesibilidad', async () => {
    document.documentElement.lang = 'es'
    const wrapper = mount(AssigneeSelector, {
      attachTo: document.body,
      props: { modelValue: 'u2', candidates },
    })

    const results = await axe.run(wrapper.element, {
      rules: { 'color-contrast': { enabled: false } },
    })
    expect(results.violations.filter((v) => v.impact === 'critical')).toEqual([])
    wrapper.unmount()
  })
})
