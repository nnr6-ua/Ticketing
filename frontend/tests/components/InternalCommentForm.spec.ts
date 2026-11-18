import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import InternalCommentForm from '@/components/tickets/InternalCommentForm.vue'

function submitButton(wrapper: ReturnType<typeof mount>) {
  return wrapper.find('button[type="submit"]')
}

describe('InternalCommentForm', () => {
  it('muestra etiqueta, ayuda de visibilidad y contador', () => {
    const wrapper = mount(InternalCommentForm, { props: { modelValue: '' } })

    expect(wrapper.find('label').text()).toBe('Comentario interno')
    expect(wrapper.text()).toContain(
      'Solo visible para el técnico asignado, supervisores y administradores.',
    )
    expect(wrapper.find('#internal-comment-counter').text()).toBe('0 / 5000')
    expect(wrapper.find('textarea').attributes('maxlength')).toBe('5000')
  })

  it('emite update:modelValue al escribir', async () => {
    const wrapper = mount(InternalCommentForm, { props: { modelValue: '' } })

    await wrapper.find('textarea').setValue('Nota interna')

    expect(wrapper.emitted('update:modelValue')).toEqual([['Nota interna']])
  })

  it('deshabilita el botón con texto vacío o solo espacios', async () => {
    const wrapper = mount(InternalCommentForm, { props: { modelValue: '' } })
    expect(submitButton(wrapper).attributes('disabled')).toBeDefined()

    await wrapper.setProps({ modelValue: '   ' })
    expect(submitButton(wrapper).attributes('disabled')).toBeDefined()

    await wrapper.setProps({ modelValue: 'Nota' })
    expect(submitButton(wrapper).attributes('disabled')).toBeUndefined()
  })

  it('deshabilita el botón por encima de 5000 caracteres', () => {
    const wrapper = mount(InternalCommentForm, {
      props: { modelValue: 'a'.repeat(5001) },
    })

    expect(submitButton(wrapper).attributes('disabled')).toBeDefined()
    expect(wrapper.find('#internal-comment-counter').classes()).toContain(
      'text-red-700',
    )
  })

  it('emite submit solo con texto válido', async () => {
    const wrapper = mount(InternalCommentForm, { props: { modelValue: '' } })

    await wrapper.find('form').trigger('submit')
    expect(wrapper.emitted('submit')).toBeUndefined()

    await wrapper.setProps({ modelValue: 'Nota válida' })
    await wrapper.find('form').trigger('submit')
    expect(wrapper.emitted('submit')).toHaveLength(1)
  })

  it('deshabilita el envío mientras disabled es true y muestra el error', () => {
    const wrapper = mount(InternalCommentForm, {
      props: { modelValue: 'Nota', disabled: true, error: 'Error del servidor.' },
    })

    expect(submitButton(wrapper).attributes('disabled')).toBeDefined()
    expect(wrapper.find('[role="alert"]').text()).toBe('Error del servidor.')
  })
})
