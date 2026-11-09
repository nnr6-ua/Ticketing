import type { Component } from 'vue'
import {
  AlertOctagon,
  AlertTriangle,
  CheckCircle2,
  MinusCircle,
} from 'lucide-vue-next'

import type { SlaState } from '@/types/workQueue'

/** Mapas estáticos: Tailwind detecta las clases completas en el build. */

export const SLA_ROW_CLASS: Record<SlaState, string> = {
  overdue: 'bg-red-50 border-l-4 border-red-600',
  at_risk: 'bg-amber-50 border-l-4 border-amber-500',
  on_time: 'bg-white border-l-4 border-transparent',
  no_sla: 'bg-white border-l-4 border-transparent',
  finalized: 'bg-slate-50 border-l-4 border-transparent',
}

export const SLA_BADGE_CLASS: Record<SlaState, string> = {
  overdue: 'bg-red-100 text-red-800 ring-1 ring-inset ring-red-600',
  at_risk: 'bg-amber-100 text-amber-900 ring-1 ring-inset ring-amber-500',
  on_time: 'bg-emerald-50 text-emerald-800 ring-1 ring-inset ring-emerald-200',
  no_sla: 'bg-slate-100 text-slate-700 ring-1 ring-inset ring-slate-300',
  finalized: 'bg-slate-100 text-slate-700 ring-1 ring-inset ring-slate-300',
}

export const PRIORITY_BADGE_CLASS: Record<number, string> = {
  1: 'bg-red-100 text-red-800 ring-1 ring-inset ring-red-600',
  2: 'bg-orange-100 text-orange-900 ring-1 ring-inset ring-orange-500',
  3: 'bg-blue-100 text-blue-800 ring-1 ring-inset ring-blue-600',
  4: 'bg-slate-100 text-slate-700 ring-1 ring-inset ring-slate-500',
}

export const PRIORITY_BADGE_INACTIVE_CLASS =
  'bg-slate-100 text-slate-600 ring-1 ring-inset ring-slate-300'

export const SLA_ICON: Record<SlaState, Component> = {
  overdue: AlertOctagon,
  at_risk: AlertTriangle,
  on_time: CheckCircle2,
  no_sla: MinusCircle,
  finalized: CheckCircle2,
}
