import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import WorkQueuePagination from '@/components/work-queue/WorkQueuePagination.vue'
import type { Pagination } from '@/types/workQueue'

function makePagination(overrides: Partial<Pagination> = {}): Pagination {
  return {
    page: 2,
    page_size: 25,
    total_items: 60,
    total_pages: 3,
    has_next: true,
    has_previous: true,
    ...overrides,
  }
}

function mountPagination(
  pagination: Pagination = makePagination(),
  disabled = false,
) {
  return mount(WorkQueuePagination, { props: { pagination, disabled } })
}

describe('WorkQueuePagination', () => {
  it('muestra el número de página actual y el total', () => {
    const wrapper = mountPagination()

    expect(wrapper.find('nav').attributes('aria-label')).toBe(
      'Paginación de la cola de trabajo',
    )
    expect(wrapper.text()).toContain('Página 2 de 3')
  })

  it('emite "change" con la página anterior y la siguiente', async () => {
    const wrapper = mountPagination()
    const [previous, next] = wrapper.findAll('button')

    await previous.trigger('click')
    await next.trigger('click')

    expect(wrapper.emitted('change')).toEqual([[1], [3]])
  })

  it('deshabilita Anterior en la primera página', async () => {
    const wrapper = mountPagination(
      makePagination({ page: 1, has_previous: false }),
    )
    const [previous, next] = wrapper.findAll('button')

    expect(previous.attributes('disabled')).not.toBeUndefined()
    expect(next.attributes('disabled')).toBeUndefined()

    await previous.trigger('click')
    expect(wrapper.emitted('change')).toBeUndefined()
  })

  it('deshabilita Siguiente en la última página', async () => {
    const wrapper = mountPagination(
      makePagination({ page: 3, has_next: false }),
    )
    const [previous, next] = wrapper.findAll('button')

    expect(previous.attributes('disabled')).toBeUndefined()
    expect(next.attributes('disabled')).not.toBeUndefined()

    await next.trigger('click')
    expect(wrapper.emitted('change')).toBeUndefined()
  })

  it('deshabilita ambos controles durante la carga', async () => {
    const wrapper = mountPagination(makePagination(), true)
    const [previous, next] = wrapper.findAll('button')

    expect(previous.attributes('disabled')).not.toBeUndefined()
    expect(next.attributes('disabled')).not.toBeUndefined()

    await previous.trigger('click')
    await next.trigger('click')
    expect(wrapper.emitted('change')).toBeUndefined()
  })
})
