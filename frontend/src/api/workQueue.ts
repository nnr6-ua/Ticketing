import { apiGet } from '@/api/client'
import type { WorkQueueParams, WorkQueueResponse } from '@/types/workQueue'

/** `GET /api/v1/me/work-queue` */
export function fetchWorkQueue(
  params: WorkQueueParams = {},
  signal?: AbortSignal,
): Promise<WorkQueueResponse> {
  const query: Record<string, string | number | undefined> = {
    priority: params.priority?.length ? params.priority.join(',') : undefined,
    page: params.page,
    page_size: params.page_size,
  }
  // Si se aplican los estados activos por defecto se omite `status` para que
  // el servidor decida y `applied_filters.is_default` sea verdadero.
  if (params.status && params.status.length > 0) {
    query.status = params.status.join(',')
  }

  return apiGet<WorkQueueResponse>('/api/v1/me/work-queue', { signal, query })
}
