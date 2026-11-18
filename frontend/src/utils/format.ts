import { formatDuration } from '@/utils/sla'

const percentFormatter = new Intl.NumberFormat('es-ES', {
  minimumFractionDigits: 1,
  maximumFractionDigits: 1,
})

const countFormatter = new Intl.NumberFormat('es-ES')

/** «87,5 %» con coma decimal y un decimal. */
export function formatPercent(value: number | null): string {
  if (value === null || !Number.isFinite(value)) {
    return 'Sin datos'
  }
  return `${percentFormatter.format(value)} %`
}

/** Recuento entero es-ES: «10.000» usa el separador de miles. */
export function formatCount(value: number): string {
  if (!Number.isFinite(value)) {
    return 'Sin datos'
  }
  return countFormatter.format(value)
}

/**
 * Duraciones es-ES reutilizando `formatDuration` de `utils/sla.ts`
 * («3 d 4 h», «4 h 12 min», «37 min», «menos de 1 min»).
 */
export function formatDurationEs(seconds: number): string {
  return formatDuration(seconds)
}

const madridFormatter = new Intl.DateTimeFormat('es-ES', {
  timeZone: 'Europe/Madrid',
  day: '2-digit',
  month: '2-digit',
  year: 'numeric',
  hour: '2-digit',
  minute: '2-digit',
  hourCycle: 'h23',
})

/** «15/11/2026 09:34» en `Europe/Madrid`. */
export function formatMadridDateTime(iso: string): string {
  const date = new Date(iso)
  if (Number.isNaN(date.getTime())) {
    return 'Sin datos'
  }
  const parts = madridFormatter.formatToParts(date)
  const get = (type: Intl.DateTimeFormatPartTypes): string =>
    parts.find((part) => part.type === type)?.value ?? ''

  return `${get('day')}/${get('month')}/${get('year')} ${get('hour')}:${get('minute')}`
}
