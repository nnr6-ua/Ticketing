import { mount } from '@vue/test-utils'
import { describe, expect, it, vi } from 'vitest'

import TicketConfirmation from '@/components/TicketConfirmation.vue'
import type { Ticket } from '@/types/api'

function ticket(overrides: Partial<Ticket> = {}): Ticket {
  return {
    id: 't1',
    ticket_number: 'TK-000123',
    title: 'No funciona la VPN desde ayer',
    description: 'No puedo conectar desde ayer por la tarde.',
    status: 'Abierto',
    creator: { id: 'u1', name: 'Solicitante', email: 'usuario@example.com' },
    category: { id: 'c1', name: 'Red' },
    priority: { id: 'p1', name: 'Crítica', level: 1, color: '#dc2626' },
    attachments: [],
    created_at: '2026-01-15T10:00:00Z',
    updated_at: '2026-01-15T10:00:00Z',
    duplicate: false,
    ...overrides,
  }
}

describe('TicketConfirmation', () => {
  it('muestra la referencia, el estado y los datos del ticket', () => {
    const wrapper = mount(TicketConfirmation, { props: { ticket: ticket() } })

    expect(wrapper.text()).toContain('Ticket creado')
    expect(wrapper.text()).toContain('TK-000123')
    expect(wrapper.text()).toContain('Abierto')
    expect(wrapper.text()).toContain('Red')
    expect(wrapper.text()).toContain('Crítica')
    expect(wrapper.text()).toContain('Solicitante')
  })

  it('formatea la fecha de creación en Europe/Madrid', () => {
    const wrapper = mount(TicketConfirmation, { props: { ticket: ticket() } })

    expect(wrapper.text()).toContain('15 de enero de 2026')
    expect(wrapper.text()).toContain('11:00')
  })

  it('distingue un duplicado del alta nueva', () => {
    const wrapper = mount(TicketConfirmation, {
      props: { ticket: ticket({ duplicate: true }) },
    })

    expect(wrapper.text()).toContain('Ticket ya registrado')
    expect(wrapper.text()).toContain('Ya existía un ticket con este mismo contenido')
  })

  it('copia el número de ticket al portapapeles', async () => {
    const writeText = vi.fn().mockResolvedValue(undefined)
    Object.assign(navigator, { clipboard: { writeText } })
    const wrapper = mount(TicketConfirmation, { props: { ticket: ticket() } })

    await wrapper.get('button').trigger('click')

    expect(writeText).toHaveBeenCalledWith('TK-000123')
    expect(wrapper.text()).toContain('Copiado')
  })
})
