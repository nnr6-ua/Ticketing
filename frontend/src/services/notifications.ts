import { apiGet, apiPost } from '@/api/client'
import type {
  MarkNotificationReadResponse,
  NotificationListResponse,
} from '@/types/notifications'

const BASE_PATH = '/api/v1/me/notifications'

export interface NotificationQuery {
  page?: number
  page_size?: number
  unread_only?: boolean
}

/** `GET /api/v1/me/notifications?page=&page_size=&unread_only=` */
export function getNotifications(
  query: NotificationQuery = {},
  signal?: AbortSignal,
): Promise<NotificationListResponse> {
  return apiGet<NotificationListResponse>(BASE_PATH, {
    signal,
    query: {
      page: query.page,
      page_size: query.page_size,
      unread_only:
        query.unread_only === undefined ? undefined : String(query.unread_only),
    },
  })
}

/** `POST /api/v1/me/notifications/{id}/read` */
export function markNotificationRead(
  notificationId: string,
  signal?: AbortSignal,
): Promise<MarkNotificationReadResponse> {
  return apiPost<MarkNotificationReadResponse, Record<string, never>>(
    `${BASE_PATH}/${encodeURIComponent(notificationId)}/read`,
    {},
    { signal },
  )
}
