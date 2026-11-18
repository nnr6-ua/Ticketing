export interface Employee {
  id: string;
  name: string;
  email: string;
}

export interface Category {
  id: string;
  name: string;
}

export interface Priority {
  id: string;
  name: string;
  level: number;
  color: string | null;
  is_system?: boolean;
}

export interface Attachment {
  id: string;
  original_filename: string;
  mime_type: string;
  size_bytes: number;
}

export interface Ticket {
  id: string;
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
  detail?: {
    code?: string;
    message?: string;
  };
}
