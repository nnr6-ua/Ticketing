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
    expect(wrapper.emitted('submit')).toBeUndefined()
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
})
