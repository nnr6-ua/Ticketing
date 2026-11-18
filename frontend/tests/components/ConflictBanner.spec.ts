import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import ConflictBanner from '@/components/admin/ConflictBanner.vue'

describe('ConflictBanner', () => {
  it('expone el conflicto y emite recarga', async () => {
    const wrapper = mount(ConflictBanner, {
      props: { message: 'Otro administrador guardó antes.' },
    })

    const alert = wrapper.get('[role="alert"]')
    expect(alert.text()).toContain('La configuración ha cambiado')
    expect(alert.text()).toContain('Otro administrador guardó antes.')

    await wrapper.get('button').trigger('click')
    expect(wrapper.emitted('reload')).toHaveLength(1)
  })

  it('deshabilita la recarga mientras se ejecuta', () => {
    const wrapper = mount(ConflictBanner, {
      props: { message: 'Conflicto', reloading: true },
    })

    const button = wrapper.get('button')
    expect(button.attributes('disabled')).toBeDefined()
    expect(button.text()).toContain('Recargando')
  })
})
