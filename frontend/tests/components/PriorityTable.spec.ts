import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import PriorityTable from '@/components/admin/PriorityTable.vue'
import type { PriorityAdmin } from '@/types/adminConfiguration'

const priority: PriorityAdmin = {
  id: 'p1',
  name: 'Alta',
  level: 2,
  color: '#ea580c',
  base_hours: '7.25',
  keywords: [],
  is_active: true,
  is_default: true,
  is_system: false,
  sort_order: 10,
  revision: 1,
  ticket_count: 0,
  rule_count: 0,
  can_delete: false,
}

describe('PriorityTable', () => {
  it('muestra el plazo base con dos decimales es-ES', () => {
    const wrapper = mount(PriorityTable, { props: { items: [priority] } })

    expect(wrapper.text()).toContain('7,25 h')
  })

  it('muestra un esqueleto de carga cuando loading es verdadero', () => {
    const wrapper = mount(PriorityTable, { props: { items: [], loading: true } })

    expect(wrapper.find('.animate-pulse').exists()).toBe(true)
    expect(wrapper.text()).not.toContain('Todavía no hay prioridades configuradas.')
  })
})
