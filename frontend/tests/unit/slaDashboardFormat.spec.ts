import { describe, expect, it } from 'vitest'

import {
  formatCount,
  formatDurationEs,
  formatMadridDateTime,
  formatPercent,
} from '@/utils/format'

describe('formatPercent', () => {
  it('usa coma decimal y un decimal con el símbolo de porcentaje', () => {
    expect(formatPercent(87.5)).toBe('87,5 %')
    expect(formatPercent(100)).toBe('100,0 %')
    expect(formatPercent(0)).toBe('0,0 %')
  })

  it('devuelve «Sin datos» cuando no hay valor', () => {
    expect(formatPercent(null)).toBe('Sin datos')
  })
})

describe('formatCount', () => {
  it('usa el separador de miles es-ES en los recuentos enteros', () => {
    expect(formatCount(10000)).toBe('10.000')
    expect(formatCount(1234567)).toBe('1.234.567')
    expect(formatCount(1)).toBe('1')
    expect(formatCount(0)).toBe('0')
  })
})

describe('formatDurationEs', () => {
  it('formatea días, horas y minutos en es-ES', () => {
    expect(formatDurationEs(3 * 86400 + 4 * 3600)).toBe('3 d 4 h')
    expect(formatDurationEs(4 * 3600 + 12 * 60)).toBe('4 h 12 min')
    expect(formatDurationEs(37 * 60)).toBe('37 min')
  })

  it('trata los valores menores de un minuto', () => {
    expect(formatDurationEs(30)).toBe('menos de 1 min')
    expect(formatDurationEs(0)).toBe('0 min')
  })
})

describe('formatMadridDateTime', () => {
  it('presenta el instante UTC en Europe/Madrid', () => {
    expect(formatMadridDateTime('2026-11-15T08:34:00Z')).toBe(
      '15/11/2026 09:34',
    )
  })

  it('cambia de día cuando el instante UTC cae en el día siguiente en Madrid', () => {
    expect(formatMadridDateTime('2026-11-14T23:30:00Z')).toBe(
      '15/11/2026 00:30',
    )
  })
})
