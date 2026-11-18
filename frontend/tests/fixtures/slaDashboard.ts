import type {
  ComplianceMetrics,
  MatrixRow,
  RankingEntry,
  SlaDashboardFilters,
  SlaDashboardMeta,
  SlaDashboardOptions,
  SlaDashboardResponse,
  TotalsEntry,
} from '@/types/slaDashboard'

export function makeMetrics(
  overrides: Partial<ComplianceMetrics> = {},
): ComplianceMetrics {
  return {
    ticket_count: 10,
    no_sla_count: 1,
    attended_with_sla: 6,
    on_time: 5,
    compliance_pct: 83.3,
    avg_response_seconds: 4 * 3600 + 12 * 60,
    overdue_count: 1,
    semaphore: 'ambar',
    ...overrides,
  }
}

export function makeMatrixRow(overrides: Partial<MatrixRow> = {}): MatrixRow {
  return {
    ...makeMetrics(),
    priority_level: 1,
    priority_name: 'Crítica',
    priority_is_active: true,
    category_id: '11111111-1111-4111-8111-111111111111',
    category_name: 'Red',
    category_is_active: true,
    ...overrides,
  }
}

export function makeTotalsEntry(
  overrides: Partial<TotalsEntry> = {},
): TotalsEntry {
  return {
    ...makeMetrics(),
    scope: 'priority',
    priority_level: 1,
    priority_name: 'Crítica',
    priority_is_active: true,
    category_id: null,
    category_name: null,
    category_is_active: null,
    ...overrides,
  }
}

export function makeRankingEntry(
  overrides: Partial<RankingEntry> = {},
): RankingEntry {
  return {
    technician_id: '22222222-2222-4222-8222-222222222222',
    technician_name: 'Ana Torres',
    team: 'Soporte',
    is_active: true,
    overdue_count: 3,
    avg_delay_seconds: 2 * 3600,
    ...overrides,
  }
}

export const defaultFilters: SlaDashboardFilters = {
  desde: '2026-10-17',
  hasta: '2026-11-15',
  categorias: [],
  prioridades: [],
}

export function makeMeta(
  overrides: Partial<SlaDashboardMeta> = {},
): SlaDashboardMeta {
  return {
    generated_at: '2026-11-15T08:34:00Z',
    timezone: 'Europe/Madrid',
    thresholds: { green_pct: 90, amber_pct: 70 },
    filters: { ...defaultFilters },
    has_tickets: true,
    ...overrides,
  }
}

export function makeResponse(
  overrides: Partial<SlaDashboardResponse> = {},
): SlaDashboardResponse {
  const data = {
    summary: makeMetrics(),
    matrix: [
      makeMatrixRow(),
      makeMatrixRow({
        priority_level: 2,
        priority_name: 'Alta',
        category_id: null,
        category_name: 'Sin categoría',
        category_is_active: null,
      }),
    ],
    priority_totals: [
      makeTotalsEntry(),
      makeTotalsEntry({
        priority_level: 2,
        priority_name: 'Alta',
        compliance_pct: 50,
        semaphore: 'rojo',
      }),
    ],
    category_totals: [
      makeTotalsEntry({
        scope: 'category',
        priority_level: null,
        priority_name: null,
        priority_is_active: null,
        category_id: '11111111-1111-4111-8111-111111111111',
        category_name: 'Red',
        category_is_active: true,
      }),
      makeTotalsEntry({
        scope: 'category',
        priority_level: null,
        priority_name: null,
        priority_is_active: null,
        category_id: null,
        category_name: 'Sin categoría',
        category_is_active: null,
      }),
    ],
    ranking: {
      technicians: [
        makeRankingEntry(),
        makeRankingEntry({
          technician_id: '33333333-3333-4333-8333-333333333333',
          technician_name: 'Luis Pérez',
          team: 'Redes',
          is_active: false,
          overdue_count: 1,
          avg_delay_seconds: 3600,
        }),
      ],
      unassigned: makeRankingEntry({
        technician_id: null,
        technician_name: 'Sin asignar',
        team: null,
        is_active: null,
        overdue_count: 2,
        avg_delay_seconds: 7200,
      }),
      overdue_total: 6,
    },
    ...(overrides.data ?? {}),
  }

  return {
    data,
    meta: overrides.meta ?? makeMeta(),
  }
}

export function makeOptions(
  overrides: Partial<SlaDashboardOptions> = {},
): SlaDashboardOptions {
  return {
    desde: '2026-10-17',
    hasta: '2026-11-15',
    categories: [
      {
        id: '11111111-1111-4111-8111-111111111111',
        name: 'Red',
        is_active: true,
      },
      { id: null, name: 'Sin categoría', is_active: null },
    ],
    priorities: [
      { level: 1, name: 'Crítica', is_active: true },
      { level: 2, name: 'Alta', is_active: false },
    ],
    ...overrides,
  }
}
