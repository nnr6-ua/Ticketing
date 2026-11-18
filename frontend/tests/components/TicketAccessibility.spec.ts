import { flushPromises, mount, type VueWrapper } from '@vue/test-utils'
import axe from 'axe-core'
import { afterEach, beforeAll, describe, expect, it, vi } from 'vitest'

const { getPriorities, getSuggestion } = vi.hoisted(() => ({
  getPriorities: vi.fn(),
  getSuggestion: vi.fn(),
}))

vi.mock('@/services/api', async (importOriginal) => {
  const original = await importOriginal<typeof import('@/services/api')>()
  return { ...original, getPriorities, getSuggestion }
})

import AttachmentField from '@/components/AttachmentField.vue'
import SuggestionPanel from '@/components/SuggestionPanel.vue'
import TicketForm from '@/components/TicketForm.vue'
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

const mounted: VueWrapper[] = []

function attach(wrapper: VueWrapper): VueWrapper {
  mounted.push(wrapper)
  return wrapper
}

async function criticalViolations(wrapper: VueWrapper) {
  const results = await axe.run(wrapper.element)
  return results.violations
}

beforeAll(() => {
  URL.createObjectURL = vi.fn(() => 'blob:preview')
  URL.revokeObjectURL = vi.fn()
})

afterEach(() => {
  while (mounted.length > 0) {
    mounted.pop()?.unmount()
  }
})

describe('Accesibilidad del flujo de creación (axe-core)', () => {
  it('la sugerencia expone el selector de prioridad con nombre accesible', async () => {
    document.documentElement.lang = 'es'
    const wrapper = attach(
      mount(SuggestionPanel, {
        attachTo: document.body,
        props: {
          suggestion,
          loading: false,
          error: null,
          priorities,
          priorityId: 'p1',
        },
      }),
    )

    expect(wrapper.get('[aria-label="Prioridad del ticket"]')).toBeTruthy()
    expect(await criticalViolations(wrapper)).toEqual([])
  })

  it('los adjuntos asocian etiqueta, ayuda y miniaturas', async () => {
    document.documentElement.lang = 'es'
    const file = new File([new Uint8Array([1, 2, 3])], 'captura.png', {
      type: 'image/png',
    })
    const wrapper = attach(
      mount(AttachmentField, {
        attachTo: document.body,
        props: { modelValue: [file] },
      }),
    )

    const input = wrapper.get('input[type="file"]')
    expect(input.attributes('id')).toBe('ticket-attachments')
    expect(wrapper.get('label[for="ticket-attachments"]').text()).toContain('Adjuntos')
    expect(wrapper.get('img').attributes('alt')).toBe('Vista previa de captura.png')
    expect(await criticalViolations(wrapper)).toEqual([])
  })

  it('el flujo completo supera axe con contraste AA', async () => {
    document.documentElement.lang = 'es'
    getPriorities.mockResolvedValue(priorities)
    getSuggestion.mockResolvedValue(suggestion)
    const wrapper = attach(
      mount(TicketForm, { attachTo: document.body }),
    )
    await flushPromises()

    expect(await criticalViolations(wrapper)).toEqual([])
  })
})
