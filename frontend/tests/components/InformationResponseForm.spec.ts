import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import InformationResponseForm from '@/components/tickets/InformationResponseForm.vue'
import type { InformationRequestRef } from '@/types/ticketWorkflow'

const REQUEST: InformationRequestRef = {
  id: 'r1',
  body: '¿Qué versión del navegador usas?',
  requested_at: '2026-11-13T10:00:00Z',
  requested_by: { id: 'u1', name: 'Laura Técnica', role: 'tecnico' },
}

function submitButton(wrapper: ReturnType<typeof mount>) {
  return wrapper.find('button[type="submit"]')
}

describe('InformationResponseForm', () => {
  it('muestra la petición activa con autor y fecha', () => {
    const wrapper = mount(InformationResponseForm, {
      props: { modelValue: '', request: REQUEST },
    })

    expect(wrapper.text()).toContain('El técnico necesita esta información')
    expect(wrapper.text()).toContain('¿Qué versión del navegador usas?')
    expect(wrapper.text()).toContain('Laura Técnica')
    expect(wrapper.find('[role="note"]').exists()).toBe(true)
  })

  it('muestra un aviso cuando el ticket legado no tiene petición', () => {
    const wrapper = mount(InformationResponseForm, {
      props: { modelValue: '', request: null },
    })

    expect(wrapper.text()).toContain('Este ticket está pendiente de tu respuesta')
    expect(wrapper.find('[role="note"]').exists()).toBe(false)
    expect(wrapper.find('[role="status"]').exists()).toBe(true)
  })

  it('emite update:modelValue y submit con texto válido', async () => {
    const wrapper = mount(InformationResponseForm, {
      props: { modelValue: '', request: REQUEST },
    })

    await wrapper.find('textarea').setValue('Uso Chrome 131.')
    expect(wrapper.emitted('update:modelValue')).toEqual([['Uso Chrome 131.']])

    await wrapper.setProps({ modelValue: 'Uso Chrome 131.' })
    await wrapper.find('form').trigger('submit')
    expect(wrapper.emitted('submit')).toHaveLength(1)
  })

  it('deshabilita el envío vacío, por encima de 5000 o disabled', async () => {
    const wrapper = mount(InformationResponseForm, {
      props: { modelValue: '', request: REQUEST },
    })
    expect(submitButton(wrapper).attributes('disabled')).toBeDefined()

    await wrapper.setProps({ modelValue: '   ' })
    expect(submitButton(wrapper).attributes('disabled')).toBeDefined()

    await wrapper.setProps({ modelValue: 'a'.repeat(5001) })
    expect(submitButton(wrapper).attributes('disabled')).toBeDefined()
    expect(wrapper.find('#information-response-counter').classes()).toContain(
      'text-red-700',
    )

    await wrapper.setProps({ modelValue: 'Respuesta', disabled: true })
    expect(submitButton(wrapper).attributes('disabled')).toBeDefined()
  })

  it('muestra el error y no interpreta HTML en el cuerpo', () => {
    const wrapper = mount(InformationResponseForm, {
      props: {
        modelValue: 'Respuesta',
        request: { ...REQUEST, body: '<b>No interpretar HTML</b>' },
        error: 'Error del servidor.',
      },
    })

    expect(wrapper.find('[role="alert"]').text()).toBe('Error del servidor.')
    expect(wrapper.text()).toContain('<b>No interpretar HTML</b>')
    expect(wrapper.find('b').exists()).toBe(false)
  })
})
