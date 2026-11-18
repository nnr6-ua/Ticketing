export interface MyTicketCategory {
  id: string
  name: string
}

export interface MyTicketPriority {
  id: string
  name: string
  level: number
  color: string | null
}

export interface MyTicketSummary {
  id: string
  ticket_number: string
  title: string
  status: string
  status_label: string
  category: MyTicketCategory | null
  priority: MyTicketPriority
  created_at: string
  updated_at: string
  awaiting_user_response: boolean
  response_requested_at: string | null
  reminder_active: boolean
  reminder_due_at: string | null
}

export interface MyTicketsResponse {
  items: MyTicketSummary[]
}
