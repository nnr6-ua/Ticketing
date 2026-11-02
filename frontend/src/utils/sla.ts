import type { SlaState } from '@/types/workQueue'

const MINUTE = 60
const HOUR = 60 * MINUTE
const DAY = 24 * HOUR

/**
 * Formatea una duración positiva en español de España.
 *
 * - ≥ 1 día: "3 d 4 h"
 * - ≥ 1 hora: "4 h 12 min"
 * - ≥ 1 minuto: "37 min"
 * - 1..59 s: "menos de 1 min"
 */
export function formatDuration(seconds: number): string {
  const total = Math.max(0, Math.floor(seconds))

  if (total >= DAY) {
    const days = Math.floor(total / DAY)
    const hours = Math.floor((total % DAY) / HOUR)
    return hours > 0 ? `${days} d ${hours} h` : `${days} d`
  }
  if (total >= HOUR) {
    const hours = Math.floor(total / HOUR)
    const minutes = Math.floor((total % HOUR) / MINUTE)
    return minutes > 0 ? `${hours} h ${minutes} min` : `${hours} h`
  }
  if (total >= MINUTE) {
    return `${Math.floor(total / MINUTE)} min`
  }
  if (total > 0) {
    return 'menos de 1 min'
  }
  return '0 min'
}

export function formatRemaining(seconds: number): string {
  if (seconds < 0) {
    return `Vencido hace ${formatDuration(Math.abs(seconds))}`
  }
  if (seconds === 0) {
    return 'Vence ahora'
  }
  return formatDuration(seconds)
}

export function warningThresholdSeconds(totalSeconds: number): number {
  if (totalSeconds < HOUR) {
    return Math.floor(totalSeconds / 2)
  }
  return Math.max(HOUR, Math.floor(totalSeconds / 4))
}

export function classifyFromRemaining(remaining: number, threshold: number): SlaState {
  if (remaining < 0) {
    return 'overdue'
  }
  if (remaining <= threshold) {
    return 'at_risk'
  }
  return 'on_time'
}

interface ClassifyInput {
  isFinal: boolean
  deadline: string | null
  startedAt: string | null
  now: number
}

/** Paridad con `backend/app/utils/sla.py::classify_sla`. */
export function classifySla(input: ClassifyInput): SlaState {
  if (input.isFinal) {
    return 'finalized'
  }
  if (!input.deadline || !input.startedAt) {
    return 'no_sla'
  }

  const deadline = Date.parse(input.deadline)
  const startedAt = Date.parse(input.startedAt)
  if (Number.isNaN(deadline) || Number.isNaN(startedAt) || deadline <= startedAt) {
    return 'no_sla'
  }

  const remaining = Math.floor((deadline - input.now) / 1000)
  const total = Math.floor((deadline - startedAt) / 1000)
  return classifyFromRemaining(remaining, warningThresholdSeconds(total))
}
