import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import WorkQueueEmptyState from '@/components/work-queue/WorkQueueEmptyState.vue'
import WorkQueueErrorState from '@/components/work-queue/WorkQueueErrorState.vue'

describe('WorkQueueErrorState', () => {
  it('muestra el error de carga completo y emite "retry"', async () => {
    const wrapper = mount(WorkQueueErrorState)

    expect(wrapper.attributes('data-variant')).toBe('full')
    expect(wrapper.attributes('role')).toBe('alert')
    expect(wrapper.text()).toContain('No se pudo cargar tu cola de trabajo')
    expect(wrapper.text()).toContain('Comprueba tu conexión e inténtalo de nuevo.')

    await wrapper.find('button').trigger('click')
    expect(wrapper.emitted('retry')).toHaveLength(1)
  })

  it('usa el mensaje recibido en la variante full', () => {
    const wrapper = mount(WorkQueueErrorState, {
      props: { message: 'El servidor no responde.' },
    })

    expect(wrapper.text()).toContain('El servidor no responde.')
  })

  it('avisa de que se muestran los últimos datos al fallar un refresco', () => {
    const wrapper = mount(WorkQueueErrorState, {
      props: {
        variant: 'warning',
        message: 'No se pudo cargar tu cola de trabajo.',
      },
    })

    expect(wrapper.attributes('data-variant')).toBe('warning')
    expect(wrapper.attributes('role')).toBe('status')
    expect(wrapper.text()).toContain('No se pudo actualizar la cola de trabajo')
    expect(wrapper.text()).toContain(
      'No se pudo actualizar; se muestran los últimos datos.',
    )
    // El aviso de refresco no reutiliza el mensaje de error de carga inicial.
    expect(wrapper.text()).not.toContain('No se pudo cargar tu cola de trabajo')
  })

  it('muestra la variante forbidden sin acceso para no técnicos', async () => {
    const wrapper = mount(WorkQueueErrorState, {
      props: { variant: 'forbidden', message: 'ignorado' },
    })

    expect(wrapper.attributes('data-variant')).toBe('forbidden')
    expect(wrapper.attributes('role')).toBe('alert')
    expect(wrapper.text()).toContain('No tienes acceso a esta vista')
    expect(wrapper.text()).toContain(
      'Esta vista está disponible solo para técnicos.',
    )

    await wrapper.find('button').trigger('click')
    expect(wrapper.emitted('retry')).toHaveLength(1)
  })
})

describe('WorkQueueEmptyState', () => {
  it('distingue los tres estados vacíos', () => {
    const noAssignments = mount(WorkQueueEmptyState, {
      props: { variant: 'no_assignments' },
    })
    const onlyFinal = mount(WorkQueueEmptyState, {
      props: { variant: 'only_final' },
    })
    const noResults = mount(WorkQueueEmptyState, {
      props: { variant: 'no_results' },
    })

    expect(noAssignments.attributes('data-variant')).toBe('no_assignments')
    expect(onlyFinal.attributes('data-variant')).toBe('only_final')
    expect(noResults.attributes('data-variant')).toBe('no_results')

    const texts = [noAssignments, onlyFinal, noResults].map((wrapper) =>
      wrapper.find('h2').text(),
    )
    expect(new Set(texts).size).toBe(3)
  })

  it('muestra el estado solo finalizados y no ofrece limpiar filtros', () => {
    const wrapper = mount(WorkQueueEmptyState, {
      props: { variant: 'only_final' },
    })

    expect(wrapper.text()).toContain('No tienes tickets activos')
    expect(wrapper.text()).toContain(
      'Solo tienes tickets finalizados. Usa el filtro de estado para consultarlos.',
    )
    expect(wrapper.find('button').exists()).toBe(false)
  })

  it('solo el estado sin resultados ofrece limpiar filtros', async () => {
    const noAssignments = mount(WorkQueueEmptyState, {
      props: { variant: 'no_assignments' },
    })
    const onlyFinal = mount(WorkQueueEmptyState, {
      props: { variant: 'only_final' },
    })
    const noResults = mount(WorkQueueEmptyState, {
      props: { variant: 'no_results' },
    })

    expect(noAssignments.find('button').exists()).toBe(false)
    expect(onlyFinal.find('button').exists()).toBe(false)

    const button = noResults.find('button')
    expect(button.text()).toBe('Limpiar filtros')
    await button.trigger('click')
    expect(noResults.emitted('clear')).toHaveLength(1)
  })
})
