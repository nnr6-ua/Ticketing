# Especificación: Responder a la petición de información del técnico (HU-03)

**Rama**: `hu-03-responder-tecnico`

**Creado**: 2026-11-13

**Estado**: Borrador

**Entrada**: Descripción del usuario: "A veces el técnico necesita más información para poder avanzar, y en ese caso el usuario debe poder responder a esa petición concreta directamente desde el propio ticket, de forma que, en cuanto lo haga, el ticket cambie de estado y quede claro que ahora la pelota vuelve a estar en el tejado del equipo técnico. Tiene que tener coherencia con lo hecho anteriormente, tanto en estética como en funcionalidad, sin romper lo hecho anteriormente."

## Resumen

Cuando el técnico asignado no puede continuar con la resolución de un ticket, puede solicitar al usuario creador la información concreta que necesita. El ticket pasa a «Pendiente de usuario» y la solicitud queda visible en el propio ticket. El usuario recibe un aviso, accede al ticket y responde directamente desde esa vista. Al enviar su respuesta, el ticket vuelve automáticamente a «En progreso» y la respuesta queda registrada en la línea temporal pública.

La historia completa el ciclo de colaboración entre usuario y técnico: el usuario aporta la información que se le pide y el ticket regresa a la cola de trabajo del equipo técnico, dejando constancia de la petición, de la respuesta, de su autor y de la fecha y hora de cada una.

Esta historia se apoya en lo ya construido: reutiliza los estados y la línea temporal de HU-05, la vista de consulta de HU-02 y la cola de trabajo de HU-04, y mantiene la misma estética y los mismos patrones de interacción del resto de la aplicación.

## Clarifications

### Session 2026-11-13

- Q: ¿La solicitud de información debe exigir un mensaje concreto del técnico al marcar el ticket como «Pendiente de usuario»? → A: Sí en la acción específica de HU-03: el técnico debe escribir qué información necesita. La transición genérica de HU-05 se mantiene válida para no romper tickets ni flujos anteriores; los tickets pendientes sin mensaje previo siguen admitiendo respuesta.
- Q: ¿La respuesta del usuario debe ser un texto obligatorio o puede ser una acción sin contenido? → A: Texto obligatorio, porque la respuesta es precisamente la información solicitada; no se admite una respuesta vacía ni compuesta solo por espacios.
- Q: ¿Qué canales de aviso al usuario se incluyen? → A: Solo aviso dentro de la aplicación (indicador de ticket pendiente y aviso en la vista del ticket). El correo electrónico queda fuera de alcance en esta historia.
- Q: ¿Se debe incluir una campana o centro de notificaciones para el aviso? → A: No. El aviso es contextual: marca visual del ticket como «Pendiente de usuario» en la lista y aviso con la petición dentro de la vista del ticket.
- Q: ¿La respuesta del usuario puede incluir adjuntos? → A: No en esta historia. Los adjuntos siguen limitados a la creación del ticket según lo definido en HU-01.
- Q: ¿El técnico recibe un aviso adicional cuando el usuario responde? → A: No. Basta con el cambio a «En progreso» y la reaparición del ticket en su cola de trabajo; la respuesta se consulta en la línea temporal.
- Q: ¿Cómo se relacionan visualmente la petición y la respuesta en la línea temporal? → A: Como entradas cronológicas independientes, cada una con su autor, fecha, hora y tipo; no se agrupan ni se citan como un hilo aparte.
- Q: ¿Qué debe hacer el sistema si el usuario no responde? → A: Enviar un único recordatorio contextual a las 48 horas sin respuesta; no hay recordatorios periódicos ni escalado automático.
- Q: ¿Dónde escribe el técnico la petición de información? → A: En el panel de cambio de estado ya existente: al seleccionar «Pendiente de usuario» se despliega el campo con la petición, sin crear una pantalla ni una acción separada.

## Actores

- **Usuario creador / solicitante**: recibe el aviso, consulta la petición concreta y responde desde la vista del ticket.
- **Técnico asignado**: solicita la información y recupera el ticket cuando el usuario responde.
- **Supervisor / administrador**: consultan la petición y la respuesta para la trazabilidad; no responden en nombre del usuario dentro de esta historia.

## Reglas de Negocio

### HU03-RN-01 — Solicitud de información del técnico

- Solo el técnico actualmente asignado puede solicitar información sobre el ticket.
- La solicitud se realiza sobre un ticket en estado «En progreso» y lo mueve a «Pendiente de usuario».
- La solicitud exige un mensaje con la información concreta que necesita el técnico.
- La petición se escribe en el panel de cambio de estado ya existente; al seleccionar «Pendiente de usuario» se despliega el campo de mensaje, sin pantallas ni acciones adicionales.
- El mensaje debe contener entre 1 y 5.000 caracteres una vez eliminados los espacios al principio y al final.
- La solicitud queda registrada en la línea temporal pública con el texto, el autor (técnico), la fecha y la hora, y el cambio de estado asociado.
- Solo puede existir una solicitud activa por ticket. Mientras el ticket esté «Pendiente de usuario», no se puede crear otra solicitud hasta que el usuario responda.
- La solicitud no se puede editar ni eliminar una vez enviada.

### HU03-RN-02 — Aviso al usuario

- Cuando un ticket pasa a «Pendiente de usuario» por una solicitud de información, el usuario creador recibe un aviso contextual dentro de la aplicación.
- El aviso identifica el ticket afectado e indica que se requiere su respuesta.
- El aviso se limita a la lista de tickets y a la vista del ticket; esta historia no incluye campana ni centro de notificaciones.
- El ticket se muestra claramente como «Pendiente de usuario» en la lista de tickets del usuario creador.
- En la vista del ticket se muestra la petición concreta del técnico junto al estado actual.
- El aviso deja de estar activo cuando el usuario responde, sin que ello modifique el texto ya registrado de la petición.
- Si el usuario no responde en las 48 horas siguientes al paso a «Pendiente de usuario», el sistema muestra un único recordatorio contextual en la lista de tickets y en la vista del ticket.
- El recordatorio no se repite y no provoca escalado automático ni cambio de estado.

### HU03-RN-03 — Respuesta del usuario

- Solo el usuario creador del ticket puede responder a la solicitud.
- La respuesta solo se admite cuando el ticket está en estado «Pendiente de usuario».
- La respuesta exige un texto de entre 1 y 5.000 caracteres una vez eliminados los espacios al principio y al final.
- La respuesta está vinculada a la solicitud activa del ticket; si no existe una solicitud previa registrada, se admite igualmente como respuesta genérica a la espera de información.
- Al enviar la respuesta, el sistema cambia el estado del ticket a «En progreso» y registra la respuesta en la línea temporal pública.
- La respuesta queda registrada con el texto, el autor (usuario creador), la fecha y la hora, y el cambio de estado asociado.
- El cambio de estado y el registro de la respuesta ocurren como una única operación: si falla uno, no se guarda ninguno.
- La respuesta no se puede editar ni eliminar una vez enviada.
- Una respuesta enviada con éxito no puede repetirse sobre el mismo ciclo de solicitud; los reintentos no generan entradas duplicadas.

### HU03-RN-04 — La pelota vuelve al equipo técnico

- Tras la respuesta del usuario, el ticket deja de estar «Pendiente de usuario» y pasa a «En progreso».
- El ticket vuelve a estar visible como activo en la cola de trabajo del técnico asignado.
- El técnico asignado puede ver la respuesta del usuario en la línea temporal del ticket.
- El técnico no recibe un aviso adicional: el cambio a «En progreso» y la reaparición en su cola de trabajo son la señal de que el ticket ha vuelto a su responsabilidad.
- El aviso de respuesta pendiente del usuario queda resuelto en el mismo momento en que se registra la respuesta.
- Si el ticket no tiene técnico asignado en el momento de la respuesta, el ticket pasa igualmente a «En progreso» y queda disponible en la cola colectiva del equipo técnico.

### HU03-RN-05 — Permisos y visibilidad

- El usuario creador solo puede responder a sus propios tickets.
- El usuario creador no puede cambiar el estado del ticket a ningún otro valor ni solicitar información.
- El técnico asignado no puede responder en nombre del usuario creador.
- Supervisores y administradores pueden consultar la solicitud y la respuesta, pero no responder en nombre del usuario.
- La solicitud y la respuesta son públicas: las ven el usuario creador, el técnico asignado, los supervisores y los administradores.
- Los comentarios internos del técnico siguen ocultos para el usuario creador, conforme a HU-05.
- Un ticket ajeno se trata como no accesible: no se revela su existencia ni su contenido.

### HU03-RN-06 — Trazabilidad e inmutabilidad

- La petición de información y la respuesta del usuario generan entradas independientes en la línea temporal.
- Cada entrada muestra su autor, fecha y hora.
- Las entradas de petición y respuesta se ordenan cronológicamente con el resto de la línea temporal, sin agruparse en hilos ni citarse entre sí.
- Las entradas de petición y respuesta no se pueden editar ni eliminar.
- El cambio de estado asociado a la respuesta aparece en la línea temporal con estado anterior «Pendiente de usuario» y estado nuevo «En progreso».

### HU03-RN-07 — Concurrencia e idempotencia

- Un doble envío de la misma respuesta no debe generar dos entradas ni dos cambios de estado.
- Si el ticket ha cambiado entre la carga de la vista y el envío, el sistema rechaza la respuesta y pide actualizar la información, sin modificar el ticket.
- Si dos intentos de respuesta compiten por el mismo ticket, solo uno puede aplicarse; el otro se rechaza sin dejar cambios parciales.
- La respuesta solo se aplica si el ticket sigue en «Pendiente de usuario» en el momento de guardar.

### HU03-RN-08 — Compatibilidad con lo ya construido

- Se mantienen los cinco estados existentes: «Abierto», «En progreso», «Pendiente de usuario», «Resuelto» y «Cerrado».
- Se mantiene el flujo de estados de HU-05, incluida la transición manual de «Pendiente de usuario» a «En progreso».
- Los tickets que ya estén «Pendiente de usuario» sin mensaje de solicitud pueden recibir respuesta del usuario.
- Los tickets «Resueltos» o «Cerrados» no admiten respuesta del usuario.
- La estética, los componentes de estado, la línea temporal y los mensajes de error siguen los patrones ya usados en la aplicación.

## Escenarios de Usuario y Pruebas

### Historia 1 — Responder a la petición de información (Prioridad: P1)

Como usuario creador, quiero responder a la petición concreta del técnico directamente desde mi ticket, para aportar la información que necesita y que el trabajo continúe.

**Por qué esta prioridad**: es el núcleo de la historia; sin la respuesta del usuario el ticket queda bloqueado y el equipo técnico no puede avanzar.

**Prueba independiente**: partiendo de un ticket «Pendiente de usuario» con una petición visible del técnico, el usuario creador escribe una respuesta, la envía y comprueba que el ticket pasa a «En progreso» y que la respuesta aparece en la línea temporal.

**Escenarios de aceptación**:

1. **Dado** un ticket «Pendiente de usuario» con una petición de información del técnico, **cuando** el usuario creador accede a la vista del ticket, **entonces** ve la petición concreta y un campo para responder.
2. **Dado** un ticket «Pendiente de usuario» mostrado al usuario creador, **cuando** introduce una respuesta válida y la envía, **entonces** el estado del ticket cambia a «En progreso» y la respuesta queda registrada en la línea temporal con su nombre, fecha y hora.
3. **Dado** un ticket «Pendiente de usuario», **cuando** el usuario creador intenta enviar una respuesta vacía o compuesta solo por espacios, **entonces** el sistema no cambia el estado y muestra un mensaje indicando que la respuesta es obligatoria.
4. **Dado** un ticket «Pendiente de usuario», **cuando** el usuario creador intenta enviar una respuesta de más de 5.000 caracteres, **entonces** el sistema no cambia el estado y muestra el límite permitido.
5. **Dado** un ticket que no pertenece al usuario, **cuando** intenta responder, **entonces** el sistema deniega el acceso sin revelar el contenido del ticket.

---

### Historia 2 — Ver que el técnico necesita información (Prioridad: P1)

Como usuario creador, quiero saber que mi ticket está esperando una respuesta mía y qué información concreta se me pide, para poder responder sin tener que contactar con el equipo técnico.

**Por qué esta prioridad**: sin un aviso claro y sin ver la petición, el usuario no sabría que debe actuar y el ticket quedaría bloqueado indefinidamente.

**Prueba independiente**: el técnico solicita información en un ticket y el usuario creador comprueba que aparece el ticket como «Pendiente de usuario», que recibe un aviso en la aplicación y que puede leer la petición concreta.

**Escenarios de aceptación**:

1. **Dado** un ticket «En progreso» asignado a un técnico, **cuando** el técnico solicita información con un mensaje concreto, **entonces** el ticket pasa a «Pendiente de usuario» y la petición queda visible en la línea temporal pública.
2. **Dado** un ticket recién puesto en «Pendiente de usuario», **cuando** el usuario creador consulta su lista de tickets, **entonces** ve el ticket marcado como «Pendiente de usuario».
3. **Dado** un ticket en «Pendiente de usuario», **cuando** el usuario creador abre su vista, **entonces** ve un aviso de que se requiere su respuesta y el texto de la petición del técnico.
4. **Dado** un ticket pendiente, **cuando** el usuario creador responde, **entonces** el aviso de respuesta pendiente deja de mostrarse.

---

### Historia 3 — Devolver el ticket al equipo técnico y dejar constancia (Prioridad: P2)

Como usuario creador, quiero que al responder el ticket vuelva al equipo técnico y quede constancia de mi respuesta, para saber que el proceso continúa y que no se ha perdido información.

**Por qué esta prioridad**: completa la percepción de continuidad del proceso y aporta trazabilidad, aunque la respuesta válida ya desbloquea el ticket sin necesidad de más señales.

**Prueba independiente**: tras responder, el usuario comprueba que el ticket figura «En progreso», que el técnico ve la respuesta y que la línea temporal contiene la petición y la respuesta con sus autores y fechas.

**Escenarios de aceptación**:

1. **Dado** un ticket «Pendiente de usuario», **cuando** el usuario responde, **entonces** el ticket pasa a «En progreso» y vuelve a la cola de trabajo del técnico asignado.
2. **Dado** un ticket respondido por el usuario, **cuando** el técnico consulta la línea temporal, **entonces** ve la petición y la respuesta con sus autores, fechas y horas.
3. **Dado** un ticket respondido por el usuario, **cuando** el usuario consulta la línea temporal, **entonces** ve su propia respuesta y el cambio de estado, sin ver comentarios internos del técnico.
4. **Dado** un ticket «Resuelto» o «Cerrado», **cuando** el usuario intenta responder, **entonces** el sistema no muestra la acción de respuesta y rechaza cualquier envío.

## Casos Límite y Manejo de Errores

| Situación | Comportamiento esperado |
|---|---|
| Respuesta vacía o solo con espacios | Se impide el envío, no cambia el estado y se indica que la respuesta es obligatoria. |
| Respuesta de más de 5.000 caracteres | Se impide el envío y se indica el límite máximo. |
| Ticket que ya no está «Pendiente de usuario» al enviar | Se rechaza la respuesta, se mantiene el estado actual y se pide actualizar la información. |
| Ticket «Resuelto» o «Cerrado» | No se ofrece la acción de respuesta y cualquier envío se rechaza sin cambios. |
| Doble envío o reintento de red | Se registra una sola respuesta y un solo cambio de estado; el reintento devuelve el resultado ya aplicado. |
| Usuario distinto del creador intenta responder | Se deniega el acceso sin revelar el ticket. |
| Ticket pendiente sin mensaje de solicitud previo | Se muestra un aviso genérico de que el equipo técnico necesita información y se permite la respuesta. |
| Ticket sin técnico asignado al responder | El ticket pasa a «En progreso» y queda disponible en la cola colectiva del equipo técnico. |
| Varias solicitudes en ciclos sucesivos | Cada respuesta se vincula a la solicitud activa más reciente; las anteriores se conservan en la línea temporal. |
| Usuario que no responde | A las 48 horas se muestra un único recordatorio contextual; el ticket sigue «Pendiente de usuario» sin cambios de estado ni escalado. |
| Pérdida de conexión durante el envío | El usuario recibe un aviso de que la respuesta no se ha confirmado y puede reintentar sin duplicar entradas. |
| Caracteres especiales o texto pegado | Se conservan y muestran tal cual, sin romper el guardado ni la visualización. |

## Requisitos Funcionales

- **HU03-RF-001**: El sistema DEBE permitir al técnico asignado solicitar información concreta sobre un ticket en estado «En progreso».
- **HU03-RF-002**: El sistema DEBE exigir un mensaje de solicitud de entre 1 y 5.000 caracteres al usar la acción de solicitar información de esta historia.
- **HU03-RF-003**: El sistema DEBE mover el ticket a «Pendiente de usuario» al registrar la solicitud de información.
- **HU03-RF-004**: El sistema DEBE registrar la solicitud en la línea temporal pública con el texto, el autor, la fecha y la hora, y el cambio de estado asociado.
- **HU03-RF-005**: El sistema DEBE impedir más de una solicitud activa mientras el ticket permanezca en «Pendiente de usuario».
- **HU03-RF-006**: El sistema DEBE mostrar al usuario creador un aviso contextual dentro de la aplicación de que su ticket requiere una respuesta, sin campana ni centro de notificaciones.
- **HU03-RF-007**: El sistema DEBE mostrar el ticket como «Pendiente de usuario» en la lista de tickets del usuario creador y mostrar la petición concreta en la vista del ticket.
- **HU03-RF-008**: El sistema DEBE permitir al usuario creador responder únicamente a sus propios tickets y únicamente cuando estén en «Pendiente de usuario».
- **HU03-RF-009**: El sistema DEBE exigir una respuesta de entre 1 y 5.000 caracteres y rechazar respuestas vacías o compuestas solo por espacios.
- **HU03-RF-010**: El sistema DEBE cambiar el estado del ticket a «En progreso» al registrar la respuesta del usuario.
- **HU03-RF-011**: El sistema DEBE registrar la respuesta en la línea temporal pública con el texto, el autor, la fecha y la hora, y el cambio de estado asociado.
- **HU03-RF-012**: El sistema DEBE aplicar el cambio de estado y el registro de la respuesta como una única operación atómica.
- **HU03-RF-013**: El sistema DEBE devolver el ticket respondido a la cola de trabajo del técnico asignado o, si no lo hay, a la cola colectiva del equipo técnico.
- **HU03-RF-014**: El sistema DEBE resolver el aviso de respuesta pendiente en cuanto el usuario responde.
- **HU03-RF-015**: El sistema DEBE impedir que la solicitud o la respuesta se editen o eliminen una vez registradas.
- **HU03-RF-016**: El sistema DEBE evitar respuestas y entradas de línea temporal duplicadas ante reintentos o dobles envíos.
- **HU03-RF-017**: El sistema DEBE rechazar la respuesta sin modificar el ticket si este cambió desde que se cargó la vista.
- **HU03-RF-018**: El sistema DEBE denegar el acceso a la respuesta de tickets ajenos sin revelar su existencia.
- **HU03-RF-019**: El sistema DEBE mantener ocultos para el usuario creador los comentarios internos del técnico.
- **HU03-RF-020**: El sistema DEBE permitir responder a tickets ya «Pendiente de usuario» aunque no tengan un mensaje de solicitud previo, mostrando un aviso genérico.
- **HU03-RF-021**: El sistema DEBE conservar los estados, transiciones y patrones visuales ya existentes, sin alterar el funcionamiento previo de HU-02, HU-04 y HU-05.
- **HU03-RF-022**: El sistema DEBE mostrar un único recordatorio contextual al usuario creador si no responde en las 48 horas siguientes al paso a «Pendiente de usuario», sin repetirlo, sin escalar el ticket y sin cambiar su estado.
- **HU03-RF-023**: El sistema DEBE integrar la escritura de la petición en el panel de cambio de estado existente, mostrando el campo de mensaje al seleccionar «Pendiente de usuario» y sin añadir una pantalla o acción separada.

## Entidades Clave

- **Ticket**: incidencia sobre la que se solicita y se aporta información. Incluye número, título, estado actual, usuario creador y técnico asignado.
- **Solicitud de información**: petición concreta del técnico asignado. Incluye el texto solicitado, el ticket, el técnico autor y la fecha y hora. Queda vinculada al paso a «Pendiente de usuario».
- **Respuesta del usuario**: información aportada por el usuario creador. Incluye el texto, el ticket, el usuario autor, la fecha y hora y la solicitud a la que responde.
- **Entrada de línea temporal**: registro público e inmutable de la solicitud, de la respuesta y de los cambios de estado asociados, con autor, fecha y hora.
- **Aviso de respuesta pendiente**: señal contextual dentro de la aplicación (lista de tickets y vista del ticket) dirigida al usuario creador que indica que su ticket espera respuesta y que se resuelve al responder.
- **Recordatorio de respuesta**: segundo aviso contextual, mostrado una sola vez a las 48 horas sin respuesta, que insiste en que el ticket sigue esperando al usuario.
- **Técnico asignado**: responsable actual del ticket; solicita la información y recibe de vuelta el ticket tras la respuesta.

## Criterios de Éxito

| ID | Métrica | Objetivo |
|---|---|---|
| HU03-SC-001 | Verifica HU03-RF-001 a HU03-RF-005: solicitudes de información registradas con mensaje y paso a «Pendiente de usuario» | 100% |
| HU03-SC-002 | Verifica HU03-RF-008 a HU03-RF-012: respuestas válidas que cambian el ticket a «En progreso» y quedan en la línea temporal | 100% |
| HU03-SC-003 | Verifica HU03-RF-006 y HU03-RF-007: usuarios creadores que ven el aviso y la petición concreta | 100% |
| HU03-SC-004 | Verifica HU03-RF-016: reintentos o dobles envíos que generan entradas duplicadas | 0 casos |
| HU03-SC-005 | Verifica HU03-RF-018: intentos de respuesta sobre tickets ajenos denegados | 100% |
| HU03-SC-006 | Verifica HU03-RF-013: tickets respondidos que vuelven a la cola del técnico como «En progreso» | 100% |
| HU03-SC-007 | Tiempo que tarda el usuario en localizar la petición y enviar su respuesta | Menos de 2 minutos |
| HU03-SC-008 | Un usuario no técnico completa la petición y la respuesta usando solo la app, sin crear un ticket nuevo ni un comentario externo | 100% de los casos del quickstart |
| HU03-SC-009 | Verifica HU03-RF-022: tickets pendientes que reciben exactamente un recordatorio a las 48 horas sin respuesta | 100% |

## Supuestos

1. La autenticación y los roles ya existen; esta historia no define el mecanismo de acceso.
2. El ticket tiene un usuario creador y, salvo excepciones, un técnico asignado cuando se solicita información.
3. La línea temporal y los estados definidos en HU-05 se reutilizan sin cambios de flujo.
4. El aviso al usuario es exclusivamente dentro de la aplicación; el correo electrónico queda fuera de esta historia.
5. La respuesta del usuario es texto plano, sin adjuntos y sin formato enriquecido.
6. Solo hay una solicitud activa por ciclo; si el técnico vuelve a necesitar información tras una respuesta, se inicia un nuevo ciclo conservando el anterior en el historial.
7. Las fechas y horas se muestran en la zona horaria de España (Europe/Madrid) y se almacenan en UTC.
8. Los tickets que ya estén «Pendiente de usuario» sin mensaje de solicitud previo siguen siendo respondibles para no romper datos existentes.
9. La transición manual de «Pendiente de usuario» a «En progreso» de HU-05 se mantiene disponible para el técnico.
10. El plazo de 48 horas del recordatorio se cuenta en horas naturales desde el paso del ticket a «Pendiente de usuario».

## Fuera de Alcance

- Conversación en tiempo real o chat dentro del ticket.
- Adjuntar imágenes o archivos en la respuesta del usuario.
- Notificaciones por correo electrónico o por canales externos.
- Campana o centro de notificaciones dentro de la aplicación.
- Que el usuario cambie el estado del ticket a valores distintos de la respuesta.
- Reabrir tickets «Resueltos» o «Cerrados» desde esta historia.
- Editar o eliminar solicitudes, respuestas o entradas de la línea temporal.
- Múltiples solicitudes simultáneas sobre un mismo ticket.
- Preferencias configurables de notificación.
- Avisos adicionales al técnico distintos del cambio de estado y la cola de trabajo.
- Recordatorios periódicos, múltiples recordatorios al usuario o escalado automático por falta de respuesta.
- Cambios en el cálculo de plazos SLA.
- Historial de lectura de avisos más allá de su resolución al responder.

## Dependencias

- **HU-01**: creación de tickets y usuario creador.
- **HU-02**: consulta del estado y de la línea temporal pública.
- **HU-04**: cola de trabajo del técnico, donde vuelve el ticket respondido.
- **HU-05**: estados, transiciones, línea temporal, comentarios internos y transición automática de «Pendiente de usuario» a «En progreso».
- Sistema de autenticación y autorización por roles.
- Mecanismo de avisos dentro de la aplicación.

## Trazabilidad de los Criterios de Aceptación

| Criterio de aceptación | Reglas de negocio | Requisitos funcionales |
|---|---|---|
| El técnico solicita información concreta y el ticket pasa a «Pendiente de usuario» | HU03-RN-01, HU03-RN-08 | HU03-RF-001, HU03-RF-002, HU03-RF-003, HU03-RF-004, HU03-RF-005, HU03-RF-021, HU03-RF-023 |
| El usuario ve el aviso y la petición concreta | HU03-RN-02 | HU03-RF-006, HU03-RF-007 |
| El usuario responde desde el ticket y el estado pasa a «En progreso» | HU03-RN-03, HU03-RN-04 | HU03-RF-008, HU03-RF-009, HU03-RF-010, HU03-RF-012, HU03-RF-013 |
| La respuesta y la petición quedan registradas en la línea temporal | HU03-RN-03, HU03-RN-06 | HU03-RF-004, HU03-RF-011, HU03-RF-015 |
| El aviso desaparece al responder y el ticket vuelve al equipo técnico | HU03-RN-02, HU03-RN-04 | HU03-RF-013, HU03-RF-014 |
| El usuario no puede responder tickets ajenos ni en estados no válidos | HU03-RN-03, HU03-RN-05 | HU03-RF-008, HU03-RF-017, HU03-RF-018 |
| El usuario no responde en 48 horas | El sistema muestra un único recordatorio contextual | HU03-RN-02 | HU03-RF-006, HU03-RF-022 |
| Los comentarios internos siguen ocultos y lo anterior no se rompe | HU03-RN-05, HU03-RN-08 | HU03-RF-019, HU03-RF-020, HU03-RF-021 |
