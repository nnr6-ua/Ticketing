import { apiGet } from '@/api/client'
import type {
  SlaDashboardFilters,
  SlaDashboardOptions,
  SlaDashboardResponse,
} from '@/types/slaDashboard'

function baseQuery(filters: Pick<SlaDashboardFilters, 'desde' | 'hasta'>) {
  return {
    desde: filters.desde ?? undefined,
    hasta: filters.hasta ?? undefined,
  }
}

/** `GET /api/v1/sla-dashboard` (solo lectura). */
export function fetchSlaDashboard(
  filters: SlaDashboardFilters,
  signal?: AbortSignal,
): Promise<SlaDashboardResponse> {
  const query: Record<string, string | undefined> = {
    ...baseQuery(filters),
    categorias: filters.categorias.length
      ? filters.categorias.join(',')
      : undefined,
    prioridades: filters.prioridades.length
      ? filters.prioridades.join(',')
      : undefined,
  }

  return apiGet<SlaDashboardResponse>('/api/v1/sla-dashboard', {
    signal,
    query,
  })
}

/** `GET /api/v1/sla-dashboard/options` (solo lectura). */
export function fetchSlaDashboardOptions(
  filters: Pick<SlaDashboardFilters, 'desde' | 'hasta'>,
  signal?: AbortSignal,
): Promise<SlaDashboardOptions> {
  return apiGet<SlaDashboardOptions>('/api/v1/sla-dashboard/options', {
    signal,
    query: baseQuery(filters),
  })
}
