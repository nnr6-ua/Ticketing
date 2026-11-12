export interface Employee {
  id: number;
  name: string;
  email: string;
}

export interface Category {
  id: number;
  name: string;
}

export interface Priority {
  id: number;
  name: string;
  level: number;
  color: string;
  is_system: boolean;
}

export interface Attachment {
  id: number;
  original_filename: string;
  mime_type: string;
  size_bytes: number;
}

export interface Ticket {
  id: number;
  ticket_number: string;
  title: string;
  description: string;
  status: string;
  creator: Employee;
  category: Category;
  priority: Priority;
  attachments: Attachment[];
  created_at: string;
  updated_at: string;
  duplicate: boolean;
}

export interface SuggestionResponse {
  category: Category;
  priority: Priority;
  category_is_fallback: boolean;
  priority_is_fallback: boolean;
}

export interface ApiErrorBody {
  error?: {
    code?: string;
    message?: string;
    field?: string;
    details?: unknown;
  };
}
