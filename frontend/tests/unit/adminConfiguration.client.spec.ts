import { afterEach, describe, expect, it, vi } from 'vitest'

import { apiGet } from '@/api/client'
import {
  getConfigHistory,
  getSlaMatrix,
  listCategories,
  listPriorities,
} from '@/services/adminConfiguration'

const ADMIN_MESSAGE = 'No se pudo cargar la configuración. Inténtalo de nuevo.'

function failedResponse() {
  return {
    ok: false,
    status: 500,
    json: async () => {
      throw new Error('respuesta sin cuerpo JSON')
    },
  }
}

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('fallback de las cargas GET de administración', () => {
  it('usa un mensaje neutro en todas las cargas del servicio', async () => {
    const loads = [
      () => listCategories(),
      () => listPriorities(),
      () => getSlaMatrix(),
      () => getConfigHistory({ page: 1, page_size: 25 }),
    ]

    for (const load of loads) {
      vi.stubGlobal('fetch', vi.fn().mockResolvedValue(failedResponse()))
      await expect(load()).rejects.toMatchObject({ message: ADMIN_MESSAGE })
    }
  })

  it('conserva el fallback compartido fuera de administración', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(failedResponse()))

    await expect(apiGet('/api/v1/tickets')).rejects.toMatchObject({
      message: 'No se pudo cargar la cola de trabajo.',
    })
  })
})
