import type {
  ApiErrorBody,
  Priority,
  SuggestionResponse,
  Ticket,
} from "../types/api";

const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000/api/v1";
const EMPLOYEE_ID = import.meta.env.VITE_DEV_EMPLOYEE_ID ?? "1";

export class ApiError extends Error {
  readonly status: number;
  readonly code: string;
  readonly field?: string;
  readonly details?: unknown;

  constructor(status: number, body: ApiErrorBody) {
    const error = body.error ?? {};
    super(error.message ?? "Ha ocurrido un error inesperado.");
    this.name = "ApiError";
    this.status = status;
    this.code = error.code ?? "UNKNOWN_ERROR";
    this.field = error.field;
    this.details = error.details;
  }
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const headers = new Headers(options.headers);
  headers.set("X-Employee-Id", EMPLOYEE_ID);

  if (options.body && !(options.body instanceof FormData)) {
    headers.set("Content-Type", "application/json");
  }

  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...options,
    headers,
  });

  if (!response.ok) {
    let body: ApiErrorBody = {};
    try {
      body = (await response.json()) as ApiErrorBody;
    } catch {
      body = {
        error: {
          code: "INVALID_RESPONSE",
          message: "El servidor devolvió una respuesta no válida.",
        },
      };
    }
    throw new ApiError(response.status, body);
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return (await response.json()) as T;
}

export function getPriorities(): Promise<Priority[]> {
  return request<Priority[]>("/priorities");
}

export function getSuggestion(
  title: string,
  description: string,
): Promise<SuggestionResponse> {
  return request<SuggestionResponse>("/suggestions", {
    method: "POST",
    body: JSON.stringify({ title, description }),
  });
}

export interface CreateTicketPayload {
  title: string;
  description: string;
  priorityId: number | null;
  attachments: File[];
}

export function createTicket(payload: CreateTicketPayload): Promise<Ticket> {
  const form = new FormData();
  form.append("title", payload.title);
  form.append("description", payload.description);

  if (payload.priorityId !== null) {
    form.append("priority_id", String(payload.priorityId));
  }

  for (const file of payload.attachments) {
    form.append("attachments", file, file.name);
  }

  return request<Ticket>("/tickets", {
    method: "POST",
    body: form,
  });
}
