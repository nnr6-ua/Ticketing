import { mount } from '@vue/test-utils'
import { describe, expect, it, vi } from 'vitest'

import CategoryFormDialog from '@/components/admin/CategoryFormDialog.vue'
import type { CategoryAdmin } from '@/types/adminConfiguration'

vi.mock('@headlessui/vue', () => ({
  Dialog: {
    props: ['open'],
    template: '<div v-if="open"><slot /></div>',
  },
  DialogPanel: { template: '<div><slot /></div>' },
  DialogTitle: { template: '<h2><slot /></h2>' },
}))

const category: CategoryAdmin = {
  id: 'c1',
  name: 'Red',
  description: 'Conectividad',
  keywords: ['vpn'],
  is_active: true,
  is_default: true,
  is_system: false,
  sort_order: 10,
  revision: 3,
  ticket_count: 2,
  rule_count: 1,
  can_delete: false,
}

describe('CategoryFormDialog', () => {
  it('valida el nombre y envía un alta normalizada', async () => {
    const wrapper = mount(CategoryFormDialog, {
      props: { open: true, category: null, defaultCandidates: [] },
    })

    await wrapper.get('form').trigger('submit')
    expect(wrapper.text()).toContain('El nombre es obligatorio.')
    expect(wrapper.get('#category-name').attributes('aria-invalid')).toBe('true')

    await wrapper.get('#category-name').setValue('  Hardware  ')
    await wrapper.get('#category-description').setValue('Equipos')
    await wrapper.get('#category-keywords').setValue('equipo, EQUIPO, monitor')
    await wrapper.get('form').trigger('submit')

    expect(wrapper.emitted('submit')?.at(-1)?.[0]).toEqual({
      name: 'Hardware',
      description: 'Equipos',
      keywords: ['equipo', 'monitor'],
      sort_order: 0,
      is_default: false,
    })
  })

  it('muestra las palabras clave introducidas como chips', async () => {
    const wrapper = mount(CategoryFormDialog, {
      props: { open: true, category: null, defaultCandidates: [] },
    })

    await wrapper.get('#category-keywords').setValue('equipo, monitor, equipo')

    const chips = wrapper.findAll(
      '[aria-label="Palabras clave introducidas"] span',
    )
    expect(chips.map((chip) => chip.text())).toEqual(['equipo', 'monitor'])
  })

  it('envía expected_revision al editar y exige reemplazo del default', async () => {
    const replacement = {
      ...category,
      id: 'c2',
      name: 'Hardware',
      is_default: false,
    }
    const wrapper = mount(CategoryFormDialog, {
      props: {
        open: true,
        category,
        defaultCandidates: [category, replacement],
      },
    })

    const checkboxes = wrapper.findAll('input[type="checkbox"]')
    await checkboxes[0]?.setValue(false)
    await wrapper.get('form').trigger('submit')
    expect(wrapper.text()).toContain('Selecciona otra categoría predeterminada')

    await wrapper.get('#category-replacement').setValue('c2')
    await wrapper.get('form').trigger('submit')

    const payload = wrapper.emitted('submit')?.at(-1)?.[0]
    expect(payload).toMatchObject({
      expected_revision: 3,
      is_active: false,
      replacement_default_id: 'c2',
    })
  })

  it('muestra duplicate_catalog_name bajo el campo y lo limpia al reabrir', async () => {
    const wrapper = mount(CategoryFormDialog, {
      props: { open: true, category: null, defaultCandidates: [] },
    })

    await wrapper.setProps({
      serverError: {
        code: 'duplicate_catalog_name',
        message: 'Ya existe una categoría con ese nombre.',
      },
    })

    expect(wrapper.get('#category-name-error').text()).toContain('Ya existe')
    expect(wrapper.get('#category-name').attributes('aria-describedby')).toBe(
      'category-name-error',
    )
    expect(wrapper.get('#category-name').attributes('aria-invalid')).toBe('true')

    await wrapper.setProps({ open: false })
    await wrapper.setProps({ open: true, serverError: null })

    expect(wrapper.find('#category-name-error').exists()).toBe(false)
  })

  it('muestra el conflicto y emite la recarga sin cerrar el diálogo', async () => {
    const wrapper = mount(CategoryFormDialog, {
      props: {
        open: true,
        category,
        conflict: 'La configuración ha cambiado.',
      },
    })

    expect(wrapper.get('[role="alert"]').text()).toContain(
      'La configuración ha cambiado.',
    )
    await wrapper.get('[role="alert"] button').trigger('click')
    expect(wrapper.emitted('reload')).toHaveLength(1)
    expect(wrapper.emitted('update:open')).toBeUndefined()
  })
})
