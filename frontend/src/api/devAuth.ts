import { apiPost } from '@/api/client'

export interface DevUser {
  id: string
  email: string
  name: string
  role: string
}

export interface DevLoginResponse {
  access_token: string
  token_type: string
  expires_in: number
  user: DevUser
}

/** `POST /api/v1/dev/login` (solo disponible con el stub de desarrollo). */
export function devLogin(email: string): Promise<DevLoginResponse> {
  return apiPost<DevLoginResponse, { email: string }>('/api/v1/dev/login', { email })
}
