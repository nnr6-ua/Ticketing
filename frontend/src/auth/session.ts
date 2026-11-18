import { getStoredUserRole as getRoleFromToken } from '@/api/client'

export function getStoredUserRole(): string | null {
  return getRoleFromToken()
}

export function isTechnician(): boolean {
  return getStoredUserRole() === 'tecnico'
}
