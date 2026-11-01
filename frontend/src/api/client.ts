/**
 * Cliente HTTP tipado.
 *
 * El token JWT se obtiene del mecanismo de autenticación existente. Mientras
 * esa pieza no esté disponible en este repositorio, se lee de
 * `localStorage.access_token`; `setAccessToken` es el punto de integración.
 */

const TOKEN_STORAGE_KEY = 'access_token'

export type ApiErrorKind =
  | 'unauthorized'
  | 'forbidden'
  | 'invalid'
  | 'server'
  | 'network'

export class ApiClientError extends Error {
  readonly kind: ApiErrorKind
  readonly status?: number
  readonly code?: string

  constructor(kind: ApiErrorKind, message: string, status?: number, code?: string) {
    super(message)
    this.name = 'ApiClientError'
    this.kind = kind
    this.status = status
    this.code = code
  }
}

export function getAccessToken(): string | null {
  try {
    return window.localStorage.getItem(TOKEN_STORAGE_KEY)
  } catch {
    return null
  }
}

export function setAccessToken(token: string | null): void {
  try {
    if (token) {
      window.localStorage.setItem(TOKEN_STORAGE_KEY, token)
    } else {
      window.localStorage.removeItem(TOKEN_STORAGE_KEY)
    }
  } catch {
    // Almacenamiento no disponible: la vista seguirá sin token y devolverá 401.
  }
}

function buildUrl(path: string, query?: Record<string, string | number | undefined>): string {
  const base = (import.meta.env.VITE_API_BASE_URL ?? '').replace(/\/$/, '')
  const search = new URLSearchParams()
  for (const [key, value] of Object.entries(query ?? {})) {
    if (value !== undefined && value !== '') {
      search.set(key, String(value))
    }
  }
  const suffix = search.toString()
  return `${base}${path}${suffix ? `?${suffix}` : ''}`
}

interface RequestOptions {
  signal?: AbortSignal
  query?: Record<string, string | number | undefined>
}

async function parseError(
  response: Response,
  fallbackMessage = 'No se pudo cargar la cola de trabajo.',
): Promise<ApiClientError> {
  let code: string | undefined
  let message: string | undefined
  try {
    const body = (await response.json()) as {
      detail?: { code?: string; message?: string }
    }
    code = body.detail?.code
    message = body.detail?.message
  } catch {
    // Cuerpo no JSON: se usa el mensaje genérico.
  }

  if (response.status === 401) {
    return new ApiClientError(
      'unauthorized',
      message ?? 'La sesión no es válida o ha caducado.',
      401,
      code,
    )
  }
  if (response.status === 403) {
    return new ApiClientError(
      'forbidden',
      message ?? 'No tienes acceso a esta vista.',
      403,
      code,
    )
  }
  if (response.status === 422) {
    return new ApiClientError(
      'invalid',
      message ?? 'Los filtros seleccionados no son válidos.',
      422,
      code,
    )
  }
  return new ApiClientError('server', message ?? fallbackMessage, response.status, code)
}

function networkError(caught: unknown): ApiClientError | DOMException {
  if (caught instanceof DOMException && caught.name === 'AbortError') {
    return caught
  }
  return new ApiClientError(
    'network',
    'No se pudo conectar con el servidor. Comprueba tu conexión.',
  )
}

export async function apiGet<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const headers: Record<string, string> = { Accept: 'application/json' }
  const token = getAccessToken()
  if (token) {
    headers.Authorization = `Bearer ${token}`
  }

  let response: Response
  try {
    response = await fetch(buildUrl(path, options.query), {
      method: 'GET',
      headers,
      signal: options.signal,
      credentials: 'omit',
    })
  } catch (caught) {
    throw networkError(caught)
  }

  if (!response.ok) {
    throw await parseError(response)
  }

  return (await response.json()) as T
}

export async function apiPost<TResponse, TBody>(
  path: string,
  body: TBody,
  options: RequestOptions = {},
): Promise<TResponse> {
  const headers: Record<string, string> = {
    Accept: 'application/json',
    'Content-Type': 'application/json',
  }
  const token = getAccessToken()
  if (token) {
    headers.Authorization = `Bearer ${token}`
  }

  let response: Response
  try {
    response = await fetch(buildUrl(path, options.query), {
      method: 'POST',
      headers,
      body: JSON.stringify(body),
      signal: options.signal,
      credentials: 'omit',
    })
  } catch (caught) {
    throw networkError(caught)
  }

  if (!response.ok) {
    throw await parseError(response, 'No se pudo completar la solicitud.')
  }

  return (await response.json()) as TResponse
}

export function isAbortError(error: unknown): boolean {
  return (
    (error instanceof DOMException && error.name === 'AbortError') ||
    (error instanceof Error && error.name === 'AbortError')
  )
}
