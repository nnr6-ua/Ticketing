import { mount } from '@vue/test-utils'
import axe from 'axe-core'
import { describe, expect, it } from 'vitest'

import AssigneeChangeReasonForm from '@/components/tickets/AssigneeChangeReasonForm.vue'

describe('AssigneeChangeReasonForm', () => {
  it('muestra la ayuda de visibilidad pública y el contador con trim', () => {
    const wrapper = mount(AssigneeChangeReasonForm, {
      props: { modelValue: '  Motivo  ' },
    })

    expect(wrapper.text()).toContain(
      'Obligatorio. El usuario creador podrá ver este motivo en la línea temporal.',
    )
    expect(wrapper.find('#assignee-change-reason-counter').text()).toBe('6 / 5000')
    expect(
      wrapper.find('#assignee-change-reason').attributes('aria-required'),
    ).toBe('true')
    expect(wrapper.find('#assignee-change-reason').attributes('maxlength')).toBe(
      '5000',
    )
  })

  it('emite el texto escrito sin normalizar', async () => {
    const wrapper = mount(AssigneeChangeReasonForm, {
      props: { modelValue: '' },
    })

    await wrapper.find('#assignee-change-reason').setValue('  Texto  ')
    expect(wrapper.emitted('update:modelValue')).toEqual([['  Texto  ']])
  })

  it('marca aria-invalid y muestra el error accesible', () => {
    const wrapper = mount(AssigneeChangeReasonForm, {
      props: { modelValue: '', error: 'Indica el motivo del cambio de responsable.' },
    })

    const textarea = wrapper.find('#assignee-change-reason')
    expect(textarea.attributes('aria-invalid')).toBe('true')
    const error = wrapper.find('#assignee-change-reason-error')
    expect(error.attributes('role')).toBe('alert')
    expect(error.text()).toBe('Indica el motivo del cambio de responsable.')
    expect(textarea.attributes('aria-describedby')).toContain(
      'assignee-change-reason-error',
    )
  })

  it('expone focus() para enfocar el textarea', () => {
    const wrapper = mount(AssigneeChangeReasonForm, {
      attachTo: document.body,
      props: { modelValue: '' },
    })

    ;(wrapper.vm as unknown as { focus: () => void }).focus()
    expect(document.activeElement).toBe(
      wrapper.find('#assignee-change-reason').element,
    )
    wrapper.unmount()
  })

  it('no tiene violaciones críticas de accesibilidad', async () => {
    document.documentElement.lang = 'es'
    const wrapper = mount(AssigneeChangeReasonForm, {
      attachTo: document.body,
      props: { modelValue: 'Motivo de prueba' },
    })

    const results = await axe.run(wrapper.element, {
      rules: { 'color-contrast': { enabled: false } },
    })
    expect(results.violations.filter((v) => v.impact === 'critical')).toEqual([])
    wrapper.unmount()
  })
})
