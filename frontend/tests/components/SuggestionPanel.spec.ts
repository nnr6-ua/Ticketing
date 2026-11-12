import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import SuggestionPanel from '@/components/SuggestionPanel.vue'
import type { Priority, SuggestionResponse } from '@/types/api'

const priorities: Priority[] = [
  { id: 'p1', name: 'Crítica', level: 1, color: '#dc2626' },
  { id: 'p2', name: 'Media', level: 3, color: '#ca8a04' },
]

const suggestion: SuggestionResponse = {
  category: { id: 'c1', name: 'Red' },
  priority: priorities[0],
  category_is_fallback: false,
  priority_is_fallback: false,
}

function mountPanel(overrides: Record<string, unknown> = {}) {
  return mount(SuggestionPanel, {
    attachTo: document.body,
    props: {
      suggestion,
      loading: false,
      error: null,
      priorities,
      priorityId: 'p1',
      ...overrides,
    },
  })
}

describe('SuggestionPanel y PrioritySelect', () => {
  it('muestra la categoría sugerida y la prioridad seleccionada', () => {
    const wrapper = mountPanel()

    expect(wrapper.text()).toContain('Red')
    expect(wrapper.get('[aria-label="Prioridad del ticket"]').text()).toContain(
      'Crítica',
    )
    wrapper.unmount()
  })

  it('permite elegir otra prioridad y emite el id', async () => {
    const wrapper = mountPanel()

    await wrapper.get('[aria-label="Prioridad del ticket"]').trigger('click')
    const options = wrapper.findAll('[role="option"]')
    expect(options.map((option) => option.text())).toEqual(['Crítica', 'Media'])
    await options[1].trigger('click')

    expect(wrapper.emitted('update:priority-id')?.[0]).toEqual(['p2'])
    wrapper.unmount()
  })

  it('avisa cuando categoría o prioridad usan el valor por defecto', () => {
    const wrapper = mountPanel({
      suggestion: {
        ...suggestion,
        category_is_fallback: true,
        priority_is_fallback: true,
      },
    })

    expect(wrapper.text()).toContain('Se usará la categoría por defecto.')
    expect(wrapper.text()).toContain('Prioridad por defecto; puedes cambiarla.')
    wrapper.unmount()
  })

  it('muestra el error de sugerencia sin ocultar el selector', () => {
    const wrapper = mountPanel({ error: 'No se pudo calcular la sugerencia.' })

    expect(wrapper.text()).toContain('No se pudo calcular la sugerencia.')
    expect(wrapper.get('[aria-label="Prioridad del ticket"]')).toBeTruthy()
    wrapper.unmount()
  })
})
