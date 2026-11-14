import { mount } from '@vue/test-utils'
import axe from 'axe-core'
import { describe, expect, it } from 'vitest'

import EscalationLevelSelector from '@/components/tickets/EscalationLevelSelector.vue'
import type { EscalationTarget } from '@/types/assigneeChange'

const targets: EscalationTarget[] = [
  {
    value: 'nivel_2',
    label: 'Nivel 2',
    technician_count: 3,
    is_available: true,
  },
  {
    value: 'especialista',
    label: 'Especialista',
    technician_count: 0,
    is_available: false,
  },
]

describe('EscalationLevelSelector', () => {
  it('solo renderiza los niveles superiores indicados por el backend', () => {
    const wrapper = mount(EscalationLevelSelector, {
      props: { modelValue: null, targets },
    })

    const labels = wrapper
      .findAll('label')
      .map((label) => label.text().replace(/\s+/g, ' ').trim())
    expect(labels).toEqual(['Nivel 2', 'Especialista Sin técnicos disponibles'])
    expect(wrapper.find('legend').text()).toBe('Nivel destino')
    expect(wrapper.text()).not.toContain('Nivel 1')
  })

  it('deshabilita los niveles sin técnicos y no emite al pulsarlos', async () => {
    const wrapper = mount(EscalationLevelSelector, {
      props: { modelValue: null, targets },
    })

    const radios = wrapper.findAll('input[type="radio"]')
    expect(radios[1]?.attributes('disabled')).toBeDefined()

    await radios[0]?.trigger('change')
    expect(wrapper.emitted('update:modelValue')).toEqual([['nivel_2']])
  })

  it('nunca envía un id de persona', () => {
    const wrapper = mount(EscalationLevelSelector, {
      props: { modelValue: 'nivel_2', targets },
    })

    expect(wrapper.find('input[type="radio"][value="nivel_2"]').exists()).toBe(
      true,
    )
    expect(wrapper.html()).not.toContain('assignee')
  })

  it('muestra el estado vacío en el nivel máximo', () => {
    const wrapper = mount(EscalationLevelSelector, {
      props: { modelValue: null, targets: [] },
    })

    expect(wrapper.text()).toContain(
      'El ticket ya está en el nivel máximo de soporte.',
    )
    expect(wrapper.find('input[type="radio"]').exists()).toBe(false)
  })

  it('limpia la selección si el nivel deja de estar disponible', async () => {
    const wrapper = mount(EscalationLevelSelector, {
      props: { modelValue: 'especialista', targets },
    })

    expect(wrapper.emitted('update:modelValue')).toBeUndefined()

    await wrapper.setProps({
      targets: [
        {
          value: 'nivel_2',
          label: 'Nivel 2',
          technician_count: 1,
          is_available: true,
        },
        {
          value: 'especialista',
          label: 'Especialista',
          technician_count: 0,
          is_available: false,
        },
      ],
    })

    expect(wrapper.emitted('update:modelValue')).toEqual([[null]])
  })

  it('no tiene violaciones críticas de accesibilidad', async () => {
    document.documentElement.lang = 'es'
    const wrapper = mount(EscalationLevelSelector, {
      attachTo: document.body,
      props: { modelValue: 'nivel_2', targets },
    })

    const results = await axe.run(wrapper.element, {
      rules: { 'color-contrast': { enabled: false } },
    })
    expect(results.violations.filter((v) => v.impact === 'critical')).toEqual([])
    wrapper.unmount()
  })
})
