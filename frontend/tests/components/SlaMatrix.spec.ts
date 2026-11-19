import { mount, type VueWrapper } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import SlaMatrix from '@/components/admin/SlaMatrix.vue'
import type { SlaMatrixResponse } from '@/types/adminConfiguration'

const { onBeforeRouteLeave } = vi.hoisted(() => ({
  onBeforeRouteLeave: vi.fn(),
}))

vi.mock('vue-router', () => ({ onBeforeRouteLeave }))

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
      category: { id: 'c1', name: 'Red', is_active: true },
      priority: {
        id: 'p1',
        name: 'Alta',
        level: 2,
        color: '#ea580c',
        base_hours: '8.00',
        is_active: true,
      },
      hours: '2.00',
      valid_from_version: 2,
      configuration_version_id: 'v2',
      created_at: '2026-11-17T09:00:00Z',
      created_by: { id: 'u1', name: 'Admin', email: 'admin@example.com' },
    },
  ],
  combinations: {
    categories: [{ id: 'c1', name: 'Red', is_active: true }],
    priorities: [
      {
        id: 'p1',
        name: 'Alta',
        level: 2,
        color: '#ea580c',
        base_hours: '8.00',
        is_active: true,
      },
    ],
  },
}

function cell(wrapper: VueWrapper) {
  return wrapper.get('button[aria-label="Plazo para Red y Alta"]')
}

async function saveButton(wrapper: VueWrapper) {
  return wrapper.findAll('button').find((button) => button.text() === 'Guardar cambios')!
}

describe('SlaMatrix', () => {
  beforeEach(() => {
    onBeforeRouteLeave.mockClear()
  })

  it('muestra la regla vigente y el plazo base', () => {
    const wrapper = mount(SlaMatrix, { props: { matrix } })
    expect(cell(wrapper).text()).toContain('2,00 h')
    expect(wrapper.text()).toContain('Base: 8,00 h')
    expect(wrapper.text()).toContain('Versión v2')
  })

  it('muestra los plazos con dos decimales es-ES', () => {
    const preciseMatrix: SlaMatrixResponse = {
      ...matrix,
      items: [{ ...matrix.items[0]!, hours: '8.05' }],
      combinations: {
        ...matrix.combinations,
        priorities: [{ ...matrix.combinations.priorities[0]!, base_hours: '7.25' }],
      },
    }
    const wrapper = mount(SlaMatrix, { props: { matrix: preciseMatrix } })

    expect(cell(wrapper).text()).toContain('8,05 h')
    expect(wrapper.text()).toContain('Base: 7,25 h')
  })

  it('muestra el punto de color de la prioridad en la celda con regla', () => {
    const wrapper = mount(SlaMatrix, { props: { matrix } })
    const dot = cell(wrapper).get('span[aria-hidden="true"]')

    expect(dot.attributes('style')).toMatch(/ea580c|rgb\(234, 88, 12\)/)
  })

  it('marca la celda con el error de catálogo inactivo y conserva el borrador', async () => {
    const message = 'La categoría o la prioridad no está activa.'
    const wrapper = mount(SlaMatrix, { props: { matrix } })

    await cell(wrapper).trigger('click')
    await wrapper.get('#sla-cell-hours').setValue('3,50')
    await wrapper.get('form').trigger('submit')

    await wrapper.setProps({ cellErrors: { 'c1:p1': message } })

    expect(cell(wrapper).classes()).toContain('border-rose-400')
    expect(wrapper.get('#cell-error-c1-p1').text()).toContain('no está activa')
    expect(cell(wrapper).attributes('aria-describedby')).toContain(
      'cell-error-c1-p1',
    )
    expect(cell(wrapper).text()).toContain('3,50 h')
  })

  it('edita una celda en borrador y guarda el lote', async () => {
    const wrapper = mount(SlaMatrix, { props: { matrix } })

    await cell(wrapper).trigger('click')
    await wrapper.get('#sla-cell-hours').setValue('3,5')
    await wrapper.get('form').trigger('submit')

    expect(wrapper.text()).toContain('Cambios sin guardar')
    expect(cell(wrapper).text()).toContain('3,50 h')

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

    expect(wrapper.text()).toContain('Base: 8,00 h')
    await (await saveButton(wrapper)).trigger('click')
    expect(wrapper.emitted('save')?.at(-1)?.[0]).toEqual([
      { operation: 'retire', rule_id: 'r1', expected_rule_id: 'r1' },
    ])
  })

  it('marca como inválido un plazo de celda rechazado', async () => {
    const wrapper = mount(SlaMatrix, { props: { matrix } })

    await cell(wrapper).trigger('click')
    await wrapper.get('#sla-cell-hours').setValue('0')
    await wrapper.get('form').trigger('submit')

    expect(wrapper.get('#sla-cell-hours').attributes('aria-invalid')).toBe('true')
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

  it('deshabilita y estiliza las celdas inactivas', () => {
    const inactiveMatrix: SlaMatrixResponse = {
      ...matrix,
      combinations: {
        categories: [{ ...matrix.combinations.categories[0]!, is_active: false }],
        priorities: [{ ...matrix.combinations.priorities[0]!, is_active: false }],
      },
    }
    const wrapper = mount(SlaMatrix, { props: { matrix: inactiveMatrix } })
    const inactiveCell = cell(wrapper)

    expect(inactiveCell.attributes('disabled')).toBeDefined()
    expect(inactiveCell.classes()).toContain('bg-slate-50')
    expect(wrapper.text()).toContain('Categoría y prioridad inactivas')
  })

  it('permite retirar una regla de una combinación inactiva', async () => {
    const inactiveRuleMatrix: SlaMatrixResponse = {
      ...matrix,
      combinations: { categories: [], priorities: [] },
    }
    const wrapper = mount(SlaMatrix, { props: { matrix: inactiveRuleMatrix } })

    expect(wrapper.text()).toContain('Reglas de combinaciones inactivas')
    expect(wrapper.text()).toContain('Red × Alta')

    await wrapper
      .get('button[aria-label="Retirar regla de Red y Alta"]')
      .trigger('click')

    expect(wrapper.emitted('retire')?.[0]).toEqual(['r1'])
  })

  it('incluye reglas con refs inactivas presentes en combinations', async () => {
    const inactiveRefMatrix: SlaMatrixResponse = {
      ...matrix,
      items: [
        {
          ...matrix.items[0]!,
          category: { ...matrix.items[0]!.category, is_active: false },
        },
      ],
      combinations: {
        categories: [{ ...matrix.combinations.categories[0]!, is_active: false }],
        priorities: [...matrix.combinations.priorities],
      },
    }
    const wrapper = mount(SlaMatrix, { props: { matrix: inactiveRefMatrix } })

    expect(wrapper.text()).toContain('Reglas de combinaciones inactivas')
    expect(wrapper.text()).toContain('Red × Alta')

    await wrapper
      .get('button[aria-label="Retirar regla de Red y Alta"]')
      .trigger('click')

    expect(wrapper.emitted('retire')?.[0]).toEqual(['r1'])
  })

  it('pide confirmación al salir con cambios sin guardar', async () => {
    const wrapper = mount(SlaMatrix, { props: { matrix } })
    const leaveGuard = onBeforeRouteLeave.mock.calls.at(-1)?.[0] as () => boolean

    expect(leaveGuard()).toBe(true)

    await cell(wrapper).trigger('click')
    await wrapper.get('#sla-cell-hours').setValue('3')
    await wrapper.get('form').trigger('submit')

    const confirm = vi.spyOn(window, 'confirm').mockReturnValue(false)
    expect(leaveGuard()).toBe(false)
    expect(confirm).toHaveBeenCalledWith(
      'Tienes cambios sin guardar en la matriz SLA. ¿Salir de todos modos?',
    )
    confirm.mockRestore()
  })
})
