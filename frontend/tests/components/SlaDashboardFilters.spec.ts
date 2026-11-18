import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import SlaDashboardFilters from '@/components/sla-dashboard/SlaDashboardFilters.vue'
import { defaultFilters, makeOptions } from '../fixtures/slaDashboard'

function mountFilters(
  overrides: Partial<{
    filters: typeof defaultFilters
    applying: boolean
  }> = {},
) {
  return mount(SlaDashboardFilters, {
    props: {
      filters: overrides.filters ?? defaultFilters,
      options: makeOptions(),
      applying: overrides.applying ?? false,
    },
  })
}

describe('SlaDashboardFilters', () => {
  it('usa inputs type="date" asociados a etiquetas', () => {
    const wrapper = mountFilters()

    const desde = wrapper.find('#sla-filter-desde')
    const hasta = wrapper.find('#sla-filter-hasta')
    expect(desde.attributes('type')).toBe('date')
    expect(hasta.attributes('type')).toBe('date')
    expect(wrapper.find('label[for="sla-filter-desde"]').exists()).toBe(true)
    expect(wrapper.find('label[for="sla-filter-hasta"]').exists()).toBe(true)
  })

  it('ofrece chips con checkbox para categorías y prioridades', () => {
    const wrapper = mountFilters()

    const categories = wrapper.findAll(
      'input[id^="sla-filter-categoria-"]',
    )
    const priorities = wrapper.findAll(
      'input[id^="sla-filter-prioridad-"]',
    )
    expect(categories).toHaveLength(2)
    expect(priorities).toHaveLength(2)
    expect(categories.every((input) => input.attributes('type') === 'checkbox')).toBe(true)
    expect(wrapper.text()).toContain('Sin categoría')
    expect(wrapper.text()).toContain('Alta')
    expect(wrapper.text()).toContain('(inactiva)')
  })

  it('resume los filtros activos', () => {
    const wrapper = mountFilters()

    const summary = wrapper.find('[data-testid="sla-filters-summary"]')
    expect(summary.text()).toContain('Desde 17/10/2026')
    expect(summary.text()).toContain('hasta 15/11/2026')
  })

  it('bloquea aplicar y muestra un mensaje cuando el rango es inválido', async () => {
    const wrapper = mountFilters({
      filters: { ...defaultFilters, desde: '2026-11-20', hasta: '2026-11-01' },
    })

    const button = wrapper.findAll('button').find((node) => node.text() === 'Aplicar')
    expect(button?.attributes('disabled')).toBeDefined()
    expect(wrapper.find('[role="alert"]').text()).toContain(
      'La fecha inicial no puede ser posterior a la fecha final.',
    )

    await button?.trigger('click')
    expect(wrapper.emitted('apply')).toBeUndefined()
  })

  it('emite "apply" solo con un rango válido', async () => {
    const wrapper = mountFilters()

    const button = wrapper.findAll('button').find((node) => node.text() === 'Aplicar')
    await button?.trigger('click')

    const emitted = wrapper.emitted('apply')
    expect(emitted).toHaveLength(1)
    expect(emitted?.[0]?.[0]).toEqual(defaultFilters)
  })

  it('emite "reset" al restablecer', async () => {
    const wrapper = mountFilters()

    const button = wrapper
      .findAll('button')
      .find((node) => node.text() === 'Restablecer')
    await button?.trigger('click')

    expect(wrapper.emitted('reset')).toHaveLength(1)
  })

  it('emite "change" al marcar una categoría o una prioridad', async () => {
    const wrapper = mountFilters()

    await wrapper.find('#sla-filter-categoria-sin-categoria').setValue(true)
    expect(wrapper.emitted('change')?.[0]?.[0]).toMatchObject({
      categorias: ['sin_categoria'],
    })

    await wrapper.find('#sla-filter-prioridad-2').setValue(true)
    const last = wrapper.emitted('change')?.at(-1)?.[0] as typeof defaultFilters
    expect(last.prioridades).toEqual([2])
  })

  it('emite "change" al cambiar las fechas', async () => {
    const wrapper = mountFilters()

    const hasta = wrapper.find('#sla-filter-hasta')
    await hasta.setValue('2026-11-20')

    const last = wrapper.emitted('change')?.at(-1)?.[0] as typeof defaultFilters
    expect(last.hasta).toBe('2026-11-20')
  })
})
