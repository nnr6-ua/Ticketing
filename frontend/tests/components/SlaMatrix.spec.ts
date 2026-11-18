import { mount, type VueWrapper } from '@vue/test-utils'
import { describe, expect, it, vi } from 'vitest'

import SlaMatrix from '@/components/admin/SlaMatrix.vue'
import type { SlaMatrixResponse } from '@/types/adminConfiguration'

vi.mock('@headlessui/vue', () => ({
  Dialog: {
    props: ['open'],
    template: '<div v-if="open"><slot /></div>',
  },
  DialogPanel: { template: '<div><slot /></div>' },
  DialogTitle: { template: '<h2><slot /></h2>' },
}))

const matrix: SlaMatrixResponse = {
  configuration_version: {
    id: 'v2',
    version: 2,
    created_at: '2026-11-17T09:00:00Z',
    created_by: null,
  },
  items: [
    {
      id: 'r1',
      category: { id: 'c1', name: 'Red' },
      priority: {
        id: 'p1',
        name: 'Alta',
        level: 2,
        color: '#ea580c',
        base_hours: '8.00',
      },
      hours: '2.00',
      valid_from_version: 2,
      configuration_version_id: 'v2',
      created_at: '2026-11-17T09:00:00Z',
      created_by: { id: 'u1', name: 'Admin', email: 'admin@example.com' },
    },
  ],
  combinations: {
    categories: [{ id: 'c1', name: 'Red' }],
    priorities: [
      {
        id: 'p1',
        name: 'Alta',
        level: 2,
        color: '#ea580c',
        base_hours: '8.00',
      },
    ],
  },
}

function cell(wrapper: VueWrapper) {
  return wrapper.get('button[aria-label="Plazo para Red × Alta"]')
}

async function saveButton(wrapper: VueWrapper) {
  return wrapper.findAll('button').find((button) => button.text() === 'Guardar cambios')!
}

describe('SlaMatrix', () => {
  it('muestra la regla vigente y el plazo base', () => {
    const wrapper = mount(SlaMatrix, { props: { matrix } })
    expect(cell(wrapper).text()).toContain('2 h')
    expect(wrapper.text()).toContain('Base: 8 h')
    expect(wrapper.text()).toContain('Versión v2')
  })

  it('edita una celda en borrador y guarda el lote', async () => {
    const wrapper = mount(SlaMatrix, { props: { matrix } })

    await cell(wrapper).trigger('click')
    await wrapper.get('#sla-cell-hours').setValue('3,5')
    await wrapper.get('form').trigger('submit')

    expect(wrapper.text()).toContain('Cambios sin guardar')
    expect(cell(wrapper).text()).toContain('3,5 h')

    await (await saveButton(wrapper)).trigger('click')
    expect(wrapper.emitted('save')?.at(-1)?.[0]).toEqual([
      {
        operation: 'upsert',
        category_id: 'c1',
        priority_id: 'p1',
        hours: '3.50',
        expected_rule_id: 'r1',
      },
    ])
  })

  it('retira una regla tras confirmación', async () => {
    const wrapper = mount(SlaMatrix, { props: { matrix } })

    await cell(wrapper).trigger('click')
    await wrapper.get('button.border-rose-300').trigger('click')
    await wrapper.get('button.border-rose-300').trigger('click')

    expect(wrapper.text()).toContain('Base: 8 h')
    await (await saveButton(wrapper)).trigger('click')
    expect(wrapper.emitted('save')?.at(-1)?.[0]).toEqual([
      { operation: 'retire', rule_id: 'r1', expected_rule_id: 'r1' },
    ])
  })

  it('muestra el conflicto y solicita recarga', async () => {
    const wrapper = mount(SlaMatrix, {
      props: { matrix, conflict: 'La configuración ha cambiado.' },
    })

    expect(wrapper.get('[role="alert"]').text()).toContain(
      'La configuración ha cambiado.',
    )
    await wrapper.get('[role="alert"] button').trigger('click')
    expect(wrapper.emitted('reload')).toHaveLength(1)
  })
})
