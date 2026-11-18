# Especificación Funcional: Reasignar o escalar ticket (HU-06)

**Rama**: `hu-06-reasignar-escalar`

**Creado**: 2026-11-10

**Estado**: Borrador

**Entrada**: HU-06 — «Reasignar o escalar ticket. Como técnico, quiero reasignar el ticket a otro técnico o escalarlo a un nivel superior, para que la persona adecuada se haga cargo y sea notificada de inmediato.»

> **Nota de consolidación**: esta especificación amplía la especificación existente con el módulo funcional de la HU-06 y conserva, sin alteraciones, todos los requisitos, escenarios, reglas de negocio y criterios de aceptación de los módulos previos HU-04 (cola de trabajo priorizada) y HU-05 (cambio de estado y documentación de resolución), que se reproducen íntegros al final del documento. El módulo HU-06 se integra con la arquitectura actual sin romper el carácter «append-only» e inmutable de la línea temporal de los tickets.

> **Convención de identificadores**: los códigos `RF-###`, `SC-###` y `RN-##` son locales a cada módulo funcional. Las definiciones y tablas de trazabilidad de este módulo usan el prefijo `HU06-` (`HU06-RF-001`, `HU06-SC-001`, `HU06-RN-01`); las referencias a módulos anteriores usan su prefijo (`HU04-`, `HU05-`). Las menciones sin prefijo dentro de una sección se interpretan en el ámbito de esa sección.

## Resumen

El técnico asignado a un ticket puede transferir su responsabilidad a otra persona de dos formas: reasignándolo a otro técnico de su equipo, cuando la persona adecuada es un compañero del mismo nivel, o escalándolo a un nivel superior de soporte (por ejemplo, «Nivel 2» o «Especialista»), cuando el caso requiere conocimientos o permisos más avanzados.

En ambos casos el técnico debe indicar un motivo, el cambio de responsable queda registrado de forma inmutable en la línea temporal del ticket con autor, motivo y fecha y hora, el nuevo responsable recibe una notificación inmediata dentro de la aplicación y el ticket pasa a formar parte de la cola de trabajo del nuevo responsable, desapareciendo de la del anterior.

La reasignación y el escalado no alteran el estado del ticket, ni su prioridad, ni su límite de SLA: únicamente cambia el responsable. El técnico anterior pierde la capacidad de modificar el ticket y deja de ver los comentarios internos, mientras que el nuevo responsable los incorpora a su contexto de trabajo.

## Clarifications

### Session 2026-11-10 (decisiones confirmadas mediante `/speckit.clarify`)

- Q: ¿Quién puede reasignar o escalar un ticket, además del técnico actualmente asignado? → A: Solo el técnico actualmente asignado, en consonancia con el modelo de permisos de HU-05 (HU05-RN-07). Si el usuario creador es además el técnico asignado, puede operar como responsable; si es técnico pero no está asignado, recibe `403 forbidden` con precedencia sobre `not_ticket_assignee`. Supervisores y administradores pueden consultar el ticket y su línea temporal, pero no ejecutan estas operaciones ni consultan las opciones de cambio de responsable (`GET /assignee-change-options`), que es una acción exclusiva del técnico asignado. (Confirmado en clarificación, 2026-11-10; precedencia precisada en la revisión de análisis, 2026-11-12.)
- Q: Al escalar a un nivel superior, ¿quién elige al nuevo responsable? → A: El técnico solo elige el nivel destino (siempre superior al del responsable actual) dentro del catálogo ordenado (Nivel 1, Nivel 2, Especialista); el sistema selecciona de forma determinista al nuevo responsable entre los técnicos activos de ese nivel, excluyendo al usuario creador del ticket. (Confirmado en clarificación, 2026-11-10.)
- Q: ¿El usuario creador del ticket debe ver el motivo de la reasignación o el escalado en la línea temporal? → A: Sí; la entrada de cambio de responsable es pública con el motivo visible para el usuario creador, igual que los cambios de estado y las resoluciones. El técnico redacta el motivo sabiendo que el creador podrá consultarlo. (Confirmado en clarificación, 2026-11-10.)
- Q: ¿Qué canal debe usar la «notificación inmediata» al nuevo responsable? → A: Solo la notificación dentro de la aplicación (campana con contador de no leídas), conforme a RF-08.1 del sistema. El correo electrónico y las notificaciones push quedan fuera del alcance y se rigen por RF-08.2. (Confirmado en clarificación, 2026-11-10.)
- Q: ¿Se puede reasignar o escalar un ticket en estados finales? → A: No; las operaciones solo se permiten en estados activos (Abierto, En progreso, Pendiente de usuario). (Valor por defecto documentado en la especificación; no requirió pregunta de clarificación.)
- Q: ¿Qué técnicos deben aparecer como candidatos cuando se reasigna un ticket? → A: Solo técnicos activos del mismo equipo y del mismo nivel de escalado que el responsable actual; el escalado a un nivel superior es la única vía para transferir el ticket por encima del nivel actual. (Confirmado en clarificación, 2026-11-10.)

## Actores

- **Técnico asignado**: único actor que puede reasignar o escalar el ticket; indica el destino y el motivo.
- **Técnico destino**: recibe la titularidad del ticket, su notificación en la aplicación y el ticket en su cola de trabajo.
- **Usuario creador**: consulta el ticket y ve el cambio de responsable en la línea temporal pública; no ejecuta ninguna acción de esta historia.
- **Supervisor/administrador**: puede consultar la trazabilidad de los cambios de responsable; no reasigna ni escala en esta historia.

## Escenarios de Usuario y Pruebas

### Historia 1 — Reasignar el ticket a otro técnico del equipo (Prioridad: P1)

Como técnico asignado, quiero transferir el ticket a otro técnico de mi equipo y de mi mismo nivel, para que la persona adecuada se haga cargo cuando yo no sea el correcto (vacaciones, carga, conocimiento del caso).

**Por qué esta prioridad**: es la operación básica de la historia; sin transferencia de responsabilidad entre técnicos no existe la funcionalidad.

**Prueba independiente**: partiendo de un ticket asignado en estado «En progreso», el técnico selecciona a un compañero del equipo en la lista de candidatos, escribe un motivo y confirma; el ticket cambia de responsable, aparece la entrada en la línea temporal y el compañero recibe la notificación.

**Escenarios de aceptación**:

1. **Dado** un ticket activo asignado al técnico, **cuando** abre la acción de reasignar, **entonces** el sistema muestra la lista de técnicos candidatos: técnicos activos de su mismo equipo y de su mismo nivel, excluyendo al propio responsable actual y al usuario creador del ticket.
2. **Dado** la lista de candidatos, **cuando** el técnico selecciona a un compañero, escribe un motivo y confirma, **entonces** el responsable del ticket pasa a ser el compañero seleccionado y el estado del ticket no cambia.
3. **Dado** una reasignación confirmada, **cuando** se consulta la línea temporal, **entonces** aparece una entrada de tipo «Cambio de responsable» con el técnico anterior, el nuevo responsable, el autor de la acción, el motivo y la fecha y hora.
4. **Dado** una reasignación confirmada, **cuando** el compañero consulte sus notificaciones, **entonces** encuentra una notificación del ticket reasignado, creada en la misma operación.
5. **Dado** una reasignación confirmada, **cuando** el compañero abre su cola de trabajo, **entonces** el ticket aparece en su cola y ya no aparece en la del técnico anterior en la siguiente actualización.

---

### Historia 2 — Escalar el ticket a un nivel superior (Prioridad: P1)

Como técnico asignado, quiero escalar el ticket a un nivel de soporte superior (Nivel 2 o Especialista), para que un técnico con más conocimientos o permisos se haga cargo del caso.

**Por qué esta prioridad**: el escalado es la segunda operación esencial de la historia y la razón de ser del catálogo de niveles; sin ella no existe diferenciación con una simple reasignación.

**Prueba independiente**: partiendo de un ticket asignado a un técnico de Nivel 1, el técnico elige «Nivel 2» como destino, escribe un motivo y confirma; el ticket pasa a un técnico de Nivel 2, la línea temporal registra el escalado y el nuevo responsable recibe la notificación.

**Escenarios de aceptación**:

1. **Dado** un ticket activo asignado a un técnico de Nivel 1, **cuando** abre la acción de escalar, **entonces** el sistema ofrece únicamente los niveles superiores al del responsable actual (Nivel 2 y Especialista), nunca el mismo nivel ni uno inferior.
2. **Dado** la lista de niveles, **cuando** el técnico elige «Nivel 2», escribe un motivo y confirma, **entonces** el responsable pasa a ser un técnico activo de Nivel 2, elegido por el sistema de forma determinista, y el estado del ticket no cambia.
3. **Dado** un escalado confirmado, **cuando** se consulta la línea temporal, **entonces** aparece una entrada de tipo «Cambio de responsable» identificada como escalado, con el nivel destino, el técnico anterior, el nuevo responsable, el autor, el motivo y la fecha y hora.
4. **Dado** un escalado confirmado, **cuando** el nuevo responsable consulte sus notificaciones, **entonces** encuentra una notificación del ticket escalado, creada en la misma operación.
5. **Dado** un ticket cuyo responsable ya pertenece al nivel máximo del catálogo, **cuando** el técnico intenta escalar, **entonces** el sistema indica que no existe un nivel superior disponible y no modifica el ticket.

---

### Historia 3 — Registrar el cambio de responsable en la línea temporal (Prioridad: P1)

Como técnico asignado, quiero que cada reasignación o escalado quede registrado en la línea temporal con autor y motivo, para que exista trazabilidad completa de quién ha tenido el ticket y por qué cambió de manos.

**Por qué esta prioridad**: la trazabilidad es un criterio de aceptación explícito y un requisito de auditoría del sistema; sin registro la transferencia no es verificable.

**Prueba independiente**: tras reasignar un ticket y consultarlo, la línea temporal muestra la entrada correspondiente en orden cronológico; reintentos y errores no generan entradas duplicadas ni parciales.

**Escenarios de aceptación**:

1. **Dado** cualquier reasignación o escalado confirmado, **cuando** se consulta la línea temporal, **entonces** la entrada muestra autor de la acción, responsable anterior, responsable nuevo, tipo de cambio (reasignación o escalado), motivo y fecha y hora.
2. **Dado** un ticket con varios cambios de responsable, **cuando** se consulta la línea temporal, **entonces** las entradas aparecen en orden cronológico junto al resto de hechos del ticket y ninguna se puede editar ni eliminar.
3. **Dado** un intento rechazado (motivo vacío, destino no válido, ticket cerrado), **cuando** la operación no se completa, **entonces** no se crea ninguna entrada en la línea temporal ni se modifica el responsable.
4. **Dado** un doble envío de la misma acción de reasignación o escalado, **cuando** la operación es idempotente, **entonces** solo se registra un cambio de responsable y una entrada en la línea temporal.
5. **Dado** el usuario creador del ticket, **cuando** consulta la línea temporal, **entonces** ve las entradas de cambio de responsable junto con los cambios de estado y las resoluciones, pero no los comentarios internos.

---

### Historia 4 — Notificar al nuevo responsable y trasladar el ticket a su cola (Prioridad: P1)

Como técnico asignado, quiero que la persona que recibe el ticket se entere de inmediato y lo tenga en su cola de trabajo, para que el traspaso no deje el ticket en un limbo.

**Por qué esta prioridad**: la notificación y el traslado a la cola cierran el ciclo de la transferencia; sin ellos el nuevo responsable podría no enterarse.

**Prueba independiente**: tras reasignar o escalar, el nuevo responsable recibe una notificación en la aplicación en el plazo definido y el ticket aparece en su cola de trabajo ordenado según las reglas de la HU-04.

**Escenarios de aceptación**:

1. **Dado** una reasignación o escalado confirmado, **cuando** la operación se completa, **entonces** se crea en la misma operación una notificación en la aplicación dirigida al nuevo responsable.
2. **Dado** una notificación creada, **cuando** el nuevo responsable tiene la aplicación abierta, **entonces** la ve en su campana de notificaciones dentro del plazo máximo definido, con el número de ticket y el tipo de cambio.
3. **Dado** una notificación recibida, **cuando** el nuevo responsable la abre, **entonces** accede al ticket y la notificación queda marcada como leída.
4. **Dado** un ticket recién reasignado o escalado, **cuando** el nuevo responsable abre su cola de trabajo, **entonces** el ticket aparece en su cola, ordenado y con sus datos según las reglas de la HU-04, y desaparece de la cola del técnico anterior en la siguiente actualización.
5. **Dado** el técnico anterior con el detalle del ticket abierto, **cuando** el ticket ya no es suyo, **entonces** el sistema le impide cambiar el estado, añadir comentarios internos o volver a reasignar, y le indica que el ticket ya no está asignado a él.

---

### Historia 5 — Aclarar quién puede reasignar y en qué estados (Prioridad: P2)

Como responsable del servicio, quiero que solo el técnico asignado pueda reasignar o escalar y solo en estados activos, para que la propiedad del ticket esté siempre clara y los tickets finalizados no cambien de manos.

**Por qué esta prioridad**: protege la integridad de la propiedad del ticket y de los estados finales; es una salvaguarda del flujo, no una capacidad nueva para el usuario.

**Prueba independiente**: con un ticket cerrado y con usuarios de cada rol, se comprueba que todas las operaciones no permitidas se rechazan sin modificar el ticket ni crear entradas.

**Escenarios de aceptación**:

1. **Dado** un usuario creador, supervisor o administrador, **cuando** intenta reasignar o escalar, **entonces** el sistema deniega la operación sin modificar el ticket.
2. **Dado** un técnico distinto del responsable actual, **cuando** intenta reasignar o escalar, **entonces** el sistema deniega la operación indicando que el ticket no está asignado a él, salvo que se trate del replay idéntico de HU06-RN-13, que no escribe.
3. **Dado** un ticket en estado «Resuelto» o «Cerrado», **cuando** el técnico asignado intenta reasignar o escalar, **entonces** el sistema rechaza la operación y el responsable no cambia.
4. **Dado** un ticket en estado «Pendiente de usuario», **cuando** el técnico asignado lo reasigna o escala, **entonces** la operación se permite, el estado se mantiene y, cuando el usuario creador responda conforme a la HU-03, la transición resultante la gestiona el nuevo responsable.

## Reglas de Negocio

### HU06-RN-01 — Operaciones de cambio de responsable

Existen dos operaciones que cambian el responsable del ticket:

- **Reasignación**: transferencia a un técnico concreto elegido de la lista de candidatos.
- **Escalado**: transferencia a un nivel de escalado superior; el responsable concreto lo selecciona el sistema de forma determinista.

Ambas operaciones son exclusivas del técnico actualmente asignado, exigen motivo y se registran como una entrada de «Cambio de responsable» en la línea temporal.

### HU06-RN-02 — Catálogo y orden de niveles de escalado

- El catálogo de niveles de escalado es fijo y ordenado: **Nivel 1** (nivel base, por defecto) < **Nivel 2** < **Especialista**.
- Todo técnico pertenece exactamente a un nivel. Los técnicos existentes antes de esta funcionalidad se consideran de Nivel 1.
- La asignación y modificación del nivel de cada técnico se gestiona fuera de esta historia (administración de usuarios).

### HU06-RN-03 — Candidatos de reasignación

- Los candidatos de reasignación son usuarios con rol técnico, activos, del mismo equipo que el responsable actual y del mismo nivel de escalado que el responsable actual.
- Si el responsable actual no tiene equipo definido, los candidatos son todos los técnicos activos de su mismo nivel, con independencia del equipo.
- El responsable actual y el usuario creador del ticket nunca aparecen como candidatos.
- El responsable actual no puede reasignarse el ticket a sí mismo.

### HU06-RN-04 — Selección determinista del responsable en el escalado

Al escalar a un nivel destino, el sistema elige al nuevo responsable entre los técnicos activos de ese nivel, excluyendo al usuario creador del ticket, aplicando en orden:

1. Preferencia por los técnicos del mismo equipo que el responsable actual; si no hay ninguno, se considera todo el pool de técnicos activos del nivel.
2. Menor número de tickets activos asignados (carga activa).
3. En caso de empate, orden alfabético ascendente por nombre, sin distinguir mayúsculas ni minúsculas (`lower(name)`).
4. Si persiste el empate, `User.id` ascendente como desempate final.

La selección es determinista: ante el mismo estado del sistema produce siempre el mismo resultado. Si no existe ningún técnico activo en el nivel destino que pueda recibir el ticket (excluido el usuario creador), la operación se rechaza sin modificar el ticket.

### HU06-RN-05 — Motivo obligatorio

- Toda reasignación o escalado exige un motivo de entre 1 y 5.000 caracteres una vez eliminados los espacios al inicio y al final.
- Se considera vacío un motivo compuesto solo por espacios, tabuladores o saltos de línea.
- El motivo queda registrado en la entrada de la línea temporal y no se puede editar ni eliminar una vez guardado.

### HU06-RN-06 — Estados permitidos y efecto sobre el flujo

- La reasignación y el escalado solo se permiten en estados activos: «Abierto», «En progreso» y «Pendiente de usuario».
- En «Resuelto» y «Cerrado» ambas operaciones se rechazan sin modificar el ticket.
- Ni la reasignación ni el escalado cambian el estado del ticket, ni su prioridad, ni su categoría, ni su límite de SLA.
- La matriz de transiciones de estados de la HU-05 (HU05-RN-02) no se modifica: el cambio de responsable no es una transición de estado y no crea entradas de tipo cambio de estado.

### HU06-RN-07 — Trazabilidad e inmutabilidad de la línea temporal

- Cada cambio de responsable genera una entrada de tipo «Cambio de responsable» con: autor de la acción, responsable anterior, responsable nuevo, tipo de cambio (reasignación o escalado), nivel de escalado implicado, motivo y fecha y hora.
- Las entradas de la línea temporal son «append-only»: no se pueden editar ni eliminar, y mantienen el orden cronológico.
- La entrada de cambio de responsable es pública: visible para el usuario creador y para el personal interno, conforme a la visibilidad de la línea temporal de la HU-02.
- Los intentos rechazados no generan entradas.

### HU06-RN-08 — Notificación inmediata al nuevo responsable

- Cada reasignación o escalado confirmado genera una notificación en la aplicación dirigida al nuevo responsable, creada en la misma operación que el cambio.
- La notificación identifica el ticket (número y título), el tipo de cambio y el responsable anterior.
- La notificación se marca como leída cuando el nuevo responsable la consulta; hasta entonces se contabiliza como no leída.
- La notificación se entrega dentro de la aplicación; el correo electrónico y las notificaciones push quedan fuera del alcance (RF-08.2).
- Solo el nuevo responsable recibe notificación; el técnico anterior y el usuario creador no reciben ninguna en esta historia.

### HU06-RN-09 — Traslado entre colas de trabajo

- Al confirmar el cambio, el ticket pasa a ser propiedad del nuevo responsable a todos los efectos de la cola de trabajo de la HU-04 (HU04-RN-01 y HU04-RN-12).
- El ticket aparece en la cola del nuevo responsable y desaparece de la del anterior en la siguiente actualización de la cola (máximo 60 segundos).
- La prioridad, el tiempo restante de SLA y el orden de la cola del nuevo responsable se calculan con las reglas de la HU-04, sin excepciones por tratarse de un traspaso.

### HU06-RN-10 — Pérdida de permisos del técnico anterior

- El técnico anterior deja de poder cambiar el estado, añadir comentarios internos, reasignar o escalar el ticket (HU05-RN-07), salvo el replay idéntico de HU06-RN-13, que no escribe.
- El técnico anterior deja de ver los comentarios internos del ticket; el nuevo responsable pasa a verlos, conforme a HU05-RN-06.
- El técnico anterior conserva el acceso de lectura a la línea temporal pública del ticket.

### HU06-RN-11 — Permisos

- Solo el técnico actualmente asignado puede ejecutar la reasignación o el escalado. Si el usuario creador es además el técnico asignado vigente, actúa en su capacidad de responsable y puede operar; como creador sigue excluido como destino de la reasignación y del pool de escalado.
- La comprobación se aplica en este orden y de forma excluyente: (1) si el actor no tiene rol técnico (incluidos supervisores y administradores) ⇒ `403 forbidden`; (2) si el actor tiene rol técnico, no es el responsable vigente y es el usuario creador ⇒ `403 forbidden`, con precedencia sobre la comprobación de asignación; (3) si el actor tiene rol técnico pero no es el responsable vigente ⇒ `403 not_ticket_assignee`.
- El usuario creador que no sea el técnico asignado, los supervisores y los administradores no ejecutan estas operaciones ni consultan el endpoint de opciones en esta historia.
- La autorización se evalúa siempre en el servidor contra el responsable vigente en el momento de la operación. La única excepción es el replay idempotente definido en HU06-RN-13, que no modifica el ticket ni crea evidencia.

### HU06-RN-12 — Atomicidad

- El cambio de responsable, la entrada de la línea temporal y la notificación al nuevo responsable se guardan como una única operación.
- Si falla cualquier validación o el guardado no puede completarse, no persiste ningún cambio parcial: ni el responsable, ni la entrada de la línea temporal, ni la notificación.

### HU06-RN-13 — Idempotencia y concurrencia

- Cada reasignación o escalado exige un identificador de solicitud (`request_id`) establecido por el cliente, que actúa como clave de idempotencia, en línea con HU05-RN-04.
- Un reintento idéntico con el mismo `request_id` no escribe y devuelve un resultado indicando que no hubo cambios.
- **Excepción de replay**: el reintento idéntico definido en el punto anterior se admite aunque el actor haya dejado de ser el responsable vigente, siempre que coincidan actor, tipo, destino y motivo normalizado; no escribe ni crea entradas ni notificaciones. Cualquier solicitud nueva o con datos distintos exige asignación vigente.
- **Definición de "otros datos" para idempotencia**: se considera "otros datos" que cualquier campo difiera después de `strip()` en el motivo. Mismo actor + mismo `change_kind` + mismo `new_assignee_id` + razón normalizada ⇒ idempotente (200 `changed=false`). Cualquier diferencia en actor, tipo, destino o motivo ⇒ `409 request_id_reused`.
- La reutilización de un `request_id` con distintos datos se rechaza con un error de conflicto.
- La operación exige la versión esperada del ticket (`expected_updated_at`); si el ticket cambió entre la lectura y el envío, se rechaza y se solicita actualizar la información, sin modificar el ticket.

### HU06-RN-14 — Selección de destino válida

- La reasignación se rechaza si el técnico destino no existe, no está activo, no tiene rol técnico, no pertenece al mismo equipo y nivel que el responsable actual conforme a RN-03, es el propio responsable o es el usuario creador del ticket.
- El escalado se rechaza si el nivel destino no es superior al del responsable actual o si no hay técnicos activos en ese nivel que puedan recibir el ticket (excluido el usuario creador).
- Los candidatos y niveles ofrecidos en la interfaz se recalculan en el momento de la operación; un destino válido al abrir el formulario puede dejar de serlo al confirmar.

## Requisitos Funcionales

### Reasignación

- **HU06-RF-001**: El sistema DEBE permitir al técnico actualmente asignado reasignar el ticket a otro técnico candidato conforme a RN-03.
- **HU06-RF-002**: El sistema DEBE mostrar la lista de candidatos de reasignación con nombre y equipo de cada técnico, excluyendo al responsable actual y al usuario creador del ticket.
- **HU06-RF-003**: El sistema DEBE exigir un motivo de entre 1 y 5.000 caracteres en toda reasignación.
- **HU06-RF-004**: El sistema DEBE rechazar la reasignación cuando el destino no cumpla RN-03 o RN-14, manteniendo el responsable original y sin crear entradas en la línea temporal.
- **HU06-RF-005**: El sistema DEBE impedir que el técnico se reasigne el ticket a sí mismo.

### Escalado

- **HU06-RF-006**: El sistema DEBE permitir al técnico actualmente asignado escalar el ticket a un nivel de escalado superior al del responsable actual, conforme a RN-02.
- **HU06-RF-007**: El sistema DEBE ofrecer únicamente niveles de destino superiores al nivel del responsable actual.
- **HU06-RF-008**: El sistema DEBE seleccionar al nuevo responsable del escalado conforme a la regla determinista de RN-04.
- **HU06-RF-009**: El sistema DEBE rechazar el escalado cuando el responsable actual pertenezca al nivel máximo del catálogo, indicando que no existe un nivel superior.
- **HU06-RF-010**: El sistema DEBE rechazar el escalado cuando no exista ningún técnico activo en el nivel destino que pueda recibir el ticket (excluido el usuario creador), sin modificar el ticket.

### Registro en la línea temporal

- **HU06-RF-011**: El sistema DEBE registrar cada cambio de responsable como una entrada de la línea temporal con autor, responsable anterior, responsable nuevo, tipo de cambio, nivel de escalado implicado, motivo y fecha y hora.
- **HU06-RF-012**: El sistema DEBE distinguir en la línea temporal las reasignaciones de los escalados, y ambas de los cambios de estado, las resoluciones y los comentarios internos.
- **HU06-RF-013**: El sistema DEBE mostrar el cambio de responsable en la línea temporal en orden cronológico y en menos de 2 segundos tras confirmar la operación.
- **HU06-RF-014**: El sistema DEBE impedir la edición y la eliminación de una entrada de cambio de responsable una vez guardada.
- **HU06-RF-015**: El sistema DEBE mostrar las entradas de cambio de responsable al usuario creador del ticket junto con los cambios de estado y las resoluciones, sin mostrarle los comentarios internos.

### Notificación al nuevo responsable

- **HU06-RF-016**: El sistema DEBE crear una notificación en la aplicación dirigida al nuevo responsable en la misma operación que el cambio de responsable.
- **HU06-RF-017**: La notificación DEBE identificar el ticket (número y título), el tipo de cambio (reasignación o escalado) y el responsable anterior.
- **HU06-RF-018**: El sistema DEBE mostrar al nuevo responsable sus notificaciones no leídas en la campana de notificaciones dentro de un plazo máximo de 30 segundos desde la creación.
- **HU06-RF-019**: El sistema DEBE permitir al nuevo responsable marcar la notificación como leída al consultarla.
- **HU06-RF-020**: El sistema DEBE conservar la notificación hasta que se marque como leída, también si el nuevo responsable está desconectado en el momento del cambio.

### Cola de trabajo y permisos

- **HU06-RF-021**: El sistema DEBE hacer que el ticket pase a la cola de trabajo del nuevo responsable en la siguiente actualización (máximo 60 segundos), ordenado conforme a las reglas de la HU-04.
- **HU06-RF-022**: El sistema DEBE hacer que el ticket desaparezca de la cola de trabajo del técnico anterior en la siguiente actualización (máximo 60 segundos).
- **HU06-RF-023**: El sistema DEBE impedir que el técnico anterior cambie el estado, añada comentarios internos, reasigne o escale el ticket tras el traspaso, indicándole que el ticket ya no está asignado a él, salvo el replay idéntico de HU06-RF-029, que no modifica el ticket.
- **HU06-RF-024**: El sistema DEBE permitir las operaciones de esta historia únicamente al técnico actualmente asignado al ticket, salvo el replay idéntico de HU06-RF-029, que devuelve el resultado original sin escribir.
- **HU06-RF-025**: El sistema DEBE denegar la operación cuando el usuario no tenga permiso o el ticket no esté asignado a él, con los mensajes del catálogo de errores definido en el plan de esta historia.
- **Cross-reference**: Reglas de autorización compatibles con RN-10 y RN-11 del plan: rol no técnico ⇒ `403 forbidden`; creador técnico no asignado ⇒ `forbidden` con precedencia sobre `not_ticket_assignee`; creador asignado vigente ⇒ puede operar; técnico anterior no creador ⇒ `not_ticket_assignee`. Ver también RN-10 y RN-11 para reglas de autorización.
- **HU06-RF-026**: El sistema DEBE impedir la reasignación y el escalado de tickets en estados «Resuelto» y «Cerrado».
- **HU06-RF-027**: El sistema DEBE mantener el estado, la prioridad, la categoría y el límite de SLA del ticket sin cambios tras una reasignación o escalado.

### Consistencia, idempotencia y errores

- **HU06-RF-028**: El sistema DEBE guardar el cambio de responsable, la entrada de la línea temporal y la notificación como una única operación, sin persistir cambios parciales ante errores.
- **HU06-RF-029**: El sistema DEBE evitar cambios duplicados cuando el técnico envíe dos veces la misma acción: el `request_id` es obligatorio, un reintento idéntico no escribe y la reutilización con distintos datos se rechaza con un error de conflicto.
- **HU06-RF-030**: El sistema DEBE detectar y rechazar cambios realizados sobre una versión desactualizada del ticket, solicitando su actualización.
- **HU06-RF-031**: El sistema DEBE mantener el ticket sin cambios ante cualquier error de validación, permisos, destino no válido o concurrencia.
- **HU06-RF-032**: El sistema DEBE mostrar mensajes de error en español de España, comprensibles y sin tecnicismos, con códigos estables, conforme al formato de errores del sistema.
- **HU06-RF-033**: El sistema DEBE mantener la coherencia entre el responsable mostrado en el ticket y el último cambio de responsable registrado en la línea temporal.

### Notas de integración (informativas, no normativas)

Estas notas orientan el plan (`plan.md`) de esta historia y no añaden requisitos:

- La línea temporal se extiende de forma aditiva: se amplía el catálogo de tipos de entrada con «Cambio de responsable» y se añaden columnas anulables para el responsable anterior, el responsable nuevo y el tipo de cambio, con restricciones que no afecten a las entradas existentes. El carácter «append-only» e inmutable de la tabla se conserva.
- El nivel de escalado se incorpora como atributo del técnico con valor por defecto «Nivel 1», mediante migración aditiva verificable sobre PostgreSQL; el catálogo de niveles es fijo en esta versión.
- Las notificaciones en la aplicación se materializan como una tabla nueva de notificaciones por usuario, vinculada al ticket, sin alterar tablas existentes.
- Los comandos de cambio de responsable se modelan como recursos POST, sin alterar los endpoints existentes de la HU-05, cuya matriz de estados, permisos e idempotencia permanecen intactos.
- El frontend reutiliza la vista de detalle del ticket y la cola de trabajo existentes: un panel de reasignación/escalado en el detalle, una campana de notificaciones en la cabecera y la actualización de la cola ya gobernada por la HU-04, sin duplicar su lógica.

## Entidades Clave

- **Cambio de responsable**: ticket afectado, autor de la acción, responsable anterior, responsable nuevo, tipo de cambio (reasignación o escalado), nivel de escalado implicado, motivo y fecha y hora; queda vinculado a una entrada de la línea temporal.
- **Nivel de escalado**: nivel de soporte del técnico dentro del catálogo ordenado (Nivel 1, Nivel 2, Especialista); determina qué escalados son posibles.
- **Técnico**: usuario con rol técnico, equipo y nivel de escalado; es candidato de reasignación y destino posible del escalado.
- **Notificación**: mensaje en la aplicación dirigido al nuevo responsable, con el ticket, el tipo de cambio, el estado de lectura y la fecha y hora.
- **Ticket**: incorpora la noción de responsable actual, único propietario de la cola de trabajo y único autorizado a ejecutar las operaciones de esta historia.
- **Entrada de línea temporal**: se amplía con el tipo «Cambio de responsable» y los datos de responsable anterior y nuevo, manteniendo la inmutabilidad.

## Casos Límite y Manejo de Errores

| Situación | Comportamiento esperado | Mensaje orientativo |
|---|---|---|
| Se intenta reasignar el ticket a sí mismo | Se bloquea la operación; el responsable no cambia. | «No puedes reasignarte el ticket a ti mismo.» |
| El motivo está vacío o solo contiene espacios | Se bloquea la operación sin cambios ni entradas. | «Indica el motivo del cambio de responsable.» |
| El motivo supera los 5.000 caracteres | Se bloquea la operación y se conserva el responsable. | «El motivo no puede superar los 5.000 caracteres.» |
| Se intenta reasignar a un técnico de otro equipo o de otro nivel | Se bloquea la operación sin cambios. | «Solo puedes reasignar a técnicos de tu equipo y de tu nivel.» |
| El técnico destino se desactiva entre abrir el formulario y confirmar | Se rechaza la operación sin modificar el ticket. | «El técnico seleccionado ya no está disponible. Actualiza la lista e inténtalo de nuevo.» |
| No hay técnicos activos en el nivel destino (excluyendo al usuario creador) | Se rechaza la operación sin modificar el ticket. | «No hay técnicos disponibles en ese nivel en este momento. Si el usuario creador es técnico, ofrece escalado al siguiente nivel o mantiene ticket asignado.» |
| Se selecciona al usuario creador del ticket como destino | No aparece como candidato y la operación directa se rechaza. | «Ese usuario no puede recibir este ticket.» |
| Se intenta escalar desde el nivel máximo («Especialista») | Se rechaza la operación indicando que no hay nivel superior. | «El ticket ya está en el nivel máximo de soporte.» |
| El nivel destino no tiene ningún técnico activo distinto del usuario creador | Se rechaza la operación sin modificar el ticket. | «No hay técnicos disponibles en ese nivel en este momento.» |
| El ticket está «Resuelto» o «Cerrado» | Se rechaza la operación; los tickets finalizados no cambian de responsable. | «El ticket está finalizado y no admite cambios de responsable.» |
| Un usuario creador, supervisor o administrador intenta reasignar o escalar | Se deniega la operación sin modificar el ticket. | «No tienes permiso para modificar este ticket.» |
| Un técnico no asignado intenta reasignar o escalar | Se deniega la operación, salvo el replay idéntico de HU06-RN-13, que no escribe. | «Este ticket ya no está asignado a ti.» |
| El ticket fue reasignado mientras el técnico anterior tenía la vista abierta | Se rechazan sus acciones y se le pide actualizar la información. | «El ticket ha sido modificado por otra persona. Actualiza la información e inténtalo de nuevo.» |
| Se pulsa dos veces seguidas «Confirmar» | Solo se registra un cambio de responsable, una entrada y una notificación. | No requiere mensaje de error. |
| Se reutiliza el `request_id` con otros datos | Se rechaza sin modificar el ticket ni la línea temporal. | «La solicitud ya se utilizó con otros datos. Genera una nueva solicitud e inténtalo de nuevo.» |
| Falta el `request_id` o no es un UUID válido | Se rechaza la operación sin modificar el ticket. | «La solicitud no es válida. Revisa los datos e inténtalo de nuevo.» |
| Se produce un fallo al guardar el cambio | No se modifica el responsable, ni la línea temporal, ni se crea la notificación; el técnico puede reintentar. | «No se pudo guardar el cambio. El ticket no se ha modificado. Inténtalo de nuevo.» |
| El ticket no existe o no se puede consultar | Se muestra un error y no se realiza ningún cambio. | «No se ha encontrado el ticket.» |
| El nuevo responsable está desconectado al producirse el cambio | La notificación queda pendiente y disponible al reconectarse. | No aplica. |
| Varios técnicos del nivel destino empatan en carga activa | El desempate alfabético por nombre determina la selección de forma estable. | No aplica. |
| Se reasigna un ticket «Pendiente de usuario» | La operación se permite, el estado se mantiene y la respuesta del creador la gestiona el nuevo responsable conforme a la HU-03. | No requiere mensaje de error. |
| El técnico anterior consulta el detalle tras el traspaso | Ve la línea temporal pública, no los comentarios internos, y no puede ejecutar acciones. | «Este ticket ya no está asignado a ti.» |
| El cambio de responsable coincide con otras escrituras simultáneas | La operación que llega segundo se rechaza por versión desactualizada, sin sobrescribir la primera. | «El ticket ha sido modificado por otra persona. Actualiza la información e inténtalo de nuevo.» |

## Criterios de Éxito

| ID | Métrica | Objetivo |
|---|---|---|
| HU06-SC-001 | Cambios de responsable registrados en la línea temporal con autor y motivo | 100% de las operaciones confirmadas |
| HU06-SC-002 | Entradas de cambio de responsable visibles en la línea temporal | 100% en menos de 2 segundos |
| HU06-SC-003 | Nuevos responsables con notificación creada en la misma operación | 100% de los cambios confirmados |
| HU06-SC-004 | Notificaciones visibles en la campana del nuevo responsable | En 30 segundos o menos |
| HU06-SC-005 | Tickets trasladados a la cola del nuevo responsable | 100% en la siguiente actualización (máximo 60 segundos) |
| HU06-SC-006 | Cambios de responsable sin motivo o con motivo vacío | 0 casos |
| HU06-SC-007 | Escalados a un nivel igual o inferior al del responsable anterior | 0 casos |
| HU06-SC-008 | Cambios de responsable en tickets «Resuelto» o «Cerrado» | 0 casos |
| HU06-SC-009 | Entradas duplicadas por doble envío | 0 casos |
| HU06-SC-010 | Tiempo para reasignar o escalar un ticket | Menos de 300 ms p95 en servidor (objetivo plan.md) |
| HU06-SC-011 | Técnicos que completan la reasignación o el escalado en el primer intento | Al menos 95% |

## Supuestos

1. El sistema ya dispone de tickets con responsable, usuario creador, cola de trabajo y línea temporal, según HU-01 a HU-05.
2. La autenticación y los roles ya existen; esta historia no define el mecanismo de acceso.
3. Cada ticket tiene un único técnico responsable en cada momento.
4. El catálogo de niveles de escalado es fijo en esta versión (Nivel 1, Nivel 2, Especialista) y su gestión (asignar niveles a técnicos) pertenece a la administración de usuarios, fuera del alcance.
5. Los técnicos existentes antes de esta funcionalidad se consideran de Nivel 1.
6. El campo de equipo del técnico ya existe; los técnicos sin equipo participan en el pool general de su nivel.
7. La entrada de cambio de responsable es pública: el usuario creador la ve, incluido el motivo; el técnico la escribe sabiendo esto.
8. La notificación inmediata se entrega dentro de la aplicación (campana); el correo electrónico y las notificaciones push quedan fuera del alcance y se rigen por RF-08.2.
9. La reasignación y el escalado no alteran el estado, la prioridad, la categoría ni el límite de SLA del ticket.
10. Las fechas y horas se muestran en la zona horaria de España (Europe/Madrid) y se almacenan en UTC.
11. Las notificaciones de esta historia se dirigen únicamente al nuevo responsable.
12. El usuario creador del ticket no es candidato de reasignación ni de escalado, aunque tenga rol técnico.
13. La reasignación se restringe a técnicos del mismo equipo y nivel que el responsable actual; para pasar el ticket a un nivel superior existe el escalado.
14. La visibilidad de los comentarios internos tras el traspaso se rige por la HU-05 (HU05-RN-06 y HU05-RN-07).

## Fuera de Alcance

- Reasignación o escalado masivo de varios tickets a la vez.
- Escalado a equipos externos, proveedores o terceros.
- Notificaciones por correo electrónico o push (se rigen por RF-08.2).
- Cambio de prioridad, categoría o límite de SLA al reasignar o escalar.
- Escalado automático por incumplimiento de SLA o por reglas de enrutamiento.
- Gestión de niveles de escalado por parte de administradores (alta, edición, orden del catálogo).
- Reasignación o escalado de tickets en estados finales («Resuelto», «Cerrado»).
- Bajada de nivel («de-escalado») del ticket.
- Colas de equipo compartidas o asignación múltiple.
- Aceptación o rechazo del traspaso por parte del nuevo responsable.

## Dependencias

- HU-01: creación de tickets y asignación inicial.
- HU-02: consulta del estado y línea temporal del ticket.
- HU-03: respuesta del usuario creador y transición automática desde «Pendiente de usuario», que gestiona el nuevo responsable tras el traspaso.
- HU-04: cola de trabajo priorizada y sus reglas de propiedad y refresco (HU04-RN-01, HU04-RN-12 y HU04-FR-005).
- HU-05: línea temporal «append-only», matriz de estados, permisos del técnico asignado e idempotencia (HU05-RN-02, HU05-RN-04, HU05-RN-06, HU05-RN-07).
- RF-03 del sistema: asignación y escalado de tickets.
- RF-08.1 del sistema: notificaciones dentro de la aplicación.
- Sistema de autenticación y autorización por roles.

## Trazabilidad de los Criterios de Aceptación

| Criterio de aceptación de HU-06 | Reglas de negocio | Requisitos funcionales |
|---|---|---|
| El técnico puede seleccionar otro técnico de la lista del equipo para reasignar. | HU06-RN-01, HU06-RN-03, HU06-RN-14 | HU06-RF-001 (RF-005 fusionada a RF-001), HU06-RF-024 a HU06-RF-026 |
| El técnico puede escalar a un nivel superior (ej: «Nivel 2», «Especialista»). | HU06-RN-01, HU06-RN-02, HU06-RN-04, HU06-RN-14 | HU06-RF-006 a HU06-RF-010, HU06-RF-024 a HU06-RF-026 |
| Al reasignar/escalar, el nuevo responsable recibe notificación inmediata. | HU06-RN-08, HU06-RN-12 | HU06-RF-016 a HU06-RF-020, HU06-RF-028 |
| El cambio de responsable queda registrado en la línea temporal con autor y motivo. | HU06-RN-05, HU06-RN-07, HU06-RN-13 | HU06-RF-011 a HU06-RF-015, HU06-RF-029, HU06-RF-030 |
| El ticket pasa a la cola de trabajo del nuevo responsable. | HU06-RN-09, HU06-RN-10, HU06-RN-12 | HU06-RF-021 a HU06-RF-023, HU06-RF-031, HU06-RF-033 |
| Solo el técnico asignado puede reasignar o escalar, y solo en estados activos. | HU06-RN-06, HU06-RN-11 | HU06-RF-024 a HU06-RF-026 |

---

# Módulo HU-04: Cola de Trabajo Priorizada (conservado íntegro)

> Contenido conservado sin cambios respecto a `specs/004-prioritized-work-queue/spec.md`. No se ha modificado ningún requisito, escenario, regla de negocio ni criterio de aceptación.

# Especificación de Funcionalidad: Cola de Trabajo Priorizada (HU-04)

**Rama**: `hu-04-cola-trabajo`

**Creado**: 2026-10-29

**Estado**: Borrador

**Entrada**: Descripción del usuario: "Ver cola de trabajo priorizada. El técnico ve solo los tickets que tiene asignados. La lista muestra número de ticket, título/resumen, categoría, prioridad y tiempo restante hasta el límite SLA. El orden por defecto prioriza mayor prioridad primero y, dentro de la misma prioridad, menor tiempo restante primero. Se destacan visualmente los tickets próximos a incumplir su plazo. El técnico puede filtrar por estado y prioridad. Incluir reglas de negocio claras (SLA ya incumplido) y casos límite (ningún ticket asignado)."

## Resumen

El técnico de la mesa de ayuda dispone de una vista personal, denominada cola de trabajo, que reúne exclusivamente los tickets asignados a él y los presenta ordenados por urgencia. La urgencia combina la prioridad del ticket y el tiempo que queda hasta su límite de SLA, de forma que el técnico identifique de un vistazo qué debe atender primero, qué está a punto de incumplir su plazo y qué ya lo ha incumplido.

La vista permite además acotar el listado por estado y por prioridad, manteniendo el orden por urgencia dentro del subconjunto filtrado. Esta funcionalidad no modifica tickets: es una vista de consulta y priorización que sirve de punto de partida para el trabajo diario del técnico.

## Clarifications

### Session 2026-10-29

- Q: Cuando el técnico filtra por un estado final (Resuelto o Cerrado), ¿cómo debe mostrarse el dato del SLA en esos tickets? → A: Mostrar el resultado histórico ("Dentro de plazo" o "Incumplido hace [tiempo]"), sin cuenta atrás en vivo ni destacado de riesgo activo. En los finalizados, `[tiempo]` es el retraso acumulado al finalizar (`finalized_at - sla_deadline`), no el tiempo transcurrido desde el cierre; por tanto, es un valor estático que no crece.
- Q: ¿Cómo debe aplicarse el umbral de aviso "Próximo a vencer" cuando la duración total del SLA es inferior a 60 minutos? → A: Limitar el umbral a la mitad de la duración total cuando el SLA sea inferior a 60 minutos (por ejemplo, SLA de 30 min → ámbar en los últimos 15 min).
- Q: Cuando el filtro incluye a la vez estados activos y estados finales, ¿dónde deben aparecer los tickets Resuelto o Cerrado dentro del listado? → A: Al final de todo el listado, con independencia de la prioridad, ordenados por fecha de finalización más reciente primero.

## Escenarios de Usuario y Pruebas *(obligatorio)*

### Historia de Usuario 1 - Ver mi cola de trabajo priorizada (Prioridad: P1)

Como técnico, quiero abrir mi cola de trabajo y ver únicamente mis tickets asignados ordenados por urgencia, para saber cuál debo atender primero sin revisar el resto del sistema.

**Por qué esta prioridad**: Es el núcleo de la funcionalidad y el mínimo entregable con valor: sin el listado propio y correctamente ordenado, el técnico no puede planificar su trabajo.

**Prueba independiente**: Se puede probar con un técnico que tenga al menos tres tickets asignados y otro técnico con tickets propios. Al abrir la cola, el técnico ve solo sus tickets, con los cinco datos requeridos en cada fila y en el orden esperado.

**Escenarios de aceptación**:

1. **Dado** un técnico con tickets asignados a él y tickets asignados a otros técnicos, **cuando** abre su cola de trabajo, **entonces** ve únicamente los tickets cuyo responsable actual es él y no ve ningún ticket ajeno.
2. **Dado** un técnico con tickets de prioridades Crítica, Alta, Media y Baja, **cuando** se muestra la cola, **entonces** los tickets aparecen agrupados de mayor a menor prioridad (Crítica, Alta, Media, Baja).
3. **Dado** dos tickets de la misma prioridad con distinto tiempo restante hasta su límite SLA, **cuando** se muestra la cola, **entonces** aparece primero el que tiene menor tiempo restante.
4. **Dado** cualquier ticket listado, **cuando** el técnico lo observa en la cola, **entonces** la fila muestra el número de ticket, el título o resumen, la categoría, la prioridad y el tiempo restante hasta el límite SLA.
5. **Dado** un ticket sin fecha límite de SLA aplicable, **cuando** aparece en la cola, **entonces** se muestra con la indicación "Sin SLA definido" y se sitúa al final de su grupo de prioridad.

---

### Historia de Usuario 2 - Identificar tickets en riesgo de incumplir el SLA (Prioridad: P2)

Como técnico, quiero que los tickets próximos a incumplir o ya incumplidos se destaquen visualmente, para reaccionar antes de que se agote el plazo y reconocer de inmediato los que ya están fuera de plazo.

**Por qué esta prioridad**: El orden por urgencia ya prioriza, pero el destacado visual permite detectar el riesgo sin comparar tiempos ni hacer cálculos mentales.

**Prueba independiente**: Se puede probar con tickets cuyo tiempo restante esté por encima, por debajo y agotado respecto a los umbrales definidos, verificando color, icono y etiqueta textual en cada caso.

**Escenarios de aceptación**:

1. **Dado** un ticket con tiempo restante positivo pero dentro del umbral de aviso, **cuando** aparece en la cola, **entonces** se muestra con destacado ámbar, un icono de advertencia y la etiqueta "Próximo a vencer".
2. **Dado** un ticket cuyo límite SLA ya pasó, **cuando** aparece en la cola, **entonces** se muestra con destacado rojo, un icono de incumplimiento y la etiqueta "Vencido hace [tiempo]".
3. **Dado** un ticket sin riesgo inmediato, **cuando** aparece en la cola, **entonces** se muestra sin destacado de alarma y con la etiqueta "Dentro de plazo".
4. **Dado** un técnico con daltonismo o que usa un lector de pantalla, **cuando** consulta la cola, **entonces** el estado de riesgo se transmite también mediante icono y texto, no solo mediante color.
5. **Dado** un ticket Resuelto o Cerrado consultado mediante el filtro de estado, **cuando** aparece en el listado, **entonces** muestra su resultado histórico de SLA ("Dentro de plazo" o "Incumplido hace [tiempo]"), sin cuenta atrás en vivo ni destacado de riesgo activo; `[tiempo]` es el retraso con el que se finalizó respecto al límite, no el tiempo transcurrido desde el cierre.
6. **Dado** un ticket activo con un SLA total de 30 minutos y 20 minutos restantes, **cuando** aparece en la cola, **entonces** no se destaca en ámbar; **dado** ese mismo ticket con 15 minutos o menos restantes, **cuando** se actualiza la cola, **entonces** sí se destaca en ámbar como "Próximo a vencer".

---

### Historia de Usuario 3 - Filtrar mi cola por estado y prioridad (Prioridad: P2)

Como técnico, quiero filtrar mi cola por estado y por prioridad, para concentrarme en un subconjunto de tickets sin perder el orden por urgencia.

**Por qué esta prioridad**: Con colas grandes, el filtrado es lo que hace utilizable el listado en el día a día y permite, por ejemplo, revisar solo lo que está en progreso.

**Prueba independiente**: Se puede probar aplicando cada filtro por separado y en combinación, comprobando que solo aparecen los tickets que cumplen todos los criterios y que se mantiene el orden por prioridad y tiempo restante.

**Escenarios de aceptación**:

1. **Dado** una cola con tickets en varios estados, **cuando** el técnico filtra por estado "En progreso", **entonces** solo ve sus tickets en ese estado.
2. **Dado** una cola con tickets de varias prioridades, **cuando** el técnico filtra por prioridad "Crítica", **entonces** solo ve sus tickets de prioridad Crítica.
3. **Dado** un filtro de estado y otro de prioridad aplicados a la vez, **cuando** se muestra el resultado, **entonces** solo aparecen los tickets que cumplen ambos criterios.
4. **Dado** un resultado filtrado, **cuando** el técnico revisa el listado, **entonces** el orden por prioridad y tiempo restante se conserva dentro del subconjunto.
5. **Dado** un filtro aplicado, **cuando** el técnico lo restablece, **entonces** vuelve a ver la cola por defecto completa.
6. **Dado** un filtro que no devuelve ningún ticket, **cuando** se muestra el resultado, **entonces** aparece un mensaje de "sin resultados para los filtros seleccionados" con una acción para limpiarlos, distinto del mensaje de cola vacía.
7. **Dado** un filtro que incluye estados activos y finales, **cuando** se muestra el resultado, **entonces** los tickets activos aparecen primero con el orden por prioridad y tiempo restante, y los finalizados quedan al final, ordenados por fecha de finalización más reciente primero e independientemente de su prioridad.

---

### Historia de Usuario 4 - Entender estados vacíos y fallos de carga (Prioridad: P3)

Como técnico, quiero recibir mensajes claros cuando no tengo tickets asignados o cuando la cola no puede cargarse, para distinguir una situación normal de un error y saber qué hacer a continuación.

**Por qué esta prioridad**: Evita interpretaciones erróneas (creer que no hay trabajo cuando en realidad falló la carga) y completa la experiencia, pero no bloquea el valor principal de la funcionalidad.

**Prueba independiente**: Se puede probar con un técnico sin asignaciones, con filtros que no devuelven resultados y con una carga fallida, verificando que cada situación muestra un mensaje distinto y adecuado.

**Escenarios de aceptación**:

1. **Dado** un técnico sin ningún ticket asignado, **cuando** abre su cola, **entonces** ve un estado vacío que indica "No tienes tickets asignados actualmente" y no un mensaje de error.
2. **Dado** un técnico cuyos únicos tickets asignados están resueltos o cerrados, **cuando** abre la cola por defecto, **entonces** ve el estado vacío explicando que no hay tickets activos y cómo consultar los finalizados mediante el filtro de estado.
3. **Dado** un fallo al obtener la cola, **cuando** la vista no puede mostrarla, **entonces** aparece un mensaje de error diferenciado con una acción de reintento, sin presentarse como cola vacía.
4. **Dado** un técnico que permanece en la vista, **cuando** cambia la asignación o el estado de un ticket, **entonces** la cola se actualiza automáticamente en un plazo máximo de 60 segundos sin recargar la página completa.

---

### Casos Límite

- **Sin tickets asignados**: se muestra el estado vacío normal, nunca un error ni una lista vacía sin explicación.
- **Todos los tickets asignados cerrados o resueltos**: la cola por defecto (solo estados activos) aparece vacía con la explicación correspondiente; el técnico puede verlos cambiando el filtro de estado.
- **Filtros sin resultados**: mensaje específico de "sin resultados" con acción de limpiar filtros, diferenciado del estado vacío por falta de asignaciones.
- **Ticket justo en el límite (tiempo restante igual a cero)**: se considera aún no incumplido, se destaca en ámbar con la etiqueta "Vence ahora" y pasa a "Vencido" en cuanto el tiempo restante es negativo.
- **SLA de duración muy corta (menos de 60 minutos)**: el umbral de aviso se limita a la mitad de la duración total, de modo que el ticket conserva una fase inicial sin alarma; por ejemplo, un SLA de 30 minutos pasa a ámbar en los últimos 15 minutos.
- **Ticket vencido hace mucho tiempo**: se muestra "Vencido hace [X días]" sin truncar la gravedad; permanece visible y no se oculta automáticamente.
- **Ticket sin SLA definido**: se muestra "Sin SLA definido", no se destaca como riesgo y se ordena después de los tickets con SLA dentro de su misma prioridad.
- **Ticket finalizado mostrado al filtrar por estado**: muestra "Dentro de plazo" o "Incumplido hace [tiempo]" como resultado histórico, sin cuenta atrás ni destacado de riesgo activo, aunque se consulte mucho después de su cierre. `[tiempo]` es el retraso acumulado al finalizar (`finalized_at - sla_deadline`), no el tiempo transcurrido desde el cierre, por lo que no crece.
- **Filtro mixto de estados activos y finales**: los tickets activos se mantienen al principio con su orden por prioridad y tiempo restante, y los finalizados se agrupan al final por fecha de finalización más reciente, sin mezclarse con los activos aunque tengan mayor prioridad.
- **Ticket sin categoría o con categoría desactivada**: se muestra la categoría almacenada o "Sin categoría"; no impide listar ni ordenar.
- **Prioridad desactivada después de la asignación**: el ticket conserva y muestra su prioridad almacenada; el filtro de prioridad incluye las prioridades presentes en toda la cola del técnico —sin aplicar los filtros actuales, para que el técnico pueda ampliar el filtro sin perder opciones—, indicando si alguna está inactiva.
- **Cambio de prioridad o de fecha límite por nueva configuración de SLA**: los tickets existentes conservan la prioridad y el límite SLA vigentes en el momento de su creación; la cola refleja esos valores.
- **Ticket reasignado a otro técnico mientras la vista está abierta**: desaparece de la cola en la siguiente actualización (máximo 60 segundos). El aviso dentro de una vista de detalle ya abierta pertenece a la HU-06 (detalle y reasignación) y queda fuera de esta historia.
- **Ticket en "Pendiente de usuario"**: permanece en la cola y su contador SLA sigue avanzando, ya que el plazo no se pausa.
- **Usuario responde y el ticket vuelve a "En progreso"**: el ticket se reposiciona según su prioridad y tiempo restante en la siguiente actualización.
- **Cambio de hora oficial (verano/invierno)**: los tiempos restantes se calculan sobre instantes UTC, de modo que el cambio de hora no produce saltos ni duplicados; Europe/Madrid se usa solo para presentar fechas y horas.
- **Cola con más tickets que el tamaño de página**: el orden se aplica al conjunto completo antes de paginar, de modo que la primera página contiene siempre los tickets más urgentes.
- **Sesión caducada**: se solicita iniciar sesión de nuevo y, tras hacerlo, se regresa a la cola.
- **Actualización automática durante el uso de filtros**: los filtros aplicados se mantienen y el orden se recalcula con los nuevos tiempos.
- **Título muy largo**: se muestra truncado en la fila con acceso al texto completo, sin romper la alineación ni ocultar los demás datos.

## Requisitos *(obligatorio)*

### Requisitos Funcionales

**Alcance y visibilidad**

- **FR-001**: El sistema DEBE mostrar en la cola únicamente los tickets cuyo responsable actual sea el técnico autenticado.
- **FR-002**: El sistema DEBE impedir que un técnico vea tickets de otros técnicos a través de filtros, enlaces directos o cualquier otro medio de acceso a la vista.
- **FR-003**: El sistema DEBE excluir de la cola por defecto los tickets en estados finales (Resuelto y Cerrado), manteniéndolos accesibles mediante el filtro de estado.
- **FR-004**: El sistema DEBE incluir por defecto los tickets en estados activos (Abierto, En progreso y Pendiente de usuario).
- **FR-005**: El sistema DEBE actualizar la cola automáticamente en un plazo máximo de 60 segundos y al recuperar el foco de la vista, sin requerir recarga manual.

**Contenido del listado**

- **FR-006**: Cada fila de la cola DEBE mostrar el número de ticket, el título o resumen, la categoría, la prioridad y el dato de SLA: tiempo restante en estados activos o resultado histórico en estados finales.
- **FR-007**: El sistema DEBE mostrar el tiempo restante en unidades legibles y adaptadas a su magnitud (días y horas, horas y minutos, o minutos).
- **FR-008**: El sistema DEBE mostrar "Vence ahora" con destacado ámbar cuando el tiempo restante sea exactamente cero, considerándolo aún no incumplido.
- **FR-009**: El sistema DEBE mostrar el tiempo transcurrido desde el incumplimiento cuando el límite SLA ya haya pasado en un ticket activo, con la indicación "Vencido hace [tiempo]". En tickets activos este tiempo es dinámico y sigue creciendo hasta que el ticket se finaliza.
- **FR-010**: El sistema DEBE mostrar "Sin SLA definido" cuando el ticket no tenga un límite SLA aplicable.
- **FR-011**: El sistema DEBE mostrar el resultado vacío o el error de carga de forma diferenciada y con un mensaje comprensible en español.

**Ordenación**

- **FR-012**: El sistema DEBE ordenar por defecto los tickets activos de mayor a menor prioridad, considerando Crítica como la mayor y Baja como la menor.
- **FR-013**: Dentro de la misma prioridad, el sistema DEBE ordenar los tickets activos por menor tiempo restante hasta el límite SLA primero.
- **FR-014**: El sistema DEBE considerar los tickets vencidos como los de menor tiempo restante (valores negativos), situándolos antes que los no vencidos de su misma prioridad.
- **FR-015**: El sistema DEBE situar los tickets sin SLA definido al final de su grupo de prioridad.
- **FR-016**: El sistema DEBE aplicar un desempate estable por número de ticket ascendente cuando prioridad y tiempo restante coincidan.
- **FR-017**: El sistema DEBE mantener este orden tras aplicar filtros y antes de paginar los resultados.
- **FR-036**: El sistema DEBE paginar el resultado ya ordenado en páginas de 25 tickets por defecto, admitiendo un tamaño entre 1 y 100 mediante el parámetro `page_size`; si la página solicitada supera el total de páginas, DEBE devolver la última página disponible.

**Destacado de riesgo**

- **FR-018**: El sistema DEBE destacar en rojo, con icono y etiqueta "Vencido hace [tiempo]", los tickets activos cuyo límite SLA ya se ha superado.
- **FR-019**: El sistema DEBE destacar en ámbar, con icono y etiqueta "Próximo a vencer", los tickets activos con tiempo restante positivo e igual o inferior al umbral de aviso, así como los que estén exactamente en el límite conforme a FR-008.
- **FR-020**: El sistema DEBE calcular el umbral de aviso de los tickets activos así: si la duración total del SLA es inferior a 60 minutos, la mitad de esa duración; en caso contrario, el mayor entre 60 minutos y el 25 % de la duración total del SLA.
- **FR-021**: El sistema DEBE mostrar el indicador de riesgo junto al dato de SLA en los tickets activos, sin necesidad de abrir el detalle del ticket.
- **FR-022**: El sistema DEBE transmitir el riesgo mediante color, icono y texto, de modo que no dependa únicamente del color.

**Filtrado**

- **FR-023**: El sistema DEBE permitir filtrar la cola por uno o varios estados entre los disponibles, incluyendo los estados finales.
- **FR-024**: El sistema DEBE permitir filtrar la cola por una o varias prioridades.
- **FR-025**: El sistema DEBE combinar los filtros de estado y prioridad con lógica "Y", mostrando solo los tickets que cumplan todos los criterios seleccionados.
- **FR-026**: El sistema DEBE mostrar el número de tickets resultantes tras aplicar los filtros.
- **FR-027**: El sistema DEBE ofrecer una acción para restablecer los filtros a la vista por defecto.
- **FR-028**: El sistema DEBE mantener los filtros aplicados durante la sesión de navegación en la cola.
- **FR-029**: Los filtros NUNCA DEBEN ampliar el alcance de visibilidad del técnico ni mostrar tickets no asignados a él.

**Estados vacíos y errores**

- **FR-030**: Cuando el técnico no tenga ningún ticket asignado, el sistema DEBE mostrar un estado vacío informativo que indique que no hay tickets asignados. El estado vacío DEBE distinguir entre «sin asignaciones» y «solo tickets finalizados» usando el número total de tickets activos y finalizados de la cola.
- **FR-031**: Cuando los filtros no devuelvan resultados, el sistema DEBE mostrar un mensaje específico de "sin resultados" con la acción de limpiar filtros.
- **FR-032**: Cuando la cola no pueda cargarse, el sistema DEBE mostrar un mensaje de error con una acción de reintento, sin confundirlo con una cola vacía.
- **FR-033**: Cuando la sesión haya caducado, el sistema DEBE solicitar autenticación de nuevo y devolver al técnico a su cola tras iniciar sesión.
- **FR-034**: Cuando un ticket en estado final (Resuelto o Cerrado) se muestre mediante el filtro de estado, el sistema DEBE mostrar su resultado histórico de SLA: "Dentro de plazo" si se finalizó en el límite o antes, o "Incumplido hace [tiempo]" si se finalizó después, sin cuenta atrás en vivo ni destacado de riesgo activo. En los finalizados, `[tiempo]` es el retraso acumulado al finalizar (`finalized_at - sla_deadline`), no el tiempo transcurrido desde el cierre, por lo que es estático y no crece. Si no tiene SLA aplicable, mostrará "Sin SLA definido".
- **FR-035**: Cuando el resultado de un filtro incluya tickets activos y finalizados, el sistema DEBE mostrar primero todos los tickets activos con el orden de urgencia definido y, después, todos los finalizados al final del listado, con independencia de su prioridad y ordenados por fecha de finalización más reciente primero. Si dos tickets finalizados comparten fecha de finalización, se desempatará por número de ticket ascendente.

### Reglas de Negocio

- **RN-01 (Propiedad del ticket)**: un ticket aparece en la cola de un único técnico: su responsable actual. La asignación es la única fuente de verdad para la visibilidad; ningún filtro, orden o enlace puede ampliarla.
- **RN-02 (Composición por defecto)**: la cola por defecto contiene los estados Abierto, En progreso y Pendiente de usuario. Resuelto y Cerrado solo se muestran si el técnico los selecciona explícitamente en el filtro de estado.
- **RN-03 (Límite SLA fijo)**: cada ticket conserva el límite SLA vigente en el momento de su creación. Los cambios posteriores en la configuración de categorías, prioridades o plazos no alteran tickets ya creados.
- **RN-04 (Cálculo del tiempo restante)**: el tiempo restante es la diferencia entre el límite SLA y el instante actual, calculada en UTC sobre instantes absolutos y presentada en la zona horaria Europe/Madrid. Para la visualización se redondea a la baja al minuto, para no dar una falsa sensación de holgura. La clasificación de riesgo (FR-008, FR-019 y RN-09) se evalúa con el valor exacto en segundos: por ello, un ticket que muestra «15 min» puede seguir en «Dentro de plazo» hasta que queden 15:00 o menos.
- **RN-05 (Reloj SLA)**: el contador SLA no se pausa en ningún estado activo, incluido "Pendiente de usuario". Un ticket en espera de respuesta del usuario sigue consumiendo plazo y puede llegar a incumplirse.
- **RN-06 (Prioridad)**: el orden de los tickets activos usa la prioridad almacenada en el ticket: Crítica > Alta > Media > Baja. Una prioridad desactivada posteriormente no cambia el orden de los tickets existentes.
- **RN-07 (SLA ya incumplido)**: en tickets activos, un ticket vencido no se elimina de la cola, no se reasigna automáticamente y no se oculta. Permanece asignado al técnico, se muestra en rojo con la etiqueta "Vencido hace [tiempo]" y se ordena, dentro de su prioridad, antes que los tickets aún no vencidos. En estos tickets activos, el tiempo mostrado crece de forma dinámica. El técnico puede seguir consultándolo y actualizándolo con normalidad. El incumplimiento queda registrado y es visible para la supervisión; cerrar el ticket no borra dicho registro.
- **RN-08 (El vencimiento no altera la prioridad)**: un ticket vencido de prioridad Baja sigue apareciendo después de un ticket de prioridad Crítica aún dentro de plazo. El incumplimiento no promociona el ticket a una prioridad superior.
- **RN-09 (Umbral de aviso)**: en tickets activos, un ticket está "Próximo a vencer" cuando su tiempo restante es igual a cero o positivo y menor o igual al umbral de aviso. El umbral es la mitad de la duración total cuando esta es inferior a 60 minutos, y en caso contrario el mayor de 60 minutos o el 25 % de dicha duración; así, un SLA de 30 minutos avisa en los últimos 15 minutos, uno de 4 horas avisa en los últimos 60 minutos y uno de 24 horas avisa en las últimas 6 horas. En ese caso, incluido el instante exacto del límite, se destaca en ámbar y se etiqueta "Vence ahora"; con tiempo negativo se destaca en rojo como vencido; en el resto de casos no muestra alarma. Los tickets en estados finales no reciben estos destacados, conforme a RN-13.
- **RN-10 (Sin SLA)**: un ticket sin límite SLA aplicable no se considera vencido ni próximo a vencer, se muestra como "Sin SLA definido" y se ordena al final de su grupo de prioridad.
- **RN-11 (Filtros)**: los filtros de estado y prioridad se combinan con lógica "Y", nunca sustituyen a la regla de propiedad y no modifican el orden por urgencia. Los filtros se mantienen durante la navegación en la cola hasta que el técnico los restablezca.
- **RN-12 (Reasignación)**: si un ticket se reasigna a otro técnico, deja de formar parte de la cola del técnico anterior en la siguiente actualización y pasa a la del nuevo responsable.
- **RN-13 (Estados finales)**: un ticket Resuelto o Cerrado no aparece en la vista por defecto porque ya no requiere acción del técnico, pero sigue siendo consultable mediante el filtro de estado. En ese caso muestra su resultado histórico de SLA —"Dentro de plazo" o "Incumplido hace [tiempo]"—, sin cuenta atrás ni destacado de riesgo activo. En finalizados, `[tiempo]` es el retraso acumulado al finalizar (`finalized_at - sla_deadline`), no el tiempo transcurrido desde el cierre, por lo que no crece. Se considera fecha de finalización el primer paso del ticket a Resuelto o Cerrado, y se entiende cumplido el SLA si dicha fecha es igual o anterior al límite.
- **RN-14 (Refresco de tiempos)**: los tiempos restantes y los indicadores de riesgo se recalculan como mínimo cada 60 segundos, sin que el técnico deba recargar la vista.
- **RN-15 (Idioma y formato)**: la vista se presenta en español de España, con fechas, horas y duraciones en formato local y zona horaria Europe/Madrid.
- **RN-16 (Accesibilidad)**: la información de riesgo y prioridad debe ser perceptible sin depender del color, con contraste suficiente, textos alternativos y navegación por teclado conforme a WCAG 2.1 AA.
- **RN-17 (Orden con estados finales)**: cuando el filtro incluya estados finales, los tickets finalizados se colocan después de todos los activos, sin ordenarse por prioridad, de más recientemente finalizado a menos. Un empate se resuelve por número de ticket ascendente. Este criterio no altera el orden de los tickets activos.

### Requisitos de Empaquetado y Despliegue

Estos requisitos son transversales al proyecto y no alteran el comportamiento funcional de la cola. Permiten validar la historia en un entorno reproducible y comprobar que la aplicación arranca con sus dependencias.

- **FR-037**: El proyecto DEBE incluir un `Dockerfile` multi-etapa que compile el frontend con Node y construya dos destinos: `frontend` (Nginx + SPA) y `backend` (Python + FastAPI).
- **FR-038**: El repositorio DEBE incluir un `.dockerignore` que excluya dependencias locales, entornos virtuales, secretos, artefactos de pruebas, bases de datos locales y metadatos del repositorio.
- **FR-039**: El proyecto DEBE incluir un `docker-compose.yml` con los servicios `db` (PostgreSQL 16), `backend` y `frontend`, conectados por la red interna de Compose y con healthchecks que ordenen el arranque.
- **FR-040**: `docker compose up` DEBE dejar la aplicación operativa sin pasos manuales: el backend aplica las migraciones de Alembic automáticamente y el frontend queda disponible en `http://localhost:8080` con `/api` proxificado al backend.
- **FR-041**: Los datos de PostgreSQL DEBEN persistir en el volumen nombrado `ticketing_db_data`; `docker compose down` no debe borrarlos y `docker compose down -v` debe permitir un reinicio limpio.
- **FR-042**: Toda la configuración (credenciales de PostgreSQL, secreto JWT, emisor/audiencia, puertos, orígenes CORS y URL del API) DEBE recibirse por variables de entorno documentadas en `.env.example` y en el `README.md`, sin secretos reales en el repositorio.
- **FR-043**: El `README.md` DEBE documentar los comandos de arranque, parada, logs, reinicio, borrado de datos, seed opcional y solución de problemas.

### Entidades Clave

- **Ticket**: representa la incidencia. Para esta funcionalidad se consideran su número identificador, título o resumen, categoría, prioridad, estado, técnico asignado, fecha de creación, fecha límite de SLA, fecha de finalización y resultado histórico de SLA.
- **Asignación**: vínculo entre un ticket y el técnico responsable actual. Determina qué tickets aparecen en cada cola y cambia cuando el ticket se reasigna.
- **Prioridad**: nivel de urgencia del ticket (Crítica, Alta, Media y Baja) con su orden jerárquico y su color asociado. Define la primera clave de ordenación.
- **Límite SLA**: fecha y hora máximas de atención del ticket, fijada al crearse según la regla de SLA aplicable. Define el tiempo restante y el estado de riesgo.
- **Estado del ticket**: situación del ticket dentro de su ciclo de vida (Abierto, En progreso, Pendiente de usuario, Resuelto, Cerrado). Determina la pertenencia a la cola por defecto y las opciones de filtrado.
- **Categoría**: clasificación del ticket según el tipo de incidencia. Se muestra en cada fila del listado.
- **Técnico**: usuario con rol técnico al que se asignan tickets. Es el propietario de la cola y único destinatario de la vista.

## Criterios de Éxito *(obligatorio)*

### Resultados Medibles

- **SC-001**: El 100 % de las filas de la cola corresponde a tickets asignados al técnico autenticado, verificado con dos técnicos y sus colas cruzadas, con cero tickets ajenos visibles.
- **SC-002**: Un técnico puede identificar el ticket más urgente de su cola en menos de 10 segundos desde que la vista termina de cargar.
- **SC-003**: El 100 % de los tickets activos con SLA incumplido muestra el destacado rojo, el icono y la etiqueta "Vencido hace [tiempo]" en la cola.
- **SC-004**: El 100 % de los tickets próximos a vencer según el umbral definido muestra el destacado ámbar, el icono y la etiqueta correspondiente.
- **SC-005**: El 95 % de las aperturas de la cola muestra la lista completa en menos de 2 segundos para técnicos con hasta 100 tickets asignados.
- **SC-006**: Un técnico encuentra un ticket concreto usando los filtros de estado y prioridad en menos de 15 segundos en una cola de 50 tickets.
- **SC-009**: El 100 % de los casos de cola sin tickets asignados y de error de carga muestra el mensaje diferenciado correcto, sin falsos estados vacíos.
- **SC-010**: El 100 % de los tickets vencidos sigue visible y accesible en la cola hasta su resolución, cierre o reasignación, sin ocultaciones automáticas.
- **SC-011**: El 100 % de los tickets finalizados consultados mediante el filtro de estado muestra su resultado histórico de SLA sin cuenta atrás en vivo ni destacado de riesgo activo.
- **SC-012**: El 100 % de las consultas con filtros mixtos coloca todos los tickets activos antes que los finalizados, y estos últimos ordenados por fecha de finalización más reciente.
- **SC-013**: Partiendo de un clon limpio y un equipo con Docker, `docker compose up` deja la aplicación y la base de datos operativas sin instalar Python, Node ni PostgreSQL, y los datos persisten tras `docker compose down` y un nuevo `docker compose up`.

### Resultados de Negocio (post-lanzamiento, no verificables con la app)

Estos resultados orientan el valor del producto, pero no forman parte de los criterios de aceptación verificables de esta historia:

- **BN-001**: El 90 % de los técnicos encuestados afirma que el orden por defecto refleja correctamente la urgencia de su trabajo.
- **BN-002**: Se reduce en un 30 % el tiempo medio entre la asignación de un ticket crítico y la primera acción del técnico sobre él, respecto al periodo anterior a la funcionalidad.

## Supuestos

- El sistema de autenticación y los roles (usuario, técnico, supervisor, administrador) ya existen o se integran con un proveedor externo; esta funcionalidad asume que el técnico está autenticado y correctamente identificado.
- Cada ticket tiene un único técnico responsable en un momento dado; no se contemplan asignaciones compartidas ni colas de equipo en esta historia.
- La prioridad del ticket ya existe y tiene un orden definido (Crítica, Alta, Media, Baja); esta funcionalidad no la calcula ni la modifica.
- La fecha límite de SLA se calcula y almacena al crear el ticket según la configuración vigente, conforme a la HU-08; esta vista solo la consume.
- El reloj SLA no se pausa en "Pendiente de usuario"; se ha optado por la opción más estricta y coherente con un límite SLA fijo, y así se refleja en las métricas de supervisión.
- El umbral de aviso definido (la mitad del SLA si dura menos de 60 minutos; en caso contrario, el mayor de 60 minutos o el 25 % del SLA) es un valor de partida razonable; podría hacerse configurable en una evolución futura sin cambiar el comportamiento esencial.
- La cola muestra todos los estados activos por defecto; los estados finales quedan accesibles mediante filtro, no mediante una vista de historial separada.
- La fecha de finalización de un ticket es la de su primer paso a Resuelto o Cerrado; el resultado histórico del SLA se calcula comparando esa fecha con el límite SLA, sin cuenta atrás en vivo.
- Se asume un volumen habitual de hasta 100 tickets activos por técnico, con un tamaño de página de 25 tickets por defecto configurable por API entre 1 y 100; la interfaz no ofrece control de tamaño de página.
- La vista está orientada a escritorio y tablet; no se requiere una experiencia específica para móvil en esta historia.
- La zona horaria de referencia es Europe/Madrid y la interfaz se presenta en español de España.
- No se incluye en esta historia la reasignación, el escalado, el cambio de estado ni la edición de tickets; esas acciones pertenecen a otras historias y aquí solo se consultan.
- La fila puede incluir un enlace de consulta al detalle existente del ticket; esta historia no implementa ni modifica esa vista, que pertenece a la HU-06.
- No se incluyen notificaciones push ni alertas proactivas por SLA; el destacado visual y la actualización periódica son el mecanismo de aviso de esta vista.
- No se incluye una cola global o de equipo para supervisores; la supervisión agregada corresponde a la HU-07.

## Fuera de Alcance

- Reasignar, escalar o cambiar el estado de un ticket desde la cola.
- Editar la prioridad, la categoría o el límite SLA de un ticket desde la cola.
- Cola compartida de equipo o vista de "todos los tickets" para supervisores.
- Ordenaciones alternativas configurables por el técnico (por fecha, por categoría, etc.).
- Notificaciones por correo o push por proximidad o incumplimiento de SLA.
- Historial de tickets finalizados como vista independiente.
- Configuración de los umbrales de aviso por parte del técnico.

---

# Módulo HU-05: Cambio de estado y documentación de resolución (conservado íntegro)

> Contenido conservado sin cambios respecto a `specs/005-cambio-estado-resolucion/spec.md`. No se ha modificado ningún requisito, escenario, regla de negocio ni criterio de aceptación.

# Especificación Funcional: Cambio de estado y documentación de resolución (HU-05)

**Rama**: `hu-05-cambiar-estado`

**Creado**: 2026-11-02

**Estado**: Implementada (verificado el 2026-11-09)

**Entrada**: HU-05 — «Cambiar estado y documentar resolución»

## Resumen

El técnico asignado a un ticket puede hacer avanzar su estado respetando el flujo definido por el sistema. Cuando el ticket pasa a «Resuelto», es obligatorio describir la solución aplicada. Esa descripción se conserva y se muestra en la línea temporal del ticket. Además, el técnico puede registrar comentarios internos en cualquier momento, independientemente del estado del ticket.

La funcionalidad debe garantizar que no exista ningún ticket «Resuelto» sin solución documentada, que todo cambio quede trazado con autor y fecha, y que los comentarios internos nunca sean visibles para el usuario creador.

## Clarifications

### Session 2026-11-02

- Q: ¿Se permite que un ticket pase de «Resuelto» a «En progreso» para corregir o completar la solución, o el flujo debe ser estrictamente Abierto → En progreso → Resuelto → Cerrado? → A: Se permite reabrir de «Resuelto» a «En progreso», conservando la resolución anterior como histórico; «Cerrado» sigue siendo definitivo.
- Q: ¿La descripción de la solución debe ser visible para el usuario creador del ticket o debe quedar restringida al personal interno? → A: La solución es visible para el usuario creador y para el personal interno, y aparece en la línea temporal pública como entrada «Resolución».
- Q: ¿Quién debe poder consultar los comentarios internos de un ticket? → A: Solo el técnico actualmente asignado, los supervisores y los administradores; los técnicos no asignados y el usuario creador no tienen acceso.
- Q: ¿La transición a «Pendiente de usuario» debe exigir un mensaje con la información solicitada al usuario, o esa validación corresponde únicamente a HU-03? → A: HU-05 solo valida la transición; la solicitud de información y su contenido se rigen por HU-03.

## Actores

- **Técnico asignado**: único actor que puede cambiar el estado y añadir comentarios internos en el ticket.
- **Usuario creador**: consulta el estado y la línea temporal pública; puede ver la resolución, pero no los comentarios internos.
- **Supervisor/administrador**: puede consultar la trazabilidad y los comentarios internos; no realiza cambios de estado dentro del alcance de esta historia.

## Escenarios de Usuario y Pruebas

### Historia 1 — Cambiar el estado según el flujo permitido (Prioridad: P1)

Como técnico asignado, quiero cambiar el estado del ticket entre los valores definidos, para reflejar en qué fase se encuentra y mantener informado al usuario.

**Por qué esta prioridad**: es la base de la historia; sin un flujo de estados controlado no puede existir una resolución trazable.

**Prueba independiente**: partiendo de un ticket asignado en estado «Abierto», el técnico puede moverlo a «En progreso» y comprobar que el nuevo estado y la entrada correspondiente aparecen en la línea temporal.

**Escenarios de aceptación**:

1. **Dado** un ticket «Abierto» asignado al técnico, **cuando** el técnico selecciona «En progreso», **entonces** el ticket pasa a «En progreso» y se registra una entrada en la línea temporal con el estado anterior, el nuevo, el autor y la fecha y hora.
2. **Dado** un ticket «En progreso», **cuando** el técnico selecciona «Pendiente de usuario», **entonces** el ticket pasa a «Pendiente de usuario» y el cambio queda registrado en la línea temporal.
3. **Dado** un ticket «Pendiente de usuario», **cuando** HU-03 procesa una respuesta del usuario creador, **entonces** HU-05 debe aceptar la transición resultante a «En progreso» y registrarla en la línea temporal. La detección y el procesamiento de la respuesta son responsabilidad de HU-03; esta historia solo cubre la validez y la trazabilidad de la transición.
4. **Dado** un ticket «Resuelto», **cuando** el técnico selecciona «Cerrado», **entonces** el ticket pasa a «Cerrado» y el cierre queda registrado en la línea temporal.
5. **Dado** un ticket «Cerrado», **cuando** el técnico intenta seleccionar cualquier otro estado, **entonces** el sistema no permite la transición y muestra los estados disponibles, que en este caso son ninguno.
6. **Dado** un ticket «Abierto», **cuando** el técnico intenta pasar directamente a «Resuelto» o «Cerrado», **entonces** el sistema rechaza la transición, mantiene el estado «Abierto» y no crea ninguna entrada en la línea temporal.

---

### Historia 2 — Documentar obligatoriamente la resolución (Prioridad: P1)

Como técnico asignado, quiero describir cómo he resuelto el ticket al marcarlo como «Resuelto», para que la solución quede documentada y sirva de referencia futura.

**Por qué esta prioridad**: cumple el criterio central de la historia; un ticket resuelto sin explicación no aporta valor como referencia ni garantiza la calidad del servicio.

**Prueba independiente**: partiendo de un ticket «En progreso», se intenta marcar como «Resuelto» sin descripción y el sistema lo impide; al repetir con una descripción válida, el estado cambia y la solución aparece en la línea temporal.

**Escenarios de aceptación**:

1. **Dado** un ticket «En progreso», **cuando** el técnico selecciona «Resuelto» y deja la descripción de la solución vacía, **entonces** el sistema impide guardar, mantiene el estado «En progreso», no crea ninguna entrada en la línea temporal y muestra un mensaje indicando que la descripción es obligatoria.
2. **Dado** un ticket «En progreso», **cuando** el técnico introduce únicamente espacios en blanco como descripción y selecciona «Resuelto», **entonces** el sistema aplica la misma validación que en el caso vacío.
3. **Dado** un ticket «En progreso», **cuando** el técnico introduce una descripción de solución válida y confirma «Resuelto», **entonces** el estado pasa a «Resuelto» y la solución se guarda asociada al ticket.
4. **Dado** un ticket recién pasado a «Resuelto», **cuando** el técnico o el usuario creador consultan la línea temporal, **entonces** ven una entrada de tipo «Resolución» con el texto de la solución, el autor y la fecha y hora.
5. **Dado** un ticket «Resuelto» con solución documentada, **cuando** el técnico lo cierra, **entonces** la solución sigue siendo visible en la línea temporal del ticket cerrado.
6. **Dado** un ticket «Resuelto» que se reabre a «En progreso», **cuando** el técnico vuelve a resolverlo con una nueva descripción, **entonces** se conserva la resolución anterior y se añade la nueva como una entrada independiente.

---

### Historia 3 — Añadir comentarios internos en cualquier momento (Prioridad: P2)

Como técnico asignado, quiero añadir notas internas al ticket en cualquier estado, para dejar constancia de comprobaciones, decisiones o información que no debe ver el usuario.

**Por qué esta prioridad**: aporta contexto operativo al equipo técnico, pero no bloquea el flujo principal de cambio de estado y resolución.

**Prueba independiente**: en un ticket «En progreso» y en un ticket «Cerrado», el técnico añade un comentario interno y comprueba que aparece en la línea temporal interna sin alterar el estado.

**Escenarios de aceptación**:

1. **Dado** un ticket en cualquier estado, **cuando** el técnico añade un comentario interno con texto válido, **entonces** el comentario se guarda, aparece en la línea temporal identificado como interno y el estado del ticket no cambia.
2. **Dado** un ticket «Cerrado», **cuando** el técnico añade un comentario interno, **entonces** el sistema permite la operación y registra el comentario.
3. **Dado** un ticket con comentarios internos, **cuando** el usuario creador consulta la línea temporal, **entonces** no ve ningún comentario interno.
4. **Dado** un ticket con comentarios internos asignado a otro técnico, **cuando** un técnico no asignado intenta consultar la línea temporal interna, **entonces** no ve los comentarios internos.
5. **Dado** un ticket en cualquier estado, **cuando** el técnico intenta guardar un comentario interno vacío o compuesto solo por espacios, **entonces** el sistema lo impide y muestra un mensaje de validación.

---

## Reglas de Negocio

### RN-01 — Estados del ticket

Los estados disponibles son los definidos en RF-02.1 del sistema:

- **Abierto**: el ticket ha sido registrado y todavía no se ha empezado a trabajar en él.
- **En progreso**: el equipo técnico está trabajando activamente en el ticket.
- **Pendiente de usuario**: el ticket está a la espera de información o de una acción del usuario creador.
- **Resuelto**: el técnico ha aplicado una solución y la ha documentado; queda pendiente el cierre.
- **Cerrado**: el ticket ha finalizado y no admite más cambios de estado.

### RN-02 — Transiciones válidas

| Estado actual \ Estado destino | Abierto | En progreso | Pendiente de usuario | Resuelto | Cerrado |
|---|---|---|---|---|---|
| **Abierto** | — | Sí | No | No | No |
| **En progreso** | No | — | Sí | Sí | No |
| **Pendiente de usuario** | No | Sí (manual o automático al responder el usuario) | — | No | No |
| **Resuelto** | No | Sí (reapertura) | No | — | Sí |
| **Cerrado** | No | No | No | No | — |

- Cualquier transición no marcada como «Sí» debe rechazarse sin modificar el ticket.
- No se registra una entrada en la línea temporal cuando el estado de destino es igual al estado actual.
- La única transición permitida desde «Cerrado» es ninguna: el cierre es definitivo en esta versión.
- La reapertura solo se permite desde «Resuelto» hacia «En progreso». Un ticket «Cerrado» no se reabre; si el problema reaparece, se gestiona como un ticket nuevo.
- La transición a «Pendiente de usuario» no exige un mensaje en esta historia. La solicitud de información y su contenido se rigen por HU-03.

### RN-03 — Descripción obligatoria de la solución

- Al mover un ticket a «Resuelto», la descripción de la solución es obligatoria.
- Se considera vacía una descripción que no contenga ningún carácter distinto de espacios, tabuladores o saltos de línea.
- La descripción debe tener entre 1 y 5.000 caracteres una vez eliminados los espacios al inicio y al final.
- La descripción no es obligatoria para el resto de transiciones; si se envía junto a un destino distinto de «Resuelto», la operación se rechaza con `resolution_not_allowed`.
- La descripción de la solución no puede modificarse una vez guardada. Si la solución cambia, debe reabrirse el ticket y documentarse una nueva resolución, conservando la anterior.
- La obligación se aplica a las transiciones ejecutadas a partir de la implantación de HU-05; a efectos de auditoría, el corte operativo es la migración `0003_ticket_timeline` y se identifica con los tickets cuyo `finalized_at` es posterior a esa migración. Los tickets resueltos con anterioridad se consideran legado y no se modifican retroactivamente.

### RN-04 — Atomicidad del cambio de estado

- El cambio de estado, la descripción de la solución y la entrada de la línea temporal se guardan como una única operación.
- Si falla cualquier validación o el guardado no puede completarse, no debe persistirse ningún cambio parcial: ni el estado, ni la solución, ni la entrada de la línea temporal.
- Un doble envío de la misma acción no debe generar entradas duplicadas en la línea temporal. Las transiciones y los comentarios internos incluyen un `request_id` obligatorio; un reintento idéntico devuelve `changed=false` (transición) o `created=false` (comentario interno) sin escribir, y su reutilización con distintos datos se rechaza con `409 request_id_reused`.

### RN-05 — Trazabilidad e inmutabilidad

- Cada cambio de estado genera una entrada en la línea temporal con: estado anterior, estado nuevo, autor, fecha y hora.
- Cada resolución genera una entrada de tipo «Resolución» con la descripción de la solución, el autor y la fecha y hora.
- Las entradas de la línea temporal no se pueden editar ni eliminar.
- Las resoluciones anteriores se conservan aunque el ticket se reabra y se vuelva a resolver.
- La línea temporal mantiene el orden cronológico de los hechos.

### RN-06 — Comentarios internos

- El técnico asignado puede añadir comentarios internos en cualquier estado del ticket, incluido «Cerrado».
- Un comentario interno debe contener entre 1 y 5.000 caracteres una vez eliminados los espacios al inicio y al final.
- Un comentario interno no cambia el estado del ticket ni sustituye a la descripción de la solución.
- Los comentarios internos están identificados como tales en la línea temporal.
- Los comentarios internos solo son visibles para el técnico actualmente asignado, los supervisores y los administradores. Nunca son visibles para el usuario creador ni para técnicos no asignados.
- Los comentarios internos no se pueden editar ni eliminar una vez guardados.

### RN-07 — Permisos

- Solo el técnico actualmente asignado al ticket puede cambiar su estado y añadir comentarios internos.
- Si el ticket se reasigna, el técnico anterior deja de ver los comentarios internos y pierde la capacidad de modificar el estado y de añadir nuevos comentarios.
- El usuario creador solo puede consultar el estado y la línea temporal pública; no puede cambiar estados ni ver comentarios internos.
- Supervisores y administradores pueden consultar la información interna, pero los cambios de estado y los comentarios internos quedan fuera de su alcance en esta historia.

### RN-08 — Concurrencia y conflicto de edición

- Si dos sesiones o dos técnicos tras una reasignación intentan modificar el mismo ticket y una de ellas guarda primero, la segunda operación debe rechazarse para evitar sobrescribir cambios.
- Ante un conflicto, el sistema debe indicar que el ticket ha cambiado y solicitar que se actualice la información antes de volver a intentarlo.
- Un conflicto no debe modificar el estado, la solución ni la línea temporal.

### RN-09 — Presentación de la resolución

- La resolución se muestra en la línea temporal visible para el técnico y para el usuario creador, conforme a RN-05 y RF-012–RF-014.
- La resolución debe distinguirse visualmente de los cambios de estado y de los comentarios internos.
- La resolución anterior a una reapertura se identifica visualmente como histórica; su conservación y visibilidad tras el cierre se rigen por RF-013 y RF-014.

## Requisitos Funcionales

### Cambio de estado

- **RF-001**: El sistema DEBE permitir al técnico asignado cambiar el estado del ticket entre los valores definidos en RN-01.
- **RF-002**: El sistema DEBE ofrecer únicamente los estados de destino permitidos para el estado actual según RN-02.
- **RF-003**: El sistema DEBE rechazar cualquier transición no permitida, mantener el estado original y no generar ninguna entrada en la línea temporal.
- **RF-004**: El sistema DEBE impedir cualquier cambio de estado cuando el ticket esté «Cerrado».
- **RF-005**: HU-03 es la propietaria de la transición automática de «Pendiente de usuario» a «En progreso» cuando el usuario creador responde. HU-05 solo debe garantizar que esa transición es válida en RN-02 y que, cuando HU-03 la ejecute, quede registrada en la línea temporal con autor y fecha. La detección de la respuesta y el contenido de la solicitud de información no forman parte de esta historia.

  **Contrato de integración con HU-03 (RF-005)**: HU-03 ejecuta la transición mediante la función interna `apply_user_response_transition` de `ticket_workflow.py`, dentro de su propia transacción. La función exige `actor_id == ticket.creator_id`, estado `pendiente_usuario`, `request_id` estable del evento de respuesta y `expected_updated_at`; registra `status_change` con autor creador y no se expone como endpoint público. HU-03 confirma la respuesta y la transición de forma atómica.
- **RF-006**: El sistema DEBE impedir que un ticket pase directamente de «Abierto» a «Resuelto» o «Cerrado», y de «Pendiente de usuario» a «Resuelto» o «Cerrado».
- **RF-007**: El sistema DEBE permitir la reapertura de «Resuelto» a «En progreso» y registrar el cambio con su autor y fecha.

### Resolución

- **RF-008**: El sistema DEBE exigir una descripción de la solución cuando el estado de destino sea «Resuelto».
- **RF-009**: El sistema DEBE rechazar la transición a «Resuelto» si la descripción está vacía, compuesta solo por espacios en blanco o supera los 5.000 caracteres.
- **RF-010**: Cuando la validación de la resolución falle, el sistema DEBE mantener el estado original, no guardar la solución y no crear ninguna entrada en la línea temporal.
- **RF-011**: Cuando la validación sea correcta, el sistema DEBE guardar de forma conjunta el estado «Resuelto», la descripción de la solución y la entrada de la línea temporal.
- **RF-012**: El sistema DEBE conservar la descripción de la solución asociada al ticket y mostrarla en su línea temporal con autor y fecha y hora.
- **RF-013**: El sistema DEBE mantener visible la resolución después del cierre del ticket.
- **RF-014**: El sistema DEBE conservar las resoluciones anteriores cuando el ticket se reabra y se vuelva a resolver.
- **RF-015**: El sistema DEBE impedir la edición o eliminación de una resolución ya guardada.

### Línea temporal

- **RF-016**: El sistema DEBE registrar cada cambio de estado con estado anterior, estado nuevo, autor, fecha y hora.
- **RF-017**: El sistema DEBE mostrar la línea temporal en orden cronológico.
- **RF-018**: El sistema DEBE distinguir en la línea temporal entre cambios de estado, resoluciones y comentarios internos.
- **RF-019**: El sistema DEBE mostrar al usuario creador los cambios de estado y las resoluciones, pero no los comentarios internos.
- **RF-020**: El sistema DEBE conservar las entradas de la línea temporal aunque el ticket se cierre o se reabra.

### Comentarios internos

- **RF-021**: El sistema DEBE permitir al técnico asignado añadir comentarios internos en cualquier estado del ticket, incluido «Cerrado».
- **RF-022**: El sistema DEBE rechazar comentarios internos vacíos, compuestos solo por espacios en blanco o de más de 5.000 caracteres.
- **RF-023**: El sistema DEBE guardar el comentario interno con autor, fecha y hora, y mostrarlo en la línea temporal identificado como interno.
- **RF-024**: El sistema DEBE garantizar que los comentarios internos solo sean visibles para el técnico actualmente asignado, los supervisores y los administradores, y nunca para el usuario creador ni para técnicos no asignados.
- **RF-025**: El sistema DEBE impedir que un comentario interno cambie el estado del ticket.
- **RF-026**: El sistema DEBE impedir la edición o eliminación de un comentario interno ya guardado.

### Permisos, errores y consistencia

- **RF-027**: El sistema DEBE permitir las operaciones de esta historia únicamente al técnico actualmente asignado al ticket.
- **RF-028**: El sistema DEBE denegar la operación con el mensaje definido en el catálogo de errores (`plan.md` §1.5) cuando el usuario no tenga permiso (`403 forbidden`) o el ticket ya no esté asignado a él (`403 not_ticket_assignee`).
- **RF-029**: El sistema DEBE mostrar mensajes de error en español de España, comprensibles y sin tecnicismos, cuando una validación o un guardado fallen, utilizando los códigos estables y mensajes definidos en `plan.md` §1.5 y en el contrato `contracts/ticket-workflow.openapi.yaml`. La tabla «Casos Límite y Manejo de Errores» de esta especificación solo enumera mensajes orientativos; los códigos normativos no se duplican aquí.
- **RF-030**: El sistema DEBE mantener el ticket sin cambios cuando se produzca un error de validación, de permisos o de concurrencia. Para las transiciones rechazadas, esta regla se concreta en RF-003; para las resoluciones y los comentarios internos, en RF-010 y RF-022.
- **RF-031**: El sistema DEBE detectar y rechazar cambios realizados sobre una versión desactualizada del ticket, solicitando su actualización.
- **RF-032**: El sistema DEBE evitar entradas duplicadas en la línea temporal cuando el técnico envíe dos veces la misma acción. Para las transiciones y para los comentarios internos, el `request_id` es obligatorio y actúa como clave de idempotencia; un reintento idéntico no escribe y devuelve `changed=false` (o `created=false` en el caso de comentarios internos), y la reutilización con distintos datos se rechaza con `409 request_id_reused`.
- **RF-033**: El sistema DEBE mantener la coherencia entre el estado mostrado en el ticket y el último cambio registrado en la línea temporal.
- **RF-034**: El sistema DEBE rechazar con un error de validación (`resolution_not_allowed`) cualquier descripción de solución enviada junto a un estado de destino distinto de «Resuelto», sin modificar el ticket ni crear entradas en la línea temporal. Queda a salvo la idempotencia de RF-032: un reintento con el mismo `request_id` y los mismos datos se resuelve como replay antes de aplicar esta validación.

## Entidades Clave

- **Ticket**: número, título, descripción, estado actual, técnico asignado, usuario creador, fecha de creación, fecha de resolución, fecha de cierre y fecha de última modificación.
- **Cambio de estado**: ticket afectado, estado anterior, estado nuevo, autor, fecha y hora.
- **Resolución**: ticket afectado, descripción de la solución, autor, fecha y hora; queda vinculada a una entrada de la línea temporal y se conserva como histórico.
- **Comentario interno**: ticket afectado, autor, texto, fecha y hora, e indicación de visibilidad interna.
- **Entrada de línea temporal**: ticket afectado, tipo de entrada (cambio de estado, resolución o comentario interno), autor, fecha y hora, contenido y visibilidad.
- **Usuario**: identidad, rol y relación con el ticket como técnico asignado o usuario creador.

## Casos Límite y Manejo de Errores

| Situación | Comportamiento esperado | Mensaje orientativo |
|---|---|---|
| Se intenta pasar a «Resuelto» con la descripción vacía | Se bloquea la operación. El ticket sigue «En progreso» y no se crea entrada en la línea temporal. | «Indica la descripción de la solución para marcar el ticket como Resuelto.» |
| Se intenta pasar a «Resuelto» con espacios en blanco o saltos de línea | Se bloquea igual que en el caso vacío. | «Indica la descripción de la solución para marcar el ticket como Resuelto.» |
| La descripción de la solución supera los 5.000 caracteres | Se bloquea la operación y se conserva el estado original. | «La descripción de la solución no puede superar los 5.000 caracteres.» |
| Se envía una descripción de solución con un destino distinto de «Resuelto» | Se rechaza la operación sin modificar el ticket ni crear entradas. | «La descripción de la solución solo se indica al marcar el ticket como Resuelto.» |
| Se intenta una transición no permitida, por ejemplo «Abierto» → «Resuelto» | Se bloquea la operación y se muestran los estados disponibles. | «No puedes pasar de Abierto a Resuelto. Estados disponibles: En progreso.» |
| Se intenta cambiar el estado de un ticket «Cerrado» | Se bloquea la operación porque el cierre es definitivo. | «El ticket está cerrado y no admite cambios de estado.» |
| Se selecciona el mismo estado que ya tiene el ticket | No se produce ningún cambio ni se crea una entrada en la línea temporal. | «El ticket ya se encuentra en ese estado.» |
| El usuario creador responde a un ticket «Pendiente de usuario» (comportamiento de HU-03; HU-05 solo valida la transición) | El ticket pasa automáticamente a «En progreso» y se registra la transición con autor y fecha. | No requiere mensaje de error. |
| Se intenta añadir un comentario interno vacío o solo con espacios | Se bloquea el guardado y no se crea ninguna entrada. | «El comentario interno no puede estar vacío.» |
| El comentario interno supera los 5.000 caracteres | Se bloquea el guardado y se conserva el texto para que el técnico pueda corregirlo. | «El comentario interno no puede superar los 5.000 caracteres.» |
| Se añade un comentario interno a un ticket «Cerrado» | Se permite y queda registrado en la línea temporal interna. | No aplica. |
| Un usuario sin permiso intenta cambiar el estado o comentar | Se deniega la operación sin modificar el ticket. | «No tienes permiso para modificar este ticket.» |
| El ticket fue reasignado a otro técnico | El técnico anterior no puede modificar el estado ni añadir comentarios. | «Este ticket ya no está asignado a ti.» |
| Otra persona modifica el ticket mientras se está editando | Se rechaza el guardado para no sobrescribir cambios y se pide actualizar. | «El ticket ha sido modificado por otra persona. Actualiza la información e inténtalo de nuevo.» |
| Se pulsa dos veces seguidas sobre «Guardar» | Solo se registra una entrada en la línea temporal y un único cambio de estado. | No requiere mensaje de error. |
| Se reutiliza el `request_id` de una transición con otro destino o resolución | Se rechaza sin modificar el ticket ni la línea temporal. | «La solicitud ya se utilizó con otros datos. Genera una nueva solicitud e inténtalo de nuevo.» |
| Falta el `request_id` o no es un UUID válido en una transición o en un comentario interno | Se rechaza la operación sin modificar el ticket ni la línea temporal. | «La solicitud no es válida. Revisa los datos e inténtalo de nuevo.» |
| Falta `expected_updated_at` o no tiene un formato de fecha válido en una transición | Se rechaza la operación sin modificar el ticket ni la línea temporal. | «La solicitud no es válida. Revisa los datos e inténtalo de nuevo.» |
| Se produce un fallo al guardar el cambio | No se modifica el estado ni la línea temporal; el técnico puede reintentar. | «No se pudo guardar el cambio. El ticket no se ha modificado. Inténtalo de nuevo.» |
| El ticket ya no existe o no se puede consultar | Se muestra un error y no se realiza ningún cambio. | «No se ha encontrado el ticket.» |
| El usuario creador consulta un ticket con comentarios internos | Ve los cambios de estado y las resoluciones, pero no los comentarios internos. | No aplica. |
| Un técnico no asignado intenta consultar los comentarios internos | No los ve; solo el técnico asignado, los supervisores y los administradores tienen acceso a la información interna. | No aplica. |

## Criterios de Éxito

| ID | Métrica | Objetivo |
|---|---|---|
| SC-001 | Transiciones fuera de la matriz de RN-02 bloqueadas | 100% de los intentos |
| SC-002 | Tickets en estado «Resuelto» sin descripción de solución | 0 casos entre los resueltos desde la migración `0003_ticket_timeline` (corte operativo de la implantación); el legado anterior se audita y se lista, no se corrige automáticamente |
| SC-003 | Intentos de resolver sin descripción que modifican el ticket | 0 casos |
| SC-004 | Resoluciones visibles en la línea temporal tras el cambio de estado | 100% en menos de 2 segundos |
| SC-005 | Comentarios internos disponibles en cualquier estado, incluido «Cerrado» | 100% de los estados |
| SC-006 | Comentarios internos visibles para el usuario creador o para técnicos no asignados | 0 casos |
| SC-007 | Entradas duplicadas por doble envío | 0 casos |
| SC-008 | Tiempo para cambiar estado y documentar la resolución | Menos de 60 segundos para un técnico habitual |
| SC-009 | Técnicos que completan el cambio de estado y la resolución en el primer intento | Al menos 95% |
| SC-010 | Cambios de estado reflejados en la línea temporal | 100% en menos de 2 segundos |

## Supuestos

1. El sistema ya dispone de tickets con estado, técnico asignado y usuario creador, según las historias HU-01 y HU-02.
2. La autenticación y los roles ya existen; esta historia no define el mecanismo de acceso.
3. Cada ticket tiene un único técnico asignado en cada momento.
4. El usuario creador puede consultar el ticket y su línea temporal pública, pero no dispone de acciones de cambio de estado en esta historia.
5. Los comentarios internos son de texto en esta historia; los adjuntos se rigen por RF-05 y no forman parte de este alcance.
6. La resolución se considera un registro histórico inmutable; las correcciones se realizan mediante un nuevo comentario interno o una nueva resolución tras reabrir el ticket.
7. El cierre es manual por parte del técnico; no existe cierre automático por tiempo en esta historia.
8. Las fechas y horas se muestran en la zona horaria de España.
9. La historia no incluye notificaciones por correo ni en la aplicación; se rigen por RF-08.
10. Un ticket «Cerrado» no se reabre en esta versión; si el problema reaparece, se crea un ticket nuevo.
11. Los técnicos no asignados pueden consultar la línea temporal pública (cambios de estado y resoluciones), pero no los comentarios internos ni realizar cambios de estado o comentarios.
12. Los tickets resueltos o cerrados antes de la migración `0003_ticket_timeline` (corte operativo de la implantación de HU-05) se consideran legado: no se les exige una resolución retroactiva y la migración no altera sus datos.

## Fuera de Alcance

- Reapertura de tickets «Cerrados».
- Edición o eliminación de entradas de la línea temporal, resoluciones o comentarios internos.
- Adjuntos en comentarios internos.
- Notificaciones al usuario o al técnico por cambios de estado.
- Cierre automático de tickets resueltos.
- Confirmación o rechazo de la resolución por parte del usuario creador.
- Cambios masivos de estado.
- Estados personalizados o flujos configurables por categoría.
- Motivos obligatorios para transiciones distintas de «Resuelto».
- Contenido obligatorio de la solicitud de información al pasar a «Pendiente de usuario» (se rige por HU-03).

## Dependencias

- HU-01: creación de tickets y asignación inicial.
- HU-02: consulta del estado y línea temporal del ticket.
- HU-03: respuesta del usuario a la solicitud de información y transición automática desde «Pendiente de usuario».
- RF-02: definición del flujo de estados del sistema.
- Sistema de autenticación y autorización por roles.
- Mecanismo de registro cronológico de la línea temporal del ticket.

## Trazabilidad de los Criterios de Aceptación

| Criterio de aceptación de HU-05 | Reglas de negocio | Requisitos funcionales |
|---|---|---|
| El técnico puede cambiar el estado entre los valores definidos (Abierto → En progreso → Resuelto → Cerrado). | RN-01, RN-02, RN-07, RN-08 | RF-001 a RF-007, RF-027 a RF-033 |
| Al mover a «Resuelto», el sistema requiere obligatoriamente una descripción de la solución. | RN-03, RN-04 | RF-008 a RF-011, RF-029, RF-030 |
| La solución queda guardada y visible en la línea temporal. | RN-04, RN-05, RN-09 | RF-012 a RF-020 |
| El técnico puede añadir comentarios internos en cualquier momento. | RN-06, RN-07 | RF-021 a RF-026 |
