import { getAccessToken } from "@/api/client";
import type {
  ApiErrorBody,
  Priority,
  SuggestionResponse,
  Ticket,
} from "../types/api";

const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL ?? "").replace(/\/$/, "");
const API_PREFIX = `${API_BASE_URL}/api/v1`;

export class ApiError extends Error {
  readonly status: number;
  readonly code: string;

  constructor(status: number, body: ApiErrorBody) {
    const error = body.detail ?? {};
    super(error.message ?? "Ha ocurrido un error inesperado.");
    this.name = "ApiError";
    this.status = status;
    this.code = error.code ?? "UNKNOWN_ERROR";
  }
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const headers = new Headers(options.headers);
  headers.set("Accept", "application/json");

  const token = getAccessToken();
  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }

  if (options.body && !(options.body instanceof FormData)) {
    headers.set("Content-Type", "application/json");
  }

  let response: Response;
  try {
    response = await fetch(`${API_PREFIX}${path}`, {
      ...options,
      headers,
      credentials: "omit",
    });
  } catch {
    throw new ApiError(0, {
      detail: {
        code: "network_error",
        message:
          "No se pudo conectar con el servidor. Revisa tu conexión e inténtalo de nuevo.",
      },
    });
  }

  if (!response.ok) {
    let body: ApiErrorBody = {};
    try {
      body = (await response.json()) as ApiErrorBody;
    } catch {
      body = {
        detail: {
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
  priorityId: string | null;
  attachments: File[];
}

export function createTicket(payload: CreateTicketPayload): Promise<Ticket> {
  const form = new FormData();
  form.append("title", payload.title);
  form.append("description", payload.description);

  if (payload.priorityId !== null) {
    form.append("priority_id", payload.priorityId);
  }

  for (const file of payload.attachments) {
    form.append("attachments", file, file.name);
  }

  return request<Ticket>("/tickets", {
    method: "POST",
    body: form,
  });
}
