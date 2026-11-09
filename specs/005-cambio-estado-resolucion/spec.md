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
