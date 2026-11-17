/** Tipos alineados con `contracts/assignee-change.openapi.yaml` (HU-06). */

import type { Pagination } from '@/types/ticketWorkflow'

export type NotificationType = 'ticket_reassigned' | 'ticket_escalated'

export interface Notification {
  id: string
  type: NotificationType
  ticket_id: string
  ticket_number: string
  ticket_title: string
  previous_assignee_name: string
  is_read: boolean
  created_at: string
  read_at: string | null
}

export interface NotificationListResponse {
  items: Notification[]
  unread_count: number
  pagination: Pagination
}

export interface MarkNotificationReadResponse {
  changed: boolean
  message: string | null
  notification: Notification
}
