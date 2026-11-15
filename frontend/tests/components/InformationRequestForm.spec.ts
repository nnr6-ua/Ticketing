import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import InformationRequestForm from '@/components/tickets/InformationRequestForm.vue'

function submitButton(wrapper: ReturnType<typeof mount>) {
  return wrapper.find('button[type="submit"]')
}

describe('InformationRequestForm', () => {
  it('muestra etiqueta, ayuda y contador en español', () => {
    const wrapper = mount(InformationRequestForm, {
      props: { modelValue: '' },
    })

    expect(wrapper.find('label').text()).toBe('Información que necesitas')
    expect(wrapper.text()).toContain(
      'Explica al usuario qué dato concreto necesitas para continuar.',
    )
    expect(wrapper.find('#information-request-counter').text()).toBe('0 / 5000')
    expect(wrapper.find('textarea').attributes('maxlength')).toBe('5000')
  })

  it('emite update:modelValue al escribir', async () => {
    const wrapper = mount(InformationRequestForm, {
      props: { modelValue: '' },
    })

    await wrapper.find('textarea').setValue('¿Qué navegador usas?')

    expect(wrapper.emitted('update:modelValue')).toEqual([
      ['¿Qué navegador usas?'],
    ])
  })

  it('deshabilita el envío con texto vacío, solo espacios o demasiado largo', async () => {
    const wrapper = mount(InformationRequestForm, {
      props: { modelValue: '' },
    })
    expect(submitButton(wrapper).attributes('disabled')).toBeDefined()

    await wrapper.setProps({ modelValue: '   ' })
    expect(submitButton(wrapper).attributes('disabled')).toBeDefined()

    await wrapper.setProps({ modelValue: 'a'.repeat(5001) })
    expect(submitButton(wrapper).attributes('disabled')).toBeDefined()
    expect(wrapper.find('#information-request-counter').classes()).toContain(
      'text-red-700',
    )

    await wrapper.setProps({ modelValue: 'Datos necesarios' })
    expect(submitButton(wrapper).attributes('disabled')).toBeUndefined()
  })

  it('emite submit solo con texto válido y no mientras disabled', async () => {
    const wrapper = mount(InformationRequestForm, {
      props: { modelValue: '' },
    })

    await wrapper.find('form').trigger('submit')
    expect(wrapper.emitted('submit')).toBeUndefined()

    await wrapper.setProps({ modelValue: 'Datos necesarios' })
    await wrapper.find('form').trigger('submit')
    expect(wrapper.emitted('submit')).toHaveLength(1)

    await wrapper.setProps({ disabled: true })
    await wrapper.find('form').trigger('submit')
    expect(wrapper.emitted('submit')).toHaveLength(1)
  })

  it('muestra el error asociado y expone focus', async () => {
    const wrapper = mount(InformationRequestForm, {
      props: { modelValue: 'Texto', error: 'Error del servidor.' },
      attachTo: document.body,
    })

    const error = wrapper.find('[role="alert"]')
    expect(error.text()).toBe('Error del servidor.')
    expect(wrapper.find('textarea').attributes('aria-invalid')).toBe('true')
    ;(wrapper.vm as unknown as { focus: () => void }).focus()
    expect(document.activeElement).toBe(wrapper.find('textarea').element)
    wrapper.unmount()
  })
})
