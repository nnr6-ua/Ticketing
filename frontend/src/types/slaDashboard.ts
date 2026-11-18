/**
 * Tipos del contrato `contracts/frontend-components.md` §2 para HU-07.
 *
 * Todos los valores (porcentajes, semáforos, umbrales y rankings) llegan ya
 * calculados del backend; el cliente no recalcula métricas.
 */

export type SlaSemaphore = 'verde' | 'ambar' | 'rojo' | 'sin_datos'

export interface SlaThresholds {
  green_pct: number
  amber_pct: number
}

export interface ComplianceMetrics {
  ticket_count: number
  no_sla_count: number
  attended_with_sla: number
  on_time: number
  compliance_pct: number | null
  avg_response_seconds: number | null
  overdue_count: number
  semaphore: SlaSemaphore
}

export interface MatrixRow extends ComplianceMetrics {
  priority_level: 1 | 2 | 3 | 4
  priority_name: string
  priority_is_active: boolean
  category_id: string | null
  category_name: string
  category_is_active: boolean | null
}

export interface TotalsEntry extends ComplianceMetrics {
  scope: 'priority' | 'category' | 'global'
  priority_level: number | null
  priority_name: string | null
  priority_is_active: boolean | null
  category_id: string | null
  category_name: string | null
  category_is_active: boolean | null
}

export interface RankingEntry {
  technician_id: string | null
  technician_name: string
  team: string | null
  is_active: boolean | null
  overdue_count: number
  avg_delay_seconds: number
}

export interface SlaDashboardFilters {
  desde: string | null
  hasta: string | null
  categorias: string[]
  prioridades: number[]
}

export interface SlaDashboardData {
  summary: ComplianceMetrics
  matrix: MatrixRow[]
  priority_totals: TotalsEntry[]
  category_totals: TotalsEntry[]
  ranking: {
    technicians: RankingEntry[]
    unassigned: RankingEntry | null
    overdue_total: number
  }
}

export interface SlaDashboardMeta {
  generated_at: string
  timezone: 'Europe/Madrid'
  thresholds: SlaThresholds
  filters: SlaDashboardFilters
  has_tickets: boolean
}

export interface SlaDashboardOptions {
  desde: string
  hasta: string
  categories: {
    id: string | null
    name: string
    is_active: boolean | null
  }[]
  priorities: { level: number; name: string; is_active: boolean }[]
}

export interface SlaDashboardResponse {
  data: SlaDashboardData
  meta: SlaDashboardMeta
}
