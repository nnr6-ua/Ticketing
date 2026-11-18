import { ApiClientError, apiGet, apiPost, apiPostForm } from "@/api/client";
import type {
  ApiErrorBody,
  Priority,
  SuggestionResponse,
  Ticket,
} from "../types/api";

export class ApiError extends ApiClientError {
  readonly status: number;
  readonly code: string;

  constructor(status: number, body: ApiErrorBody) {
    const error = body.detail ?? {};
    const kind =
      status === 0
        ? "network"
        : status === 401
          ? "unauthorized"
          : status === 403
            ? "forbidden"
            : status < 500
              ? "invalid"
              : "server";
    super(
      kind,
      error.message ?? "Ha ocurrido un error inesperado.",
      status,
      error.code ?? "UNKNOWN_ERROR",
    );
    this.name = "ApiError";
    this.status = status;
    this.code = error.code ?? "UNKNOWN_ERROR";
  }
}

export interface CreateTicketPayload {
  title: string;
  description: string;
  priorityId: string | null;
  attachments: File[];
}

export function getPriorities(): Promise<Priority[]> {
  return apiGet("/api/v1/priorities", {
    fallbackMessage: "No se pudieron cargar las prioridades.",
  });
}

export function getSuggestion(
  title: string,
  description: string,
): Promise<SuggestionResponse> {
  return apiPost(
    "/api/v1/suggestions",
    { title, description },
    { fallbackMessage: "No se pudo calcular la sugerencia." },
  );
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

  return apiPostForm("/api/v1/tickets", form, {
    fallbackMessage: "No se pudo crear el ticket. Inténtalo de nuevo.",
  });
}
