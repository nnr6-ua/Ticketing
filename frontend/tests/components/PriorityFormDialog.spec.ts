import { mount } from '@vue/test-utils'
import { describe, expect, it, vi } from 'vitest'

import PriorityFormDialog from '@/components/admin/PriorityFormDialog.vue'
import type { PriorityAdmin } from '@/types/adminConfiguration'

vi.mock('@headlessui/vue', () => ({
  Dialog: {
    props: ['open'],
    template: '<div v-if="open"><slot /></div>',
  },
  DialogPanel: { template: '<div><slot /></div>' },
  DialogTitle: { template: '<h2><slot /></h2>' },
}))

const priority: PriorityAdmin = {
  id: 'p1',
  name: 'Media',
  level: 3,
  color: '#64748b',
  base_hours: '24.00',
  keywords: ['general'],
  is_active: true,
  is_default: true,
  is_system: false,
  sort_order: 10,
  revision: 2,
  ticket_count: 4,
  rule_count: 1,
  can_delete: false,
}

describe('PriorityFormDialog', () => {
  it('normaliza el plazo base y envía un alta', async () => {
    const wrapper = mount(PriorityFormDialog, {
      props: { open: true, priority: null, defaultCandidates: [] },
    })

    await wrapper.get('#priority-name').setValue('  Planificada  ')
    await wrapper.get('#priority-level').setValue('4')
    await wrapper.get('#priority-hours').setValue('7,5')
    await wrapper.get('#priority-keywords').setValue('planificado, PLANIFICADO')
    await wrapper.get('form').trigger('submit')

    expect(wrapper.emitted('submit')?.at(-1)?.[0]).toMatchObject({
      name: 'Planificada',
      level: 4,
      base_hours: '7.50',
      keywords: ['planificado'],
      is_default: false,
    })
  })

  it('rechaza plazos no positivos', async () => {
    const wrapper = mount(PriorityFormDialog, {
      props: { open: true, priority: null, defaultCandidates: [] },
    })

    await wrapper.get('#priority-name').setValue('Media')
    await wrapper.get('#priority-hours').setValue('0')
    await wrapper.get('form').trigger('submit')

    expect(wrapper.text()).toContain('El plazo base debe ser un número positivo')
    expect(wrapper.get('#priority-hours').attributes('aria-invalid')).toBe('true')
    expect(wrapper.emitted('submit')).toBeUndefined()
  })

  it('exige reemplazo al desactivar la prioridad predeterminada', async () => {
    const replacement = { ...priority, id: 'p2', name: 'Alta', is_default: false }
    const wrapper = mount(PriorityFormDialog, {
      props: {
        open: true,
        priority,
        defaultCandidates: [priority, replacement],
      },
    })

    await wrapper.findAll('input[type="checkbox"]')[0]?.setValue(false)
    await wrapper.get('form').trigger('submit')

    expect(wrapper.text()).toContain('Selecciona otra prioridad predeterminada')
    expect(wrapper.get('#priority-replacement').attributes('aria-invalid')).toBe(
      'true',
    )

    await wrapper.get('#priority-replacement').setValue('p2')
    await wrapper.get('form').trigger('submit')

    expect(wrapper.emitted('submit')?.at(-1)?.[0]).toMatchObject({
      expected_revision: 2,
      is_active: false,
      replacement_default_id: 'p2',
    })
  })

  it('mantiene el diálogo con conflicto y envía expected_revision', async () => {
    const wrapper = mount(PriorityFormDialog, {
      props: {
        open: true,
        priority,
        conflict: 'La configuración ha cambiado.',
      },
    })

    expect(wrapper.get('[role="alert"]').text()).toContain(
      'La configuración ha cambiado.',
    )
    await wrapper.get('[role="alert"] button').trigger('click')
    expect(wrapper.emitted('reload')).toHaveLength(1)

    await wrapper.get('#priority-hours').setValue('12')
    await wrapper.get('form').trigger('submit')
    expect(wrapper.emitted('submit')?.at(-1)?.[0]).toMatchObject({
      expected_revision: 2,
      base_hours: '12.00',
    })
  })

  it('muestra los errores de campo del backend y los limpia al reabrir', async () => {
    const wrapper = mount(PriorityFormDialog, {
      props: { open: true, priority: null, defaultCandidates: [] },
    })

    await wrapper.setProps({
      serverError: {
        code: 'duplicate_priority_level',
        message: 'Ya existe una prioridad con ese nivel.',
      },
    })

    expect(wrapper.get('#priority-level-error').text()).toContain('Ya existe')
    expect(wrapper.get('#priority-level').attributes('aria-describedby')).toBe(
      'priority-level-error',
    )

    await wrapper.setProps({
      serverError: {
        code: 'duplicate_catalog_name',
        message: 'Ya existe una prioridad con ese nombre.',
      },
    })

    expect(wrapper.get('#priority-name-error').text()).toContain('nombre')
    expect(wrapper.get('#priority-name').attributes('aria-describedby')).toBe(
      'priority-name-error',
    )

    await wrapper.setProps({ open: false })
    await wrapper.setProps({ open: true, serverError: null })

    expect(wrapper.find('#priority-name-error').exists()).toBe(false)
    expect(wrapper.find('#priority-level-error').exists()).toBe(false)
  })

  it('etiqueta el campo hexadecimal del color', () => {
    const wrapper = mount(PriorityFormDialog, {
      props: { open: true, priority: null, defaultCandidates: [] },
    })

    expect(wrapper.get('#priority-color-hex').attributes('aria-label')).toBe(
      'Color hexadecimal',
    )
  })
})
