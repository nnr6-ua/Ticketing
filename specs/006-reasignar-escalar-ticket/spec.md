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
- Q: ¿Qué canal debe usar la «notificación inmediata» al nuevo responsable? → A: Solo la notificación dentro de la aplicación (campana con contador de no leídas), conforme a HU06-RF-08.1 del sistema. El correo electrónico y las notificaciones push quedan fuera del alcance y se rigen por HU06-RF-08.2. (Confirmado en clarificación, 2026-11-10.)
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
- La notificación se entrega dentro de la aplicación; el correo electrónico y las notificaciones push quedan fuera del alcance (HU06-RF-08.2).
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

- La reasignación se rechaza si el técnico destino no existe, no está activo, no tiene rol técnico, no pertenece al mismo equipo y nivel que el responsable actual conforme a HU06-RN-03, es el propio responsable o es el usuario creador del ticket.
- El escalado se rechaza si el nivel destino no es superior al del responsable actual o si no hay técnicos activos en ese nivel que puedan recibir el ticket (excluido el usuario creador).
- Los candidatos y niveles ofrecidos en la interfaz se recalculan en el momento de la operación; un destino válido al abrir el formulario puede dejar de serlo al confirmar.

## Requisitos Funcionales

### Reasignación

- **HU06-RF-001**: El sistema DEBE permitir al técnico actualmente asignado reasignar el ticket a otro técnico candidato conforme a HU06-RN-03.
- **HU06-RF-002**: El sistema DEBE mostrar la lista de candidatos de reasignación con nombre y equipo de cada técnico, excluyendo al responsable actual y al usuario creador del ticket.
- **HU06-RF-003**: El sistema DEBE exigir un motivo de entre 1 y 5.000 caracteres en toda reasignación.
- **HU06-RF-004**: El sistema DEBE rechazar la reasignación cuando el destino no cumpla HU06-RN-03 o HU06-RN-14, manteniendo el responsable original y sin crear entradas en la línea temporal.
- **HU06-RF-005**: El sistema DEBE impedir que el técnico se reasigne el ticket a sí mismo.

### Escalado

- **HU06-RF-006**: El sistema DEBE permitir al técnico actualmente asignado escalar el ticket a un nivel de escalado superior al del responsable actual, conforme a HU06-RN-02.
- **HU06-RF-007**: El sistema DEBE ofrecer únicamente niveles de destino superiores al nivel del responsable actual.
- **HU06-RF-008**: El sistema DEBE seleccionar al nuevo responsable del escalado conforme a la regla determinista de HU06-RN-04.
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
- **Cross-reference**: Reglas de autorización compatibles con HU06-RN-10 y HU06-RN-11 del plan: rol no técnico ⇒ `403 forbidden`; creador técnico no asignado ⇒ `forbidden` con precedencia sobre `not_ticket_assignee`; creador asignado vigente ⇒ puede operar; técnico anterior no creador ⇒ `not_ticket_assignee`. Ver también HU06-RN-10 y HU06-RN-11 para reglas de autorización.
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
8. La notificación inmediata se entrega dentro de la aplicación (campana); el correo electrónico y las notificaciones push quedan fuera del alcance y se rigen por HU06-RF-08.2.
9. La reasignación y el escalado no alteran el estado, la prioridad, la categoría ni el límite de SLA del ticket.
10. Las fechas y horas se muestran en la zona horaria de España (Europe/Madrid) y se almacenan en UTC.
11. Las notificaciones de esta historia se dirigen únicamente al nuevo responsable.
12. El usuario creador del ticket no es candidato de reasignación ni de escalado, aunque tenga rol técnico.
13. La reasignación se restringe a técnicos del mismo equipo y nivel que el responsable actual; para pasar el ticket a un nivel superior existe el escalado.
14. La visibilidad de los comentarios internos tras el traspaso se rige por la HU-05 (HU05-RN-06 y HU05-RN-07).

## Fuera de Alcance

- Reasignación o escalado masivo de varios tickets a la vez.
- Escalado a equipos externos, proveedores o terceros.
- Notificaciones por correo electrónico o push (se rigen por HU06-RF-08.2).
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
- HU-04: cola de trabajo priorizada y sus reglas de propiedad y refresco (HU04-RN-01, HU04-RN-12 y HU04-RF-005).
- HU-05: línea temporal «append-only», matriz de estados, permisos del técnico asignado e idempotencia (HU05-RN-02, HU05-RN-04, HU05-RN-06, HU05-RN-07).
- HU06-RF-03 del sistema: asignación y escalado de tickets.
- HU06-RF-08.1 del sistema: notificaciones dentro de la aplicación.
- Sistema de autenticación y autorización por roles.

## Trazabilidad de los Criterios de Aceptación

| Criterio de aceptación de HU-06 | Reglas de negocio | Requisitos funcionales |
|---|---|---|
| El técnico puede seleccionar otro técnico de la lista del equipo para reasignar. | HU06-RN-01, HU06-RN-03, HU06-RN-14 | HU06-RF-001 (integra el antiguo requisito separado), HU06-RF-024 a HU06-RF-026 |
| El técnico puede escalar a un nivel superior (ej: «Nivel 2», «Especialista»). | HU06-RN-01, HU06-RN-02, HU06-RN-04, HU06-RN-14 | HU06-RF-006 a HU06-RF-010, HU06-RF-024 a HU06-RF-026 |
| Al reasignar/escalar, el nuevo responsable recibe notificación inmediata. | HU06-RN-08, HU06-RN-12 | HU06-RF-016 a HU06-RF-020, HU06-RF-028 |
| El cambio de responsable queda registrado en la línea temporal con autor y motivo. | HU06-RN-05, HU06-RN-07, HU06-RN-13 | HU06-RF-011 a HU06-RF-015, HU06-RF-029, HU06-RF-030 |
| El ticket pasa a la cola de trabajo del nuevo responsable. | HU06-RN-09, HU06-RN-10, HU06-RN-12 | HU06-RF-021 a HU06-RF-023, HU06-RF-031, HU06-RF-033 |
| Solo el técnico asignado puede reasignar o escalar, y solo en estados activos. | HU06-RN-06, HU06-RN-11 | HU06-RF-024 a HU06-RF-026 |

---

## Módulos previos (referencias)

Los módulos HU-04 y HU-05 no se reproducen en este documento: sus escenarios, reglas de negocio y criterios de aceptación son propiedad exclusiva de sus especificaciones de origen.

- [Cola de trabajo priorizada (HU-04)](../004-prioritized-work-queue/spec.md)
- [Cambio de estado y documentación de resolución (HU-05)](../005-cambio-estado-resolucion/spec.md)

Las reglas y requisitos de HU-06 se apoyan en ellos sin redefinirlos. Ante cualquier discrepancia prevalecen los documentos de origen. La verificación de conservación realizada el 2026-11-10 quedó registrada en `checklists/requirements.md`.
