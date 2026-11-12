import { mount } from '@vue/test-utils'
import { beforeAll, describe, expect, it, vi } from 'vitest'

import AttachmentField from '@/components/AttachmentField.vue'

beforeAll(() => {
  URL.createObjectURL = vi.fn(() => 'blob:preview')
  URL.revokeObjectURL = vi.fn()
})

function image(name: string, type = 'image/png'): File {
  return new File(['contenido'], name, { type })
}

async function drop(wrapper: ReturnType<typeof mount>, files: File[]) {
  await wrapper.get('button').trigger('drop', { dataTransfer: { files } })
}

describe('AttachmentField', () => {
  it('acepta imágenes válidas y emite la lista actualizada', async () => {
    const wrapper = mount(AttachmentField, { props: { modelValue: [] } })

    await drop(wrapper, [image('captura.png')])

    const emitted = wrapper.emitted('update:modelValue')
    expect(emitted).toHaveLength(1)
    expect((emitted?.[0][0] as File[]).map((file) => file.name)).toEqual([
      'captura.png',
    ])
  })

  it('rechaza extensiones no permitidas y lo anuncia con role alert', async () => {
    const wrapper = mount(AttachmentField, { props: { modelValue: [] } })

    await drop(wrapper, [new File(['hola'], 'notas.txt', { type: 'text/plain' })])

    expect(wrapper.emitted('update:modelValue')).toBeUndefined()
    expect(wrapper.get('[role="alert"]').text()).toContain(
      'solo se permiten imágenes PNG, JPG o GIF',
    )
  })

  it('rechaza archivos que superan los 5 MB', async () => {
    const wrapper = mount(AttachmentField, { props: { modelValue: [] } })
    const big = image('grande.png')
    Object.defineProperty(big, 'size', { value: 5 * 1024 * 1024 + 1 })

    await drop(wrapper, [big])

    expect(wrapper.emitted('update:modelValue')).toBeUndefined()
    expect(wrapper.get('[role="alert"]').text()).toContain('supera el límite de 5 MB')
  })

  it('limita el número máximo de adjuntos', async () => {
    const files = Array.from({ length: 5 }, (_, index) => image(`foto-${index}.png`))
    const wrapper = mount(AttachmentField, { props: { modelValue: files } })

    await drop(wrapper, [image('sexta.png')])

    expect(wrapper.emitted('update:modelValue')).toBeUndefined()
    expect(wrapper.get('[role="alert"]').text()).toContain(
      'Puedes adjuntar como máximo 5 archivos',
    )
  })

  it('permite quitar un adjunto existente', async () => {
    const file = image('captura.png')
    const wrapper = mount(AttachmentField, { props: { modelValue: [file] } })

    await wrapper.get('button[aria-label="Quitar captura.png"]').trigger('click')

    expect(wrapper.emitted('update:modelValue')?.[0][0]).toEqual([])
  })
})
