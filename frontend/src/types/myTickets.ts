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
}

export interface MyTicketsResponse {
  items: MyTicketSummary[]
}
