# Especificación: Seguimiento de la evolución del ticket (estado y línea temporal)

**Rama**: `002-ticket-timeline-history`

**Creado**: 2026-11-13

**Estado**: Borrador

**Entrada**: User description: "Ese mismo usuario, una vez abierto el ticket, querrá poder seguir su evolución sin tener que preguntar constantemente: consultar el estado en que se encuentra y revisar el historial completo, con una línea temporal que muestre cada cambio de estado y cada comentario que el técnico haya ido dejando."

## Resumen

El usuario que creó un ticket quiere conocer en cualquier momento el estado actual del ticket y revisar su historial visible (cambios de estado, resoluciones y comentarios públicos del técnico), sin tener que contactar al técnico para preguntar. Para ello, el sistema muestra el estado actual y una línea temporal cronológica que incluye cada cambio de estado del ticket y cada comentario público que el técnico haya dejado, con autor, fecha y hora de cada entrada.

Esta historia se centra en la consulta (lectura) del estado y el historial. Los cambios de estado, las resoluciones y los comentarios internos son escritos por el técnico dentro de HU-05; esta historia garantiza que el usuario pueda consultarlos.

## Clarifications

### Session 2026-11-13

- Q: ¿Qué comentarios del técnico puede ver el usuario creador en la línea temporal de su ticket: solo los comentarios públicos, todos los comentarios (incluidos los internos) o ninguno? → A: Solo los comentarios públicos; los comentarios internos del técnico quedan ocultos para el usuario creador.

## Actores

- **Usuario creador / solicitante**: consulta el estado actual y la línea temporal pública de sus propios tickets.
- **Técnico asignado**: escribe los cambios de estado, resoluciones y comentarios que el usuario consulta (alcance de escritura en HU-05).
- **Supervisor / administrador**: consulta la trazabilidad y el historial de los tickets.

## Reglas de Negocio

### RN-01 — Consulta del estado actual

- El usuario creador puede consultar el estado actual de cualquiera de sus propios tickets en cualquier momento.
- El estado mostrado es siempre el último estado registrado en el ticket.

### RN-02 — Línea temporal del ticket

- Cada cambio de estado genera una entrada en la línea temporal con: estado anterior, estado nuevo, autor y fecha y hora.
- Cada resolución genera una entrada de tipo «Resolución» con la descripción de la solución, el autor y la fecha y hora.
- Cada comentario del técnico genera una entrada en la línea temporal identificada como comentario, con el autor, el texto y la fecha y hora.
- La línea temporal se muestra en orden cronológico (de lo más antiguo a lo más reciente).
- Las entradas de la línea temporal no se pueden editar ni eliminar desde esta historia.

### RN-03 — Visibilidad de las entradas

- El usuario creador ve los cambios de estado y las resoluciones de sus tickets.
- El usuario creador ve únicamente los comentarios del técnico marcados como públicos en la línea temporal; los comentarios internos del técnico quedan ocultos para el usuario creador.

### RN-04 — Alcance de consulta

- El usuario solo puede consultar el estado y la línea temporal de los tickets que ha creado.
- Esta historia no permite al usuario cambiar estados, añadir comentarios ni editar entradas.

## Escenarios de Usuario y Pruebas

### Historia 1 — Consultar el estado actual del ticket (Prioridad: P1)

Como usuario creador, quiero ver el estado actual de mi ticket, para saber en qué fase se encuentra sin tener que preguntar al técnico.

**Por qué esta prioridad**: es la necesidad más directa del usuario; evitar llamadas o mensajes para preguntar el estado es el objetivo central de la historia.

**Prueba independiente**: partiendo de un ticket creado y asignado, el usuario accede a la vista del ticket y comprueba que el estado mostrado coincide con el último cambio registrado.

**Escenarios de aceptación**:

1. **Dado** un ticket en estado «En progreso», **cuando** el usuario creador consulta el ticket, **entonces** el sistema muestra «En progreso» como estado actual.
2. **Dado** un ticket en estado «Resuelto», **cuando** el usuario creador consulta el ticket, **entonces** el sistema muestra «Resuelto» como estado actual y, si existe, la resolución documentada.
3. **Dado** un ticket en estado «Cerrado», **cuando** el usuario creador consulta el ticket, **entonces** el sistema muestra «Cerrado» como estado actual.
4. **Dado** un ticket que no pertenece al usuario, **cuando** el usuario intenta consultar su estado, **entonces** el sistema deniega el acceso.

---

### Historia 2 — Revisar la línea temporal del ticket (Prioridad: P1)

Como usuario creador, quiero revisar el historial visible de mi ticket con una línea temporal, para ver cómo ha evolucionado y qué ha ido haciendo el técnico.

**Por qué esta prioridad**: da al usuario autonomía para hacer el seguimiento por su cuenta, reduciendo la necesidad de contactar al técnico.

**Prueba independiente**: el usuario abre el historial de un ticket con varios cambios de estado y comprueba que aparece una lista cronológica con cada cambio y cada comentario aplicable, con su autor, fecha y hora.

**Escenarios de aceptación**:

1. **Dado** un ticket con varios cambios de estado, **cuando** el usuario consulta la línea temporal, **entonces** el sistema muestra cada cambio con estado anterior, estado nuevo, autor y fecha y hora, en orden cronológico.
2. **Dado** un ticket con una resolución documentada, **cuando** el usuario consulta la línea temporal, **entonces** ve una entrada de tipo «Resolución» con la solución, el autor y la fecha y hora.
3. **Dado** un ticket con comentarios del técnico, **cuando** el usuario consulta la línea temporal, **entonces** ve los comentarios que corresponda según RN-03, identificados como comentarios, con su autor, texto y fecha y hora.
4. **Dado** un ticket sin cambios de estado ni comentarios, **cuando** el usuario consulta la línea temporal, **entonces** el sistema muestra un historial vacío o un mensaje indicando que no hay entradas.
5. **Dado** un ticket que no pertenece al usuario, **cuando** el usuario consulta la línea temporal, **entonces** el sistema deniega el acceso.

---

### Historia 3 — Identificar autor y fecha de cada entrada (Prioridad: P2)

Como usuario creador, quiero saber quién realizó cada cambio o comentario y cuándo, para valorar la antigüedad de cada entrada del historial.

**Por qué esta prioridad**: aporta trazabilidad y contexto temporal al seguimiento, aunque es secundario frente a ver el estado y el historial.

**Prueba independiente**: el usuario consulta la línea temporal y verifica que cada entrada muestra el autor y la fecha y hora.

**Escenarios de aceptación**:

1. **Dado** una entrada de la línea temporal, **cuando** el usuario la consulta, **entonces** ve el nombre o identificador del autor y la fecha y hora de la entrada.
2. **Dado** varias entradas, **cuando** el usuario las consulta, **entonces** cada una conserva su propio autor y fecha y hora independientes.

## Requisitos Funcionales

- **RF-001**: El sistema DEBE permitir al usuario creador consultar el estado actual de cada uno de sus propios tickets.
- **RF-002**: El sistema DEBE mostrar el estado actual como el último estado registrado en el ticket.
- **RF-003**: El sistema DEBE mostrar la línea temporal de un ticket en orden cronológico.
- **RF-004**: El sistema DEBE incluir en la línea temporal cada cambio de estado con estado anterior, estado nuevo, autor y fecha y hora.
- **RF-005**: El sistema DEBE incluir en la línea temporal cada resolución con la descripción de la solución, el autor y la fecha y hora.
- **RF-006**: El sistema DEBE incluir en la línea temporal los comentarios del técnico que correspondan según RN-03, identificados como comentarios, con autor, texto y fecha y hora.
- **RF-007**: El sistema DEBE denegar al usuario la consulta del estado y la línea temporal de tickets que no ha creado.
- **RF-008**: El sistema DEBE impedir al usuario, desde esta historia, cambiar estados, añadir comentarios o editar entradas de la línea temporal.
- **RF-009**: El sistema DEBE mostrar el autor y la fecha y hora en cada entrada de la línea temporal (cambio de estado, resolución o comentario público).
- **RF-010**: El sistema DEBE mostrar un mensaje claro cuando un ticket no tenga entradas en su línea temporal.

## Entidades Clave

- **Ticket**: número, título, descripción, estado actual, técnico asignado, usuario creador, fecha de creación.
- **Cambio de estado**: ticket afectado, estado anterior, estado nuevo, autor, fecha y hora.
- **Resolución**: ticket afectado, descripción de la solución, autor, fecha y hora.
- **Comentario del técnico**: ticket afectado, autor, texto, fecha y hora, visibilidad.
- **Entrada de línea temporal**: ticket afectado, tipo de entrada (cambio de estado, resolución o comentario), autor, fecha y hora, contenido y visibilidad.

## Casos Límite y Manejo de Errores

| Situación | Comportamiento esperado |
|---|---|
| Ticket sin cambios de estado ni comentarios | Se muestra un historial vacío o un mensaje indicando que no hay entradas. |
| Usuario consulta un ticket que no ha creado | Se deniega el acceso sin mostrar estado ni línea temporal. |
| Entrada de línea temporal sin autor registrado | Se muestra la entrada con el autor disponible o un indicador de «sistema». |
| Volumen grande de entradas en la línea temporal | El historial se paga para mantener el tiempo de respuesta bajo. |

## Criterios de Éxito

| ID | Métrica | Objetivo |
|---|---|---|
| SC-001 | Verifica RF-002: consultas del estado actual que muestran el último estado registrado | 100% |
| SC-002 | Verifica RF-003: entradas de la línea temporal mostradas en orden cronológico | 100% |
| SC-003 | Tiempo de respuesta para cargar el estado y la línea temporal | Menos de 2 segundos |
| SC-004 | Consultas de usuarios sobre tickets que no han creado denegadas | 100% |
| SC-005 | Usuarios que completan el seguimiento de la evolución sin contactar al técnico | Al menos 90% |
| SC-006 | Comentarios internos del técnico visibles para el usuario creador | 0 casos (según RN-03) |

## Supuestos

1. Los tickets ya existen con estado, técnico asignado y usuario creador, según las historias HU-01 y HU-02 del sistema base.
2. Los cambios de estado, resoluciones y comentarios son escritos por el técnico en HU-05; esta historia solo los consulta.
3. Cada ticket tiene un único usuario creador que puede consultar su estado y línea temporal.
4. La autenticación y los roles ya existen; esta historia no define el mecanismo de acceso.
5. Las fechas y horas se muestran en la zona horaria de España (Europe/Madrid) y se almacenan en UTC.
6. La línea temporal se paga cuando tiene muchas entradas.
7. Esta historia no incluye notificaciones automáticas al usuario ante cambios de estado.

## Fuera de Alcance

- Cambiar el estado del ticket desde la vista de consulta.
- Añadir, editar o eliminar comentarios o entradas de la línea temporal desde esta historia.
- Notificaciones al usuario por cambios de estado ni por nuevos comentarios.
- Estados personalizados o flujos configurables por categoría.
- Edición o eliminación de entradas existentes de la línea temporal.
- Descarga o exportación del historial en otros formatos.

## Dependencias

- HU-01: creación de tickets y asignación inicial (provee el ticket y su usuario creador).
- HU-05: cambio de estado, resolución y comentarios internos (provee las entradas de la línea temporal que esta historia consulta).
- RF-02: definición del flujo de estados del sistema.
- Sistema de autenticación y autorización por roles.
- Mecanismo de registro cronológico de la línea temporal del ticket.

## Trazabilidad de los Criterios de Aceptación

| Criterio de aceptación | Reglas de negocio | Requisitos funcionales |
|---|---|---|
| El usuario consulta el estado actual de su ticket | RN-01, RN-04 | RF-001, RF-002, RF-007 |
| El usuario revisa la línea temporal cronológica con cambios de estado | RN-02, RN-03, RN-04 | RF-003, RF-004, RF-007, RF-009, RF-010 |
| El usuario ve las resoluciones y los comentarios aplicables con autor y fecha | RN-02, RN-03 | RF-005, RF-006, RF-007, RF-009 |
| El usuario no puede modificar estados ni entradas desde la consulta | RN-04 | RF-008 |
