import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import ConfigHistoryTable from '@/components/admin/ConfigHistoryTable.vue'
import type { ConfigHistoryResponse } from '@/types/adminConfiguration'

const response: ConfigHistoryResponse = {
  items: [
    {
      id: 'a1',
      configuration_version: {
        id: 'v2',
        version: 2,
        created_at: '2026-11-17T09:00:00Z',
        created_by: null,
      },
      entity_type: 'category',
      entity_id: 'c1',
      action: 'update',
      actor: { id: 'u1', name: 'Ada', email: 'ada@example.com' },
      occurred_at: '2026-11-17T09:00:00Z',
      previous_values: { name: 'Red', description: null },
      new_values: { name: 'Red y VPN', keywords: ['vpn'] },
      summary: 'Categoría actualizada.',
    },
  ],
  pagination: {
    page: 2,
    page_size: 25,
    total_items: 30,
    total_pages: 2,
    has_next: false,
    has_previous: true,
  },
}

describe('ConfigHistoryTable', () => {
  it('muestra autor, acción, valores y fecha en Europe/Madrid', () => {
    const wrapper = mount(ConfigHistoryTable, {
      props: { response, filters: { page: 2, page_size: 25 } },
    })

    expect(wrapper.text()).toContain('Ada')
    expect(wrapper.text()).toContain('Edición')
    expect(wrapper.text()).toContain('Categoría')
    expect(wrapper.text()).toContain('name: Red')
    expect(wrapper.text()).toContain('description: —')
    expect(wrapper.text()).toContain('keywords: vpn')
    expect(wrapper.text()).toContain('v2')
    expect(wrapper.text()).toContain('17 nov 2026')
    expect(wrapper.text()).toContain('10:00')
  })

  it('emite filtros normalizados y reinicia la página', async () => {
    const wrapper = mount(ConfigHistoryTable, {
      props: { response, filters: { page: 2, page_size: 25 } },
    })

    await wrapper.get('#history-from').setValue('2026-11-01')
    expect(wrapper.emitted('update:filters')?.at(-1)?.[0]).toMatchObject({
      from: '2026-11-01',
      page: 1,
    })

    await wrapper.get('#history-to').setValue('2026-11-30')
    expect(wrapper.emitted('update:filters')?.at(-1)?.[0]).toMatchObject({
      to: '2026-11-30',
      page: 1,
    })

    await wrapper.get('#history-entity').setValue('priority')
    expect(wrapper.emitted('update:filters')?.at(-1)?.[0]).toMatchObject({
      entity_type: 'priority',
      page: 1,
    })

    await wrapper.get('#history-action').setValue('rule_retire')
    expect(wrapper.emitted('update:filters')?.at(-1)?.[0]).toMatchObject({
      action: 'rule_retire',
      page: 1,
    })

    await wrapper.get('#history-version').setValue('v2')
    expect(wrapper.emitted('update:filters')?.at(-1)?.[0]).toMatchObject({
      configuration_version_id: 'v2',
      page: 1,
    })
  })

  it('pagina hacia atrás y limita los controles disponibles', async () => {
    const wrapper = mount(ConfigHistoryTable, {
      props: { response, filters: { page: 2, page_size: 25 } },
    })

    const buttons = wrapper.findAll('nav button')
    expect(buttons[0]?.attributes('disabled')).toBeUndefined()
    expect(buttons[1]?.attributes('disabled')).toBeDefined()

    await buttons[0]?.trigger('click')
    expect(wrapper.emitted('update:filters')?.at(-1)?.[0]).toMatchObject({
      page: 1,
    })
  })

  it('muestra el error con reintento', async () => {
    const wrapper = mount(ConfigHistoryTable, {
      props: {
        response: null,
        filters: { page: 1, page_size: 25 },
        error: 'No se pudo cargar.',
      },
    })

    expect(wrapper.get('[role="alert"]').text()).toContain('No se pudo cargar.')
    await wrapper.get('[role="alert"] button').trigger('click')
    expect(wrapper.emitted('retry')).toHaveLength(1)
  })
})
