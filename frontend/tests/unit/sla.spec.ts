import { describe, expect, it } from 'vitest'

import {
  classifyFromRemaining,
  classifySla,
  formatDuration,
  formatRemaining,
  warningThresholdSeconds,
} from '@/utils/sla'

const HOUR = 3600
const DAY = 24 * HOUR

describe('formatDuration', () => {
  it('formatea días y horas', () => {
    expect(formatDuration(3 * DAY + 4 * HOUR)).toBe('3 d 4 h')
    expect(formatDuration(DAY)).toBe('1 d')
  })

  it('formatea horas y minutos', () => {
    expect(formatDuration(4 * HOUR + 12 * 60)).toBe('4 h 12 min')
    expect(formatDuration(HOUR)).toBe('1 h')
  })

  it('formatea minutos completos', () => {
    expect(formatDuration(37 * 60)).toBe('37 min')
  })

  it('muestra "menos de 1 min" por debajo del minuto', () => {
    expect(formatDuration(59)).toBe('menos de 1 min')
    expect(formatDuration(1)).toBe('menos de 1 min')
  })

  it('nunca produce duraciones negativas', () => {
    expect(formatDuration(0)).toBe('0 min')
    expect(formatDuration(-90)).toBe('0 min')
  })
})

describe('formatRemaining', () => {
  it('formatea el tiempo restante positivo', () => {
    expect(formatRemaining(4 * HOUR + 12 * 60)).toBe('4 h 12 min')
    expect(formatRemaining(37 * 60)).toBe('37 min')
    expect(formatRemaining(59)).toBe('menos de 1 min')
  })

  it('muestra "Vence ahora" en el límite exacto', () => {
    expect(formatRemaining(0)).toBe('Vence ahora')
  })

  it('describe el tiempo vencido con valor absoluto', () => {
    expect(formatRemaining(-(2 * HOUR + 5 * 60))).toBe('Vencido hace 2 h 5 min')
    expect(formatRemaining(-30)).toBe('Vencido hace menos de 1 min')
  })
})

describe('warningThresholdSeconds', () => {
  it('usa la mitad del total para SLA cortos (< 60 min)', () => {
    expect(warningThresholdSeconds(30 * 60)).toBe(15 * 60)
    expect(warningThresholdSeconds(59 * 60)).toBe(29 * 60 + 30)
  })

  it('usa max(60 min, 25 %) para SLA de 60 min o más', () => {
    expect(warningThresholdSeconds(60 * 60)).toBe(60 * 60)
    expect(warningThresholdSeconds(4 * HOUR)).toBe(60 * 60)
    expect(warningThresholdSeconds(24 * HOUR)).toBe(6 * HOUR)
  })
})

describe('classifyFromRemaining', () => {
  it('clasifica el límite exacto y los negativos', () => {
    expect(classifyFromRemaining(-1, 900)).toBe('overdue')
    expect(classifyFromRemaining(0, 900)).toBe('at_risk')
    expect(classifyFromRemaining(900, 900)).toBe('at_risk')
    expect(classifyFromRemaining(901, 900)).toBe('on_time')
  })
})

describe('classifySla (paridad con el backend)', () => {
  const now = Date.parse('2026-10-29T10:00:00Z')

  it('marca los finalizados como finalized', () => {
    expect(
      classifySla({
        isFinal: true,
        deadline: '2026-10-29T12:00:00Z',
        startedAt: '2026-10-29T08:00:00Z',
        now,
      }),
    ).toBe('finalized')
  })

  it('trata la ausencia de deadline o inicio como no_sla', () => {
    expect(
      classifySla({ isFinal: false, deadline: null, startedAt: null, now }),
    ).toBe('no_sla')
    expect(
      classifySla({
        isFinal: false,
        deadline: '2026-10-29T12:00:00Z',
        startedAt: null,
        now,
      }),
    ).toBe('no_sla')
  })

  it('trata datos corruptos (deadline <= inicio) como no_sla', () => {
    expect(
      classifySla({
        isFinal: false,
        deadline: '2026-10-29T08:00:00Z',
        startedAt: '2026-10-29T08:00:00Z',
        now,
      }),
    ).toBe('no_sla')
  })

  it('aplica el umbral corto de un SLA de 30 min (borde 15:30)', () => {
    const sla = {
      isFinal: false,
      deadline: '2026-10-29T10:30:00Z',
      startedAt: '2026-10-29T10:00:00Z',
    }
    expect(
      classifySla({ ...sla, now: Date.parse('2026-10-29T10:14:30Z') }),
    ).toBe('on_time')
    expect(
      classifySla({ ...sla, now: Date.parse('2026-10-29T10:15:00Z') }),
    ).toBe('at_risk')
  })

  it('clasifica el límite exacto y un segundo después', () => {
    const sla = {
      isFinal: false,
      deadline: '2026-10-29T10:30:00Z',
      startedAt: '2026-10-29T10:00:00Z',
    }
    expect(
      classifySla({ ...sla, now: Date.parse('2026-10-29T10:30:00Z') }),
    ).toBe('at_risk')
    expect(
      classifySla({ ...sla, now: Date.parse('2026-10-29T10:30:01Z') }),
    ).toBe('overdue')
  })

  it('aplica el umbral largo de un SLA de 4 h (60 min)', () => {
    const sla = {
      isFinal: false,
      deadline: '2026-10-29T14:00:00Z',
      startedAt: '2026-10-29T10:00:00Z',
    }
    expect(
      classifySla({ ...sla, now: Date.parse('2026-10-29T12:59:00Z') }),
    ).toBe('on_time')
    expect(
      classifySla({ ...sla, now: Date.parse('2026-10-29T13:00:00Z') }),
    ).toBe('at_risk')
  })
})
