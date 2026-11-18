export const WORK_QUEUE_PATH = '/cola-de-trabajo'
export const TICKET_CREATE_PATH = '/tickets/new'
export const MY_TICKETS_PATH = '/mis-tickets'
export const ADMIN_CONFIGURATION_PATH = '/admin/configuracion'
export const LOGIN_PATH = '/login'
export const SLA_DASHBOARD_PATH = '/dashboard-sla'

/** Destino inicial según el rol del usuario autenticado. */
export function landingForRole(role: string | null | undefined): string {
  if (role === 'usuario') return MY_TICKETS_PATH
  if (role === 'admin') return ADMIN_CONFIGURATION_PATH
  if (role === 'tecnico' || role === 'supervisor') return WORK_QUEUE_PATH
  return LOGIN_PATH
}

/** Comprueba que un `redirect` de login es compatible con el rol autenticado. */
export function isAllowedRedirect(path: string, role: string | null | undefined): boolean {
  if (!path.startsWith('/') || path.startsWith('//')) return false
  if (path === WORK_QUEUE_PATH) return role === 'tecnico' || role === 'supervisor'
  if (path === SLA_DASHBOARD_PATH) return role === 'supervisor' || role === 'admin'
  if (path === ADMIN_CONFIGURATION_PATH || path.startsWith(`${ADMIN_CONFIGURATION_PATH}/`)) {
    return role === 'admin'
  }
  if (path === MY_TICKETS_PATH || path.startsWith('/tickets/')) return true
  return false
}
