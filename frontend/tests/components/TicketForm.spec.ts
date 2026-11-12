import { flushPromises, mount } from '@vue/test-utils'
import { defineComponent, h } from 'vue'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const { createTicket, getPriorities, getSuggestion } = vi.hoisted(() => ({
  createTicket: vi.fn(),
  getPriorities: vi.fn(),
  getSuggestion: vi.fn(),
}))

vi.mock('@/services/api', async (importOriginal) => {
  const original = await importOriginal<typeof import('@/services/api')>()
  return {
    ...original,
    createTicket,
    getPriorities,
    getSuggestion,
  }
})

import { useTicketForm } from '@/composables/useTicketForm'
import { ApiError } from '@/services/api'
import type { Priority, SuggestionResponse, Ticket } from '@/types/api'

const media: Priority = { id: 'p3', name: 'Media', level: 3, color: '#ca8a04' }
const suggestion: SuggestionResponse = {
  category: { id: 'c1', name: 'Red' },
  priority: media,
  category_is_fallback: false,
  priority_is_fallback: false,
}

const ticket: Ticket = {
  id: 't1',
  ticket_number: 'TK-000123',
  title: 'No funciona la VPN desde ayer',
  description: 'No puedo conectar desde ayer por la tarde.',
  status: 'Abierto',
  creator: { id: 'u1', name: 'Solicitante', email: 'usuario@example.com' },
  category: suggestion.category,
  priority: media,
  attachments: [],
  created_at: '2026-01-15T10:00:00Z',
  updated_at: '2026-01-15T10:00:00Z',
  duplicate: false,
}

const Harness = defineComponent({
  setup() {
    return { form: useTicketForm() }
  },
  render() {
    return h('div')
  },
})

function mountForm() {
  const wrapper = mount(Harness)
  return { wrapper, form: wrapper.vm.form }
}

beforeEach(() => {
  getPriorities.mockResolvedValue([media])
  getSuggestion.mockResolvedValue(suggestion)
  createTicket.mockReset()
})

describe('useTicketForm · validación y preservación de datos', () => {
  it('bloquea el envío si el título o la descripción no son válidos', async () => {
    const { form } = mountForm()
    await flushPromises()

    form.title.value = 'abc'
    form.description.value = 'corta'
    const result = await form.submit()

    expect(result).toBeNull()
    expect(createTicket).not.toHaveBeenCalled()
    expect(form.titleError.value).toContain('al menos 5')
    expect(form.descriptionError.value).toContain('al menos 20')
    expect(form.showValidation.value).toBe(true)
  })

  it('conserva título, descripción y adjuntos si el servidor falla', async () => {
    const { form } = mountForm()
    await flushPromises()
    const file = new File(['contenido'], 'captura.png', { type: 'image/png' })

    form.title.value = 'No funciona la VPN desde ayer'
    form.description.value = 'No puedo conectar desde ayer por la tarde.'
    form.attachments.value = [file]
    createTicket.mockRejectedValue(
      new ApiError(500, {
        detail: { code: 'internal_error', message: 'Fallo temporal del servidor.' },
      }),
    )

    const result = await form.submit()

    expect(result).toBeNull()
    expect(form.errorMessage.value).toBe('Fallo temporal del servidor.')
    expect(form.title.value).toBe('No funciona la VPN desde ayer')
    expect(form.description.value).toBe(
      'No puedo conectar desde ayer por la tarde.',
    )
    expect(form.attachments.value).toEqual([file])
    expect(form.submitting.value).toBe(false)
  })

  it('envía los datos recortados y devuelve el ticket creado', async () => {
    const { form } = mountForm()
    await flushPromises()
    const file = new File(['contenido'], 'captura.png', { type: 'image/png' })
    form.title.value = '  No funciona la VPN desde ayer  '
    form.description.value = '  No puedo conectar desde ayer por la tarde.  '
    form.attachments.value = [file]
    form.setPriority('p3')
    createTicket.mockResolvedValue(ticket)

    const result = await form.submit()

    expect(result).toEqual(ticket)
    expect(createTicket).toHaveBeenCalledWith({
      title: 'No funciona la VPN desde ayer',
      description: 'No puedo conectar desde ayer por la tarde.',
      priorityId: 'p3',
      attachments: [file],
    })
  })
})
