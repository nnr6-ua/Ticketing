import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import TicketStatusSelector from '@/components/tickets/TicketStatusSelector.vue'

const options = [
  { value: 'abierto' as const, label: 'Abierto' },
  { value: 'en_progreso' as const, label: 'En progreso' },
]

describe('TicketStatusSelector', () => {
  it('solo renderiza las opciones permitidas y no ofrece el estado actual', () => {
    const wrapper = mount(TicketStatusSelector, {
      props: { currentStatus: 'abierto', options },
    })

    const radios = wrapper.findAll('input[type="radio"]')
    expect(radios).toHaveLength(1)
    expect((radios[0]?.element as HTMLInputElement).value).toBe('en_progreso')
    expect(wrapper.text()).toContain('Estado actual: Abierto')
    expect(wrapper.text()).toContain('Nuevo estado')
    expect(wrapper.find('fieldset').exists()).toBe(true)
    expect(wrapper.find('legend').text()).toBe('Nuevo estado')
  })

  it('muestra el mensaje de lista vacía sin controles', () => {
    const wrapper = mount(TicketStatusSelector, {
      props: { currentStatus: 'cerrado', options: [] },
    })

    expect(wrapper.text()).toContain('No hay cambios de estado disponibles.')
    expect(wrapper.find('input[type="radio"]').exists()).toBe(false)
  })

  it('emite select con el destino elegido', async () => {
    const wrapper = mount(TicketStatusSelector, {
      props: { currentStatus: 'abierto', options },
    })

    await wrapper.find('input[type="radio"]').trigger('change')

    expect(wrapper.emitted('select')).toEqual([['en_progreso']])
  })

  it('deshabilita los controles y aplica opacidad cuando disabled es true', () => {
    const wrapper = mount(TicketStatusSelector, {
      props: { currentStatus: 'abierto', options, disabled: true },
    })

    expect(wrapper.find('fieldset').attributes('disabled')).toBeDefined()
    expect(wrapper.find('input[type="radio"]').attributes('disabled')).toBeDefined()
    expect(wrapper.find('fieldset').classes()).toContain('opacity-50')
  })
})
