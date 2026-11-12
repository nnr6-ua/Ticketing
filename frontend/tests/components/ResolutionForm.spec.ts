import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import ResolutionForm from '@/components/tickets/ResolutionForm.vue'

describe('ResolutionForm', () => {
  it('muestra la etiqueta, la ayuda y el límite de 5000', () => {
    const wrapper = mount(ResolutionForm, { props: { modelValue: '' } })

    expect(wrapper.find('label').text()).toBe('Descripción de la solución')
    expect(wrapper.text()).toContain(
      'Obligatoria para marcar el ticket como Resuelto.',
    )
    expect(wrapper.text()).toContain('No podrás editarla después')
    const textarea = wrapper.find('textarea')
    expect(textarea.attributes('maxlength')).toBe('5000')
    expect(textarea.attributes('aria-required')).toBe('true')
  })

  it('cuenta los caracteres con trim()', () => {
    const wrapper = mount(ResolutionForm, {
      props: { modelValue: '  hola  ' },
    })

    expect(wrapper.find('#resolution-counter').text()).toBe('4 / 5000')
  })

  it('emite update:modelValue al escribir', async () => {
    const wrapper = mount(ResolutionForm, { props: { modelValue: '' } })

    await wrapper.find('textarea').setValue('Nueva solución')

    expect(wrapper.emitted('update:modelValue')).toEqual([['Nueva solución']])
  })

  it('muestra el error con role alert y aria-invalid', () => {
    const wrapper = mount(ResolutionForm, {
      props: { modelValue: 'texto', error: 'La solución no es válida.' },
    })

    const error = wrapper.find('[role="alert"]')
    expect(error.text()).toBe('La solución no es válida.')
    expect(wrapper.find('textarea').attributes('aria-invalid')).toBe('true')
  })

  it('deshabilita el textarea y admite un límite personalizado', () => {
    const wrapper = mount(ResolutionForm, {
      props: { modelValue: '', disabled: true, maxLength: 10 },
    })

    expect(wrapper.find('textarea').attributes('disabled')).toBeDefined()
    expect(wrapper.find('textarea').attributes('maxlength')).toBe('10')
    expect(wrapper.find('#resolution-counter').text()).toBe('0 / 10')
  })
})
