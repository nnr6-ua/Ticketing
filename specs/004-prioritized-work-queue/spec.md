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
