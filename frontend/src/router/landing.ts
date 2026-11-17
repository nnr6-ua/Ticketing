export const WORK_QUEUE_PATH = '/cola-de-trabajo'
export const TICKET_CREATE_PATH = '/tickets/new'
export const MY_TICKETS_PATH = '/mis-tickets'
export const ADMIN_CONFIGURATION_PATH = '/admin/configuracion'

/** Destino inicial según el rol del usuario autenticado. */
export function landingForRole(role: string | null | undefined): string {
  if (role === 'usuario') return MY_TICKETS_PATH
  if (role === 'admin') return ADMIN_CONFIGURATION_PATH
  return WORK_QUEUE_PATH
}
