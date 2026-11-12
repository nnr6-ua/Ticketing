import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import WorkQueueEmptyState from '@/components/work-queue/WorkQueueEmptyState.vue'
import WorkQueueFilters from '@/components/work-queue/WorkQueueFilters.vue'
import { DEFAULT_STATUSES } from '@/stores/workQueue'
import type {
  PriorityFilterOption,
  StatusFilterOption,
  TicketStatus,
} from '@/types/workQueue'

const statusOptions: StatusFilterOption[] = [
  { value: 'abierto', label: 'Abierto', is_final: false },
  { value: 'en_progreso', label: 'En progreso', is_final: false },
  { value: 'pendiente_usuario', label: 'Pendiente de usuario', is_final: false },
  { value: 'resuelto', label: 'Resuelto', is_final: true },
  { value: 'cerrado', label: 'Cerrado', is_final: true },
]

const priorityOptions: PriorityFilterOption[] = [
  { id: 'p1', name: 'Crítica', level: 1, color: '#dc2626', is_active: true },
  { id: 'p2', name: 'Alta', level: 2, color: '#ea580c', is_active: true },
]

function mountFilters(options: {
  selectedStatuses?: TicketStatus[]
  selectedPriorities?: number[]
  resultCount?: number
  disabled?: boolean
} = {}) {
  return mount(WorkQueueFilters, {
    props: {
      statusOptions,
      priorityOptions,
      selectedStatuses: options.selectedStatuses ?? [...DEFAULT_STATUSES],
      selectedPriorities: options.selectedPriorities ?? [],
      resultCount: options.resultCount ?? 3,
      disabled: options.disabled ?? false,
    },
  })
}

describe('WorkQueueFilters', () => {
  it('usa dos fieldset con legend y etiquetas en español', () => {
    const wrapper = mountFilters()

    const fieldsets = wrapper.findAll('fieldset')
    expect(fieldsets).toHaveLength(2)
    expect(fieldsets[0].find('legend').text()).toBe('Estado')
    expect(fieldsets[1].find('legend').text()).toBe('Prioridad')
    expect(wrapper.text()).toContain('Abierto')
    expect(wrapper.text()).toContain('En progreso')
    expect(wrapper.text()).toContain('Pendiente de usuario')
    expect(wrapper.text()).toContain('Resuelto')
    expect(wrapper.text()).toContain('Cerrado')
    expect(wrapper.text()).toContain('Crítica')
    expect(wrapper.text()).toContain('Alta')
  })

  it('marca los estados seleccionados y emite la selección de un chip', async () => {
    const wrapper = mountFilters()
    const abierto = wrapper.find('#filtro-estado-abierto')
    const resuelto = wrapper.find('#filtro-estado-resuelto')

    expect((abierto.element as HTMLInputElement).checked).toBe(true)
    expect((resuelto.element as HTMLInputElement).checked).toBe(false)

    await resuelto.setValue(true)

    const emitted = wrapper.emitted('update:statuses')
    expect(emitted).toHaveLength(1)
    expect(emitted?.[0][0]).toEqual([...DEFAULT_STATUSES, 'resuelto'])
  })

  it('emite la deselección de un estado', async () => {
    const wrapper = mountFilters()
    const abierto = wrapper.find('#filtro-estado-abierto')

    await abierto.setValue(false)

    const emitted = wrapper.emitted('update:statuses')
    expect(emitted?.[0][0]).toEqual(['en_progreso', 'pendiente_usuario'])
  })

  it('marca las prioridades inactivas y las mantiene filtrables', async () => {
    const wrapper = mount(WorkQueueFilters, {
      props: {
        statusOptions,
        priorityOptions: [
          ...priorityOptions,
          {
            id: 'p4',
            name: 'Baja',
            level: 4,
            color: '#64748b',
            is_active: false,
          },
        ],
        selectedStatuses: [...DEFAULT_STATUSES],
        selectedPriorities: [],
        resultCount: 3,
        disabled: false,
      },
    })

    const chip = wrapper.find('label[for="filtro-prioridad-4"]')
    expect(chip.text()).toContain('Baja')
    expect(chip.text()).toContain('(inactiva)')
    expect(wrapper.find('label[for="filtro-prioridad-1"]').text()).not.toContain(
      '(inactiva)',
    )

    await wrapper.find('#filtro-prioridad-4').setValue(true)
    expect(wrapper.emitted('update:priorities')?.[0][0]).toEqual([4])
  })

  it('emite la selección y deselección de una prioridad', async () => {
    const wrapper = mountFilters({ selectedPriorities: [1] })

    await wrapper.find('#filtro-prioridad-2').setValue(true)
    expect(wrapper.emitted('update:priorities')?.[0][0]).toEqual([1, 2])

    await wrapper.find('#filtro-prioridad-1').setValue(false)
    expect(wrapper.emitted('update:priorities')?.[1][0]).toEqual([])
  })

  it('muestra el número de resultados y lo actualiza', async () => {
    const wrapper = mountFilters({ resultCount: 3 })
    expect(wrapper.find('[data-testid="result-count"]').text()).toBe('3 tickets')

    await wrapper.setProps({ resultCount: 1 })
    expect(wrapper.find('[data-testid="result-count"]').text()).toBe('1 ticket')

    await wrapper.setProps({ resultCount: 0 })
    expect(wrapper.find('[data-testid="result-count"]').text()).toBe('0 tickets')
  })

  it('emite "clear" al pulsar Limpiar filtros', async () => {
    const wrapper = mountFilters()
    const button = wrapper
      .findAll('button')
      .find((candidate) => candidate.text() === 'Limpiar filtros')

    expect(button).toBeDefined()
    await button?.trigger('click')

    expect(wrapper.emitted('clear')).toHaveLength(1)
  })

  it('deshabilita los controles durante la carga', () => {
    const wrapper = mountFilters({ disabled: true })

    expect(wrapper.findAll('fieldset').every((fieldset) => fieldset.attributes('disabled') !== undefined)).toBe(true)
    expect(
      wrapper
        .findAll('button')
        .find((candidate) => candidate.text() === 'Limpiar filtros')
        ?.attributes('disabled'),
    ).not.toBeUndefined()
  })

  it('asocia cada etiqueta a su checkbox y permite foco por teclado', () => {
    const wrapper = mountFilters()

    for (const option of statusOptions) {
      const label = wrapper.find(`label[for="filtro-estado-${option.value}"]`)
      const input = wrapper.find(`#filtro-estado-${option.value}`)
      expect(label.exists()).toBe(true)
      expect(input.element.tagName).toBe('INPUT')
      expect(input.attributes('type')).toBe('checkbox')
      expect(input.attributes('tabindex')).toBeUndefined()
    }
  })

  it('no ofrece "Limpiar filtros" en el vacío sin asignaciones', () => {
    const wrapper = mount(WorkQueueEmptyState, {
      props: { variant: 'no_assignments' },
    })

    expect(wrapper.text()).toContain('No tienes tickets asignados actualmente')
    expect(wrapper.find('button').exists()).toBe(false)
  })

  it('muestra el estado no_results con acción para limpiar filtros', async () => {
    const wrapper = mount(WorkQueueEmptyState, {
      props: { variant: 'no_results' },
    })

    expect(wrapper.text()).toContain(
      'No hay resultados para los filtros seleccionados',
    )
    const button = wrapper.find('button')
    expect(button.text()).toBe('Limpiar filtros')

    await button.trigger('click')
    expect(wrapper.emitted('clear')).toHaveLength(1)
  })
})
