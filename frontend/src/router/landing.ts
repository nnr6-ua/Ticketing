export const WORK_QUEUE_PATH = '/cola-de-trabajo'
export const TICKET_CREATE_PATH = '/tickets/new'
export const MY_TICKETS_PATH = '/mis-tickets'

/** Destino inicial según el rol del usuario autenticado. */
export function landingForRole(role: string | null | undefined): string {
  return role === 'usuario' ? MY_TICKETS_PATH : WORK_QUEUE_PATH
}
