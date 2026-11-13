const ROLE_STORAGE_KEY = 'user_role'

export function getStoredUserRole(): string | null {
  try {
    return window.localStorage.getItem(ROLE_STORAGE_KEY)
  } catch {
    return null
  }
}

export function setStoredUserRole(role: string | null): void {
  try {
    if (role) {
      window.localStorage.setItem(ROLE_STORAGE_KEY, role)
    } else {
      window.localStorage.removeItem(ROLE_STORAGE_KEY)
    }
  } catch {
    // Almacenamiento no disponible: se usará el destino seguro por defecto.
  }
}

export function isTechnician(): boolean {
  return getStoredUserRole() === 'tecnico'
}
