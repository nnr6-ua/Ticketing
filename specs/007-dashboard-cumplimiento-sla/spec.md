# Especificación Funcional: Dashboard de cumplimiento de SLA (HU-07)

**Rama**: `hu-07-dashboard-sla`

**Creado**: 2026-11-14

**Estado**: Borrador

**Entrada**: HU-07 — «Dashboard de cumplimiento de SLA. Como supervisor, quiero ver de forma agregada el cumplimiento de tiempos de respuesta según prioridad y categoría, para que identifique retrasos y responsables de un vistazo.»

> **Nota de consolidación**: esta especificación amplía la especificación existente con el módulo funcional de la HU-07 y conserva, sin alteraciones, todos los requisitos, escenarios, reglas de negocio y criterios de aceptación de los módulos previos HU-04 (cola de trabajo priorizada), HU-05 (cambio de estado y documentación de resolución) y HU-06 (reasignación y escalado), que **no** se reproducen en este documento: se consultan en `specs/004-prioritized-work-queue/spec.md`, `specs/005-cambio-estado-resolucion/spec.md` y `specs/006-reasignar-escalar-ticket/spec.md`. El módulo HU-07 es de solo lectura: consume los datos de tickets, SLA, asignaciones y línea temporal ya definidos por las historias anteriores y no modifica su comportamiento.

> **Convención de identificadores**: los códigos `RF-###`, `SC-###` y `RN-##` son locales a cada módulo funcional. Las definiciones y tablas de trazabilidad de este módulo usan el prefijo `HU07-` (`HU07-RF-001`, `HU07-SC-001`, `HU07-RN-01`); las referencias a módulos anteriores usan su prefijo (`HU04-`, `HU05-`, `HU06-`). Las menciones sin prefijo dentro de una sección se interpretan en el ámbito de esa sección.

## Resumen

El supervisor de la mesa de ayuda dispone de un dashboard de consulta que presenta, de forma agregada, el cumplimiento de los plazos de SLA y los tiempos de respuesta del servicio. La vista permite comparar el comportamiento por prioridad (Crítica, Alta, Media y Baja) y por categoría, identificando qué combinaciones concentran retrasos, cuál es su tiempo medio de respuesta y cuántos tickets han incumplido el plazo.

El dashboard incorpora además un ranking de técnicos con tickets vencidos acumulados, ordenado por volumen, para que el supervisor identifique de un vistazo dónde se concentran los retrasos y quién es el responsable de atenderlos. Todos los datos pueden acotarse mediante filtros de rango de fechas, categoría y prioridad, y se presentan con un semáforo de cumplimiento (verde, ámbar o rojo) basado en umbrales de negocio.

La funcionalidad es exclusivamente de supervisión y solo lectura: no crea, modifica ni reasigna tickets, ni altera la configuración de SLA. Los cálculos respetan los valores históricos guardados en cada ticket en el momento de su creación, de modo que los cambios posteriores de categorías, prioridades o plazos no distorsionan los resultados de periodos anteriores.

## Clarifications

### Sesión 2026-11-14 (decisiones de negocio)

- **Q1**: ¿Qué hito del ticket debe contar como «atención» para calcular el cumplimiento del SLA y el tiempo medio de respuesta? → A: **Primera finalización** — primer paso del ticket a «Resuelto» o «Cerrado», conforme a HU04-RN-13; se aplica a todas las métricas y al semáforo.
- **Q2**: ¿Qué umbrales de porcentaje de cumplimiento deben separar el semáforo verde, ámbar y rojo? → A: **Verde ≥ 90 %, ámbar 70 %–<90 %, rojo < 70 %**; el valor exacto de un umbral pertenece a la banda superior.
- **Q3**: ¿A qué técnico debe atribuirse cada ticket vencido en el ranking? → A: **Regla mixta** — quien ejecutó la primera finalización si el ticket vencido ya la alcanzó; responsable actual si está vencido y pendiente de atención (sin primera finalización); «Sin asignar» si no tiene responsable. La atribución es estable ante reasignaciones y reaperturas posteriores. Cada ticket se atribuye a un único técnico o a «Sin asignar».
- **Q4**: ¿El dashboard debe mostrar los datos de todos los equipos de la mesa de ayuda o solo los del equipo del supervisor? → A: **Alcance global** — supervisores y administradores ven todos los equipos, sin filtro ni restricción por equipo.
- **Q5**: ¿Cómo debe calcularse el «retraso medio» que se muestra en el ranking y se usa para desempatar? → A: **Media aritmética del retraso de todos sus tickets vencidos**, conforme a HU07-RN-06: en activos, instante de la consulta menos límite; en finalizados, primera finalización menos límite. Se muestra redondeado al minuto y el desempate usa el valor exacto.

Decisiones de negocio adoptadas por defecto, documentadas para evitar ambigüedad:

- Q: ¿Quién puede acceder al dashboard? → A: Supervisores y administradores. Los técnicos y los usuarios creadores no acceden a esta vista.
- Q: ¿Qué fecha determina la pertenencia de un ticket al periodo filtrado? → A: La fecha de creación del ticket, con los dos extremos del rango incluidos y días naturales en la zona horaria Europe/Madrid.
- Q: ¿Qué rango de fechas se aplica por defecto? → A: Los últimos 30 días naturales, incluido el día de la consulta.
- Q: ¿Cómo se tratan los tickets sin SLA aplicable? → A: Se excluyen del porcentaje de cumplimiento y del tiempo medio de respuesta, se contabilizan aparte como «Sin SLA» y nunca se consideran vencidos.
- Q: ¿Cómo se contabilizan los tickets reabiertos? → A: Se cuentan una sola vez y conservan la primera finalización, conforme a HU04-RN-13.
- Q: ¿Qué ocurre con las combinaciones de prioridad y categoría sin tickets? → A: No se muestran como filas de la matriz; los totales por prioridad, por categoría y el total global sí se muestran siempre.
- Q: ¿Sobre qué métrica se aplica el semáforo? → A: Sobre el porcentaje de cumplimiento. El tiempo medio de respuesta y el número de tickets vencidos se muestran con su valor, sin sustituir al semáforo de cumplimiento.
- Q: ¿Cómo se actualizan los datos? → A: La vista se actualiza automáticamente en un plazo máximo de 60 segundos y admite actualización manual, mostrando la fecha y hora de la última actualización y conservando los filtros aplicados.
- Q: ¿Cómo se reflejan los tickets vencidos sin responsable? → A: Se agrupan en una fila separada «Sin asignar», que no se considera un técnico y que garantiza que el total del ranking cuadre con el total de tickets vencidos.
- Q: ¿Cómo se muestran categorías o prioridades desactivadas? → A: Se conserva la etiqueta histórica almacenada en el ticket y se añade la indicación «(inactiva)»; no se mezclan con otras categorías o prioridades.
- Q: ¿Qué datos personales se muestran? → A: Solo el nombre y el equipo del técnico en el ranking, junto con métricas agregadas. No se muestran datos del usuario creador, correos electrónicos, comentarios ni el detalle de tickets individuales.
- Q: ¿Qué formato y accesibilidad se aplican? → A: Español de España, fechas y horas en Europe/Madrid, formato local de números y WCAG 2.1 AA, sin depender únicamente del color.
- Q: ¿Cómo se interpreta un valor exactamente igual al umbral del semáforo? → A: El valor exacto del umbral pertenece a la banda superior; por ejemplo, con umbral verde de 90 %, un 90,0 % es verde.

## Actores

- **Supervisor**: actor principal. Consulta el dashboard con alcance global a todos los equipos, aplica filtros e interpreta las métricas y el semáforo para detectar retrasos y responsables.
- **Administrador**: puede consultar el mismo dashboard con el mismo alcance global que el supervisor; no dispone de acciones de edición desde esta vista.
- **Técnico**: aparece en el ranking de tickets vencidos y es destinatario de las métricas de responsabilidad; no accede al dashboard en esta historia.
- **Usuario creador**: no accede al dashboard ni aparece identificado en él; sus datos no forman parte de las métricas.
- **Sistema**: calcula y presenta los agregados a partir de los tickets, los valores de SLA guardados, las asignaciones y la línea temporal existentes.

## Escenarios de Usuario y Pruebas

### Historia 1 — Ver el cumplimiento agregado por prioridad y categoría (Prioridad: P1)

Como supervisor, quiero ver una matriz de cumplimiento por prioridad y categoría, para identificar de un vistazo qué tipos de incidencia y qué niveles de urgencia concentran los retrasos.

**Por qué esta prioridad**: es el núcleo de la historia; sin la vista agregada no existe el dashboard de supervisión.

**Prueba independiente**: con un conjunto controlado de tickets que cubra varias prioridades y categorías, el supervisor abre el dashboard y comprueba que cada combinación con datos muestra el porcentaje de cumplimiento, el tiempo medio de respuesta y el número de tickets vencidos, coherentes con los tickets del periodo.

**Escenarios de aceptación**:

1. **Dado** un supervisor con tickets creados dentro del periodo seleccionado, **cuando** abre el dashboard, **entonces** ve una vista agregada con las métricas de cumplimiento por prioridad (Crítica, Alta, Media y Baja) y por categoría.
2. **Dado** un conjunto de tickets de una misma categoría y prioridad, **cuando** se muestra su combinación, **entonces** la celda indica el porcentaje de tickets atendidos dentro de plazo, el tiempo medio de respuesta y el número de tickets vencidos, junto con el número total de tickets considerados.
3. **Dado** un ticket atendido exactamente en su fecha límite de SLA, **cuando** se calcula el cumplimiento, **entonces** se considera atendido dentro de plazo y no se contabiliza como vencido.
4. **Dado** un ticket sin SLA aplicable, **cuando** se calculan las métricas, **entonces** no se incluye en el porcentaje de cumplimiento ni en el tiempo medio de respuesta, se contabiliza como «Sin SLA» y no aparece como vencido.
5. **Dado** un ticket aún no atendido cuyo plazo ya ha vencido, **cuando** se consulta el dashboard, **entonces** se contabiliza como ticket vencido, aunque no forme parte del denominador del porcentaje de cumplimiento por no haber sido atendido.
6. **Dado** un ticket reabierto después de haber sido finalizado, **cuando** se calculan las métricas, **entonces** se cuenta una sola vez y conserva la primera finalización, conforme a HU04-RN-13.
7. **Dado** un ticket cuya categoría o prioridad ha sido desactivada con posterioridad, **cuando** aparece en el periodo, **entonces** se muestra con su etiqueta histórica y la indicación «(inactiva)», sin mezclarse con otras categorías o prioridades.
8. **Dado** un ticket sin categoría, **cuando** se agrega, **entonces** se agrupa bajo la etiqueta «Sin categoría».
9. **Dado** un periodo sin tickets, **cuando** el supervisor abre el dashboard, **entonces** ve un estado vacío informativo y no una matriz con ceros o datos ficticios.

---

### Historia 2 — Identificar a los técnicos con más tickets vencidos (Prioridad: P1)

Como supervisor, quiero ver una lista de técnicos con tickets vencidos acumulados, ordenada por volumen, para saber dónde se concentran los retrasos y quién debe actuar.

**Por qué esta prioridad**: el criterio de aceptación exige identificar responsables; sin el ranking, el dashboard no responde a la pregunta «quién».

**Prueba independiente**: con varios técnicos y tickets vencidos distribuidos de forma conocida, el supervisor comprueba que la lista solo incluye técnicos con al menos un vencido, que está ordenada de mayor a menor volumen y que los empates se resuelven según la regla definida.

**Escenarios de aceptación**:

1. **Dado** varios técnicos con tickets vencidos en el periodo, **cuando** se muestra el ranking, **entonces** aparece ordenado de mayor a menor número de tickets vencidos acumulados.
2. **Dado** dos técnicos con el mismo número de tickets vencidos, **cuando** se ordena el ranking, **entonces** se aplica el desempate por mayor retraso medio de sus tickets vencidos y, si persiste, por nombre ascendente y equipo.
3. **Dado** un técnico sin tickets vencidos en el periodo, **cuando** se muestra el ranking, **entonces** no aparece en la lista.
4. **Dado** un técnico con tickets vencidos que ha sido desactivado posteriormente, **cuando** se consulta el periodo histórico, **entonces** aparece con la indicación «(inactivo)» para no perder la trazabilidad del responsable.
5. **Dado** un ticket vencido sin responsable, **cuando** se calcula el ranking, **entonces** se agrupa en la fila «Sin asignar», separada de los técnicos, y el total de vencidos del ranking coincide con el total del dashboard.
6. **Dado** un ticket reasignado después de incumplir el plazo, **cuando** se atribuye el vencido, **entonces** se aplica la regla mixta de HU07-RN-09 y el ticket se contabiliza una sola vez, sin duplicarse entre técnicos.
7. **Dado** un periodo sin tickets vencidos, **cuando** se muestra el ranking, **entonces** aparece un estado vacío específico que indica que no hay vencidos en el periodo.
8. **Dado** un ranking visible, **cuando** el supervisor lo consulta, **entonces** cada fila muestra al menos el nombre del técnico, su equipo, el número de tickets vencidos y el retraso medio, sin incluir datos personales adicionales ni el detalle de tickets individuales.

---

### Historia 3 — Acotar el dashboard por fechas, categoría y prioridad (Prioridad: P2)

Como supervisor, quiero filtrar el dashboard por rango de fechas, categoría y prioridad, para analizar un periodo concreto o un subconjunto de incidencias sin perder la coherencia entre secciones.

**Por qué esta prioridad**: con volumen histórico, los filtros son lo que hace utilizable la supervisión y permiten comparar periodos o áreas concretas.

**Prueba independiente**: se aplican filtros por separado y en combinación y se comprueba que todas las secciones, totales y ranking se recalculan con el mismo conjunto de tickets.

**Escenarios de aceptación**:

1. **Dado** el dashboard abierto sin filtros, **cuando** se carga por primera vez, **entonces** se aplica por defecto el rango de los últimos 30 días naturales, con todas las categorías y prioridades.
2. **Dado** un rango de fechas con fecha inicial y final, **cuando** se aplica, **entonces** se incluyen los tickets creados en ambos extremos, considerando días naturales en Europe/Madrid.
3. **Dado** un filtro de categoría con una o varias categorías, **cuando** se aplica, **entonces** solo se consideran los tickets de esas categorías, incluida la opción «Sin categoría» si existe en el periodo.
4. **Dado** un filtro de prioridad con una o varias prioridades, **cuando** se aplica, **entonces** solo se consideran los tickets de esas prioridades.
5. **Dado** un filtro de fechas, otro de categoría y otro de prioridad aplicados a la vez, **cuando** se muestran los resultados, **entonces** solo se incluyen los tickets que cumplen todos los criterios, con lógica «Y» entre dimensiones y «O» dentro de cada selección múltiple.
6. **Dado** un resultado filtrado, **cuando** se revisan la matriz, los totales y el ranking, **entonces** todas las secciones usan exactamente el mismo conjunto de tickets y los totales cuadran con las celdas.
7. **Dado** un rango de fechas en el que la fecha inicial es posterior a la final, **cuando** se intenta aplicar, **entonces** el sistema bloquea la consulta, mantiene los filtros anteriores y muestra un mensaje comprensible.
8. **Dado** un filtro que no devuelve ningún ticket, **cuando** se muestra el resultado, **entonces** aparece un estado de «sin resultados para los filtros seleccionados» con una acción para limpiarlos, distinto del estado vacío por ausencia de datos en el periodo.
9. **Dado** un filtro aplicado, **cuando** el supervisor lo restablece, **entonces** vuelve a la configuración por defecto.
10. **Dado** un filtro aplicado, **cuando** el supervisor navega dentro del dashboard o actualiza los datos, **entonces** los filtros se conservan durante la sesión.

---

### Historia 4 — Interpretar el cumplimiento con un semáforo (Prioridad: P2)

Como supervisor, quiero que el cumplimiento se represente con un semáforo verde, ámbar o rojo según umbrales de negocio, para reconocer rápidamente las áreas que requieren atención sin interpretar cada cifra.

**Por qué esta prioridad**: el criterio de aceptación exige indicadores visuales; el semáforo convierte los porcentajes en una señal accionable.

**Prueba independiente**: se preparan combinaciones con porcentajes por encima, dentro y por debajo de los umbrales, y se comprueba que cada una recibe el color, el icono y la etiqueta textual correctos.

**Escenarios de aceptación**:

1. **Dado** un porcentaje de cumplimiento igual o superior al umbral verde, **cuando** se muestra la combinación, **entonces** se indica en verde con la etiqueta textual correspondiente y un icono comprensible.
2. **Dado** un porcentaje de cumplimiento inferior al umbral verde pero igual o superior al umbral ámbar, **cuando** se muestra la combinación, **entonces** se indica en ámbar con su etiqueta textual e icono.
3. **Dado** un porcentaje de cumplimiento inferior al umbral ámbar, **cuando** se muestra la combinación, **entonces** se indica en rojo con su etiqueta textual e icono.
4. **Dado** un porcentaje exactamente igual a un umbral, **cuando** se asigna el semáforo, **entonces** se aplica la banda superior, de modo que el umbral verde incluye el valor exacto.
5. **Dado** una combinación sin tickets atendidos con SLA, **cuando** se muestra, **entonces** se indica «Sin datos» en color neutro y no se asigna verde, ámbar ni rojo.
6. **Dado** un dashboard con varias combinaciones y totales, **cuando** se revisa el semáforo, **entonces** todos usan los mismos umbrales y la misma leyenda explicativa.
7. **Dado** un supervisor con daltonismo o que usa un lector de pantalla, **cuando** consulta el semáforo, **entonces** el estado se transmite también mediante icono y texto, no solo mediante el color.
8. **Dado** que los umbrales cambian por decisión de negocio, **cuando** se aplica la nueva configuración, **entonces** todos los semáforos del dashboard se recalculan de forma coherente y la leyenda refleja los valores vigentes.

---

### Historia 5 — Entender estados vacíos, errores y frescura de los datos (Prioridad: P3)

Como supervisor, quiero distinguir con claridad cuándo no hay datos, cuándo los filtros no devuelven resultados y cuándo ha fallado la carga, para no interpretar una ausencia de información como un buen resultado.

**Por qué esta prioridad**: completa la experiencia y evita decisiones erróneas, pero no bloquea el valor principal del dashboard.

**Prueba independiente**: se prueban un periodo sin tickets, un filtro sin resultados, un fallo de carga, una sesión caducada y una actualización fallida, comprobando que cada situación muestra un mensaje distinto y adecuado.

**Escenarios de aceptación**:

1. **Dado** un periodo sin ningún ticket, **cuando** se carga el dashboard, **entonces** aparece un estado vacío que indica que no hay tickets en el periodo y sugiere ampliar el rango de fechas.
2. **Dado** un fallo al obtener los datos, **cuando** la vista no puede mostrarse, **entonces** aparece un mensaje de error diferenciado con una acción de reintento, sin presentarse como un dashboard vacío ni con métricas a cero.
3. **Dado** una sesión caducada, **cuando** el supervisor intenta consultar el dashboard, **entonces** se solicita autenticación de nuevo y, tras iniciar sesión, se regresa al dashboard conservando los filtros cuando sea posible.
4. **Dado** un dashboard visible, **cuando** transcurre el intervalo de actualización, **entonces** los datos se actualizan automáticamente en un plazo máximo de 60 segundos y se muestra la fecha y hora de la última actualización.
5. **Dado** un dashboard visible, **cuando** el supervisor solicita una actualización manual, **entonces** los datos se recalculan y los filtros se mantienen.
6. **Dado** un fallo durante una actualización, **cuando** ya había datos previos, **entonces** se conservan los últimos datos válidos con un aviso de que pueden estar desactualizados y una acción de reintento, sin mostrar un dashboard vacío.
7. **Dado** un dashboard con datos, **cuando** el supervisor consulta la información, **entonces** la vista muestra la hora de última actualización en la zona horaria Europe/Madrid.

### Casos Límite

El catálogo completo de casos límite de esta historia — con su comportamiento
esperado y su mensaje orientativo — se mantiene como **fuente única** en la
sección «Casos Límite y Manejo de Errores» del final de este documento; esta
lista no lo duplica. Los estados diferenciados que debe distinguir la interfaz
se norman en HU07-RN-16, su exigencia funcional es HU07-RF-048 y su
verificación es HU07-SC-012.

## Reglas de Negocio

### HU07-RN-01 — Propósito y naturaleza de solo lectura

- El dashboard es una vista de supervisión agregada; no modifica tickets, estados, prioridades, categorías, responsables, plazos de SLA ni configuraciones.
- Las únicas acciones permitidas son consultar, filtrar, actualizar y restablecer filtros.
- Ninguna interacción del dashboard puede alterar la línea temporal ni los datos históricos de los tickets.

### HU07-RN-02 — Población, periodo y fecha de referencia

- La población del dashboard son los tickets cuya fecha de creación está dentro del rango de fechas seleccionado, con independencia de su estado actual (activo o final).
- El rango incluye la fecha inicial y la final, y se interpreta en días naturales de la zona horaria Europe/Madrid.
- El rango por defecto son los últimos 30 días naturales, incluido el día de la consulta.
- Los tickets creados fuera del rango no se incluyen en ninguna métrica, aunque su plazo haya vencido dentro del periodo.
- Cada ticket se cuenta una sola vez. Los tickets reabiertos conservan la primera finalización, conforme a HU04-RN-13.
- Las métricas usan la prioridad, la categoría y el límite de SLA almacenados en el ticket en el momento de su creación, conforme a HU04-RN-03 y a la configuración histórica de SLA de HU-08. Los cambios posteriores de configuración no alteran los resultados de periodos anteriores.

### HU07-RN-03 — Primera finalización y tiempo de respuesta

- El dashboard mide la atención de un ticket mediante un único hito: la **primera finalización** del ticket, entendida como su primer paso a «Resuelto» o «Cerrado», conforme a HU04-RN-13. Este hito determina tanto el cumplimiento del SLA como el tiempo medio de respuesta y se aplica de forma homogénea a todas las métricas y al semáforo.
- Un ticket que todavía no ha alcanzado la primera finalización está «pendiente de atención»: no se incluye en el porcentaje de cumplimiento ni en el tiempo medio de respuesta, pero se contabiliza como vencido si su plazo ya ha pasado.
- La primera finalización se toma una sola vez por ticket: la primera que ocurra. Las reaperturas y los cambios posteriores no reinician el cálculo.
- Esta historia no modifica las reglas de la cola de trabajo de HU-04; su indicador de SLA conserva el comportamiento definido en dicha historia.

### HU07-RN-04 — Porcentaje de cumplimiento

- El porcentaje de cumplimiento de una combinación se calcula como:

  **tickets atendidos dentro de plazo ÷ tickets atendidos con SLA × 100**

- El numerador son los tickets de la población que han alcanzado la primera finalización con fecha igual o anterior a su límite de SLA.
- El denominador son todos los tickets de la población que han alcanzado la primera finalización y tienen SLA aplicable.
- Los tickets pendientes de atención y los tickets sin SLA no forman parte del denominador.
- Un ticket atendido exactamente en el límite se considera dentro de plazo.
- El resultado se muestra con un decimal y separador decimal español. El cálculo se realiza con precisión suficiente y el semáforo usa el valor redondeado que se muestra.
- Si el denominador es cero, se muestra «Sin datos»; nunca un 0 % que pueda interpretarse como cumplimiento nulo.

### HU07-RN-05 — Tiempo medio de respuesta

- El tiempo medio de respuesta de una combinación es la media aritmética del tiempo transcurrido entre la creación del ticket y su primera finalización, para los tickets atendidos con SLA de la población.
- Los tickets pendientes de atención y los tickets sin SLA no se incluyen en la media.
- Si no hay tickets atendidos con SLA, se muestra «Sin datos».
- El valor se presenta en unidades legibles y se redondea al minuto para su visualización; el cálculo interno conserva la precisión necesaria para que los totales sean coherentes.
- El tiempo de respuesta nunca es negativo.

### HU07-RN-06 — Tickets vencidos

- Un ticket está vencido cuando tiene SLA aplicable y se cumple una de estas condiciones:
  - Ha alcanzado la primera finalización después de su límite de SLA.
  - No ha alcanzado la primera finalización y el instante actual ya supera su límite de SLA.
- Un ticket atendido exactamente en el límite no está vencido.
- Un ticket sin SLA nunca está vencido.
- El número de tickets vencidos es un recuento de tickets, no de días ni de eventos; cada ticket se cuenta una vez.
- Un ticket vencido sigue contabilizado aunque se finalice o se cierre; su condición de vencido forma parte del histórico y no se borra.
- El retraso de un ticket activo vencido crece con el tiempo hasta que se atiende o finaliza. El retraso de un ticket finalizado vencido es estático y corresponde a la diferencia entre la primera finalización y el límite.
- Los tickets reabiertos conservan la primera finalización, conforme a HU04-RN-13, y no se vuelven a contar.

### HU07-RN-07 — Agregación por prioridad y categoría

- La matriz principal cruza las prioridades Crítica, Alta, Media y Baja con las categorías de los tickets de la población.
- Se muestran las combinaciones que tienen al menos un ticket en la población. Las combinaciones sin tickets no se muestran como filas; los totales por prioridad, por categoría y el total global sí se muestran siempre.
- El orden de prioridades es Crítica, Alta, Media y Baja. Las categorías se ordenan alfabéticamente.
- Cada celda muestra el número de tickets considerados, el porcentaje de cumplimiento, el tiempo medio de respuesta y el número de tickets vencidos.
- Los tickets sin categoría se agrupan en «Sin categoría». Las categorías o prioridades desactivadas conservan su etiqueta histórica y se acompañan de «(inactiva)».
- Cada ticket pertenece a una única celda. Los totales se calculan a partir de los tickets subyacentes, no promediando los porcentajes o medias de las celdas, para evitar distorsiones estadísticas.
- La suma de los tickets de las celdas coincide con los totales por prioridad, por categoría y global.

### HU07-RN-08 — Ranking de técnicos con tickets vencidos

- El ranking incluye a los técnicos con al menos un ticket vencido atribuido en la población seleccionada.
- El orden principal es el número de tickets vencidos acumulados, de mayor a menor.
- El retraso medio es la media aritmética del retraso de todos los tickets vencidos atribuidos al técnico, calculado conforme a HU07-RN-06: en tickets activos, instante de la consulta menos límite de SLA; en finalizados, primera finalización menos límite. Se muestra redondeado al minuto, mientras que el desempate usa el valor exacto.
- En caso de empate, se ordena por mayor retraso medio de los tickets vencidos del técnico; si persiste, por nombre ascendente sin distinguir mayúsculas ni minúsculas y, por último, por equipo ascendente. El orden debe ser estable.
- Cada fila muestra al menos el nombre del técnico, su equipo, el número de tickets vencidos y el retraso medio. Si el técnico está inactivo, se añade «(inactivo)».
- Los técnicos sin tickets vencidos en el periodo no aparecen en la lista.
- Los tickets vencidos sin responsable se agrupan en una fila separada «Sin asignar», que no se considera un técnico y que se muestra después de los técnicos.
- La suma de los tickets vencidos del ranking, incluida la fila «Sin asignar», coincide con el total de tickets vencidos del dashboard.
- El ranking usa los mismos filtros y la misma población que el resto de secciones.
- El ranking no muestra tickets individuales, datos del usuario creador, correos electrónicos ni comentarios.

### HU07-RN-09 — Atribución del ticket vencido

- Cada ticket vencido se atribuye a un único técnico o a «Sin asignar»; nunca a varios.
- La regla de atribución es la **regla mixta**, ligada al hito de la primera finalización (HU07-RN-03) y no al estado actual del ticket:
  - Si el ticket ha alcanzado la primera finalización y está vencido (la primera finalización fue posterior a su límite de SLA), se atribuye a **quien ejecutó ese primer paso a «Resuelto»**, identificado por el `author_id` de la primera entrada `status_change → 'resuelto'` de la línea temporal; «quien lo finalizó» no es necesariamente el responsable asignado en ese momento.
  - Si el ticket está vencido y todavía no ha alcanzado la primera finalización (pendiente de atención), se atribuye al responsable actual en el momento de la consulta (`tickets.assignee_id`).
  - Si en ese caso no hay responsable, se atribuye a «Sin asignar».
- Esta regla garantiza una atribución estable: las reasignaciones y reaperturas posteriores no cambian a quién se atribuye un vencido ya producido. En particular, un ticket vencido reabierto tras una finalización tardía se sigue atribuyendo a quien lo finalizó, no al responsable actual.
- La atribución no altera la asignación real del ticket ni el histórico de cambios de responsable de HU-06, del que solo hace lecturas.
- Si un ticket no tiene entradas de línea temporal (ticket heredado anterior a HU-05), la primera finalización se toma de `tickets.finalized_at` y la atribución se hace al responsable vigente (`tickets.assignee_id`); si no existe, «Sin asignar».
- Cada ticket vencido se contabiliza una sola vez, sin duplicarse entre técnicos ni entre técnicos y «Sin asignar».

### HU07-RN-10 — Filtros

- El dashboard permite filtrar por rango de fechas, categoría y prioridad.
- El rango de fechas se aplica sobre la fecha de creación del ticket, con ambos extremos incluidos y días naturales en Europe/Madrid.
- La categoría y la prioridad se seleccionan de forma múltiple. Dentro de una misma dimensión, las opciones se combinan con lógica «O»; entre dimensiones, con lógica «Y».
- Los filtros se aplican de forma homogénea a la matriz, a los totales y al ranking.
- El valor por defecto es el rango de los últimos 30 días naturales, todas las categorías y todas las prioridades.
- Las opciones de filtro incluyen las categorías y prioridades presentes en el periodo, aunque estén desactivadas en la actualidad, y la opción «Sin categoría» cuando existan tickets sin categoría.
- Si la fecha inicial es posterior a la final, la consulta se bloquea y se muestra un mensaje comprensible; no se muestran datos parciales.
- Un filtro sin resultados muestra un estado específico de «sin resultados» con una acción para limpiar filtros.
- La acción de restablecer devuelve la configuración por defecto.
- Los filtros se conservan durante la sesión de navegación y se mantienen al actualizar los datos.
- Los filtros nunca amplían el alcance de permisos del usuario.

### HU07-RN-11 — Semáforo de cumplimiento

- El semáforo se aplica al porcentaje de cumplimiento de cada combinación, a los totales por prioridad, a los totales por categoría y al total global.
- Los umbrales vigentes son:
  - **Verde**: cumplimiento igual o superior al 90 %.
  - **Ámbar**: cumplimiento igual o superior al 70 % e inferior al 90 %.
  - **Rojo**: cumplimiento inferior al 70 %.
- Un valor exactamente igual a un umbral pertenece a la banda superior. El semáforo se calcula sobre el porcentaje redondeado que se muestra.
- Si no hay tickets atendidos con SLA, se muestra «Sin datos» en color neutro y no se asigna ningún color de alarma.
- El semáforo se acompaña siempre de un texto y un icono; el color nunca es el único portador de la información.
- La vista incluye una leyenda que explica los umbrales vigentes y el significado de cada color.
- Los umbrales son únicos y coherentes para todo el dashboard; no se aplican reglas distintas por categoría o prioridad salvo decisión de negocio explícita.

### HU07-RN-12 — Coherencia, actualización y frescura

- Todas las secciones del dashboard se calculan sobre la misma población y los mismos filtros, formando una instantánea coherente.
- La vista muestra la fecha y hora de la última actualización en Europe/Madrid.
- Los datos se actualizan automáticamente en un plazo máximo de 60 segundos y admiten actualización manual.
- Los filtros aplicados se conservan al actualizar.
- Si una actualización falla y existen datos previos, se conservan los últimos datos válidos con un aviso visible de posible desactualización y una acción de reintento.
- Si la carga inicial falla, no se muestran métricas a cero ni un estado vacío: se muestra un error diferenciado.
- No se muestran resultados parciales de una actualización incompleta.

### HU07-RN-13 — Permisos y privacidad

- Solo los supervisores y administradores pueden acceder al dashboard. Los técnicos y los usuarios creadores no acceden.
- El alcance de los datos es global: supervisores y administradores ven los datos de todos los equipos de la mesa de ayuda, sin filtro ni restricción por equipo.
- El acceso se deniega sin revelar datos agregados ni la existencia de métricas.
- El dashboard muestra únicamente información agregada y, en el ranking, el nombre y equipo del técnico con sus métricas de vencidos.
- No se muestran datos del usuario creador, correos electrónicos, comentarios internos, descripciones de tickets ni identificadores de tickets individuales.
- La información se limita a la necesaria para la supervisión del servicio.
- Los filtros y la vista no permiten inferir datos de tickets individuales fuera del alcance autorizado.

### HU07-RN-14 — Presentación, idioma y accesibilidad

- La vista se presenta en español de España, con fechas y horas en la zona horaria Europe/Madrid y formato local de números.
- La interfaz cumple WCAG 2.1 AA: contraste suficiente, foco visible, etiquetas asociadas, navegación por teclado y compatibilidad con lectores de pantalla.
- La información de prioridad, cumplimiento y riesgo se transmite mediante color, icono y texto, sin depender solo del color.
- La vista es responsive y utilizable en escritorio y tablet.
- Las tablas y matrices tienen encabezados claros y asociaciones comprensibles para tecnologías de asistencia.

### HU07-RN-15 — Redondeo y unidades

- Los porcentajes se muestran con un decimal y coma decimal (por ejemplo, «87,5 %»).
- Las duraciones se muestran en unidades legibles: minutos si son inferiores a una hora; horas y minutos si son inferiores a un día; días y horas en caso contrario.
- Las medias se redondean al minuto para su visualización; los cálculos internos conservan la precisión necesaria para que los totales sean coherentes.
- Una media inferior a un minuto se muestra como «menos de 1 min»; por convención, una media de exactamente 0 segundos se muestra como «0 min».
- Los recuentos son números enteros.
- No se muestran duraciones negativas ni porcentajes superiores al 100 %.
- El semáforo usa el porcentaje redondeado que se muestra, de modo que la cifra y el color sean coherentes.

### HU07-RN-16 — Estados vacíos y errores

- Se distinguen de forma explícita estas situaciones:
  - Periodo sin tickets.
  - Filtros sin resultados.
  - Periodo sin tickets con SLA.
  - Periodo sin tickets vencidos.
  - Error de carga o de actualización.
  - Sesión caducada.
  - Rango de fechas inválido.
- Cada situación muestra un mensaje comprensible en español y, cuando procede, una acción para continuar (ampliar fechas, limpiar filtros, reintentar o iniciar sesión).
- Un error nunca se presenta como un dashboard vacío ni como métricas a cero.
- Un periodo sin datos no se presenta como un buen cumplimiento.

### HU07-RN-17 — Integridad y trazabilidad de la fuente

- Las métricas se calculan exclusivamente a partir de los tickets, los valores históricos de SLA, las asignaciones y la línea temporal existentes; no admiten ajustes manuales.
- El dashboard no altera ni elimina evidencia de vencimientos, cambios de estado, resoluciones o reasignaciones.
- La condición de vencido permanece registrada aunque el ticket se cierre, conforme a HU04-RN-07.
- Las etiquetas históricas de categoría, prioridad y SLA se conservan aunque la configuración cambie.
- Cada cifra del dashboard debe poder explicarse a partir de los tickets de la población y de las reglas de esta especificación.

## Requisitos Funcionales

### Vista y alcance

- **HU07-RF-001**: El sistema DEBE ofrecer a supervisores y administradores una vista de dashboard con métricas agregadas de cumplimiento por prioridad y por categoría.
- **HU07-RF-002**: El dashboard DEBE ser de solo lectura y no DEBE permitir crear, modificar, reasignar, cerrar ni eliminar tickets, ni cambiar la configuración de SLA.
- **HU07-RF-003**: El sistema DEBE calcular las métricas sobre los tickets creados dentro del rango de fechas seleccionado, con independencia de su estado actual.
- **HU07-RF-004**: El sistema DEBE usar la prioridad, la categoría y el límite de SLA almacenados en el ticket en el momento de su creación, sin verse afectado por cambios posteriores de configuración.
- **HU07-RF-005**: El sistema DEBE mostrar un resumen global con el número de tickets considerados, los atendidos con SLA, el porcentaje de cumplimiento, el tiempo medio de respuesta, los tickets vencidos y los tickets sin SLA.

### Métricas por prioridad y categoría

- **HU07-RF-006**: Para cada combinación de prioridad y categoría con al menos un ticket en la población, el sistema DEBE mostrar el número de tickets, el porcentaje de cumplimiento, el tiempo medio de respuesta y el número de tickets vencidos.
- **HU07-RF-007**: El sistema DEBE calcular el porcentaje de cumplimiento conforme a HU07-RN-04 y mostrarlo con un decimal y separador decimal español.
- **HU07-RF-008**: El sistema DEBE calcular el tiempo medio de respuesta conforme a HU07-RN-05 y mostrarlo en unidades legibles.
- **HU07-RF-009**: El sistema DEBE calcular el número de tickets vencidos conforme a HU07-RN-06, contando cada ticket una sola vez.
- **HU07-RF-010**: El sistema DEBE mostrar totales por prioridad, totales por categoría y un total global, calculados a partir de los tickets subyacentes.
- **HU07-RF-011**: Cuando no existan tickets atendidos con SLA en una combinación o en un total, el sistema DEBE mostrar «Sin datos» en el porcentaje y en el tiempo medio, sin mostrar un 0 % engañoso.
- **HU07-RF-012**: El sistema DEBE mostrar los tickets sin categoría bajo la etiqueta «Sin categoría» y las categorías o prioridades desactivadas con su etiqueta histórica y la indicación «(inactiva)».
- **HU07-RF-013**: El sistema DEBE contar cada ticket una sola vez, conservando la primera finalización de los tickets reabiertos conforme a HU04-RN-13.
- **HU07-RF-014**: El sistema DEBE excluir del porcentaje de cumplimiento y del tiempo medio de respuesta los tickets sin SLA, mostrarlos en un conteo separado de «Sin SLA» y no considerarlos vencidos.
- **HU07-RF-015**: El sistema DEBE calcular los totales a partir de los tickets subyacentes y no promediando los porcentajes o medias de las celdas.
- **HU07-RF-016**: El sistema DEBE mostrar únicamente las combinaciones con al menos un ticket y DEBE mostrar siempre los totales por prioridad, por categoría y global.
- **HU07-RF-017**: El sistema DEBE ordenar las prioridades como Crítica, Alta, Media y Baja, y las categorías alfabéticamente.
- **HU07-RF-018**: El sistema DEBE garantizar que la suma de los tickets de las celdas coincida con los totales correspondientes.

### Ranking de técnicos

- **HU07-RF-019**: El sistema DEBE mostrar una lista de técnicos con tickets vencidos acumulados en la población seleccionada, ordenada de mayor a menor volumen.
- **HU07-RF-020**: El sistema DEBE desempatar por mayor retraso medio de los tickets vencidos, después por nombre ascendente sin distinguir mayúsculas y minúsculas y, por último, por equipo ascendente, con un orden estable.
- **HU07-RF-021**: Cada fila del ranking DEBE mostrar al menos el nombre del técnico, su equipo, el número de tickets vencidos y el retraso medio; si el técnico está inactivo, DEBE añadir «(inactivo)».
- **HU07-RF-022**: El sistema DEBE aplicar al ranking los mismos filtros y la misma población que al resto del dashboard.
- **HU07-RF-023**: El sistema DEBE atribuir cada ticket vencido a un único técnico o a «Sin asignar», conforme a HU07-RN-09, sin duplicarlo.
- **HU07-RF-024**: El sistema DEBE mostrar una fila separada «Sin asignar» para los tickets vencidos sin responsable, después de los técnicos, y DEBE garantizar que el total del ranking coincida con el total de vencidos.
- **HU07-RF-025**: Cuando no exista ningún ticket vencido en el periodo, el sistema DEBE mostrar un estado vacío específico en el ranking.
- **HU07-RF-026**: El ranking NO DEBE mostrar tickets individuales, datos del usuario creador, correos electrónicos, comentarios ni otra información personal distinta del nombre y equipo del técnico.

### Filtros

- **HU07-RF-027**: El sistema DEBE permitir filtrar por rango de fechas con fecha inicial y final, incluyendo ambos extremos y aplicando días naturales en Europe/Madrid.
- **HU07-RF-028**: El sistema DEBE aplicar por defecto el rango de los últimos 30 días naturales, incluido el día de la consulta, con todas las categorías y prioridades.
- **HU07-RF-029**: El sistema DEBE permitir seleccionar una o varias categorías, incluidas las categorías históricamente presentes y la opción «Sin categoría» cuando exista.
- **HU07-RF-030**: El sistema DEBE permitir seleccionar una o varias prioridades entre Crítica, Alta, Media y Baja, incluidas las prioridades históricamente presentes.
- **HU07-RF-031**: El sistema DEBE combinar las opciones de una misma dimensión con lógica «O» y las dimensiones entre sí con lógica «Y».
- **HU07-RF-032**: El sistema DEBE aplicar los filtros de forma homogénea a la matriz, a los totales y al ranking.
- **HU07-RF-033**: El sistema DEBE bloquear la consulta cuando la fecha inicial sea posterior a la final, mantener el estado anterior y mostrar un mensaje comprensible.
- **HU07-RF-034**: El sistema DEBE mostrar un estado específico de «sin resultados para los filtros seleccionados» con una acción para limpiar los filtros, distinto del estado vacío por ausencia de datos en el periodo.
- **HU07-RF-035**: El sistema DEBE ofrecer una acción para restablecer los filtros a la configuración por defecto.
- **HU07-RF-036**: El sistema DEBE conservar los filtros aplicados durante la sesión de navegación y al actualizar los datos.
- **HU07-RF-037**: El sistema DEBE mostrar un resumen de los filtros activos para que el supervisor sepa qué subconjunto está viendo.

### Semáforo

- **HU07-RF-038**: El sistema DEBE asignar un semáforo verde, ámbar o rojo al porcentaje de cumplimiento de cada combinación, de cada total por prioridad, de cada total por categoría y del total global, conforme a los umbrales vigentes de HU07-RN-11.
- **HU07-RF-039**: El sistema DEBE mostrar «Sin datos» en color neutro y sin semáforo cuando no existan tickets atendidos con SLA.
- **HU07-RF-040**: El sistema DEBE acompañar cada semáforo de un texto y un icono comprensibles, de modo que el color no sea el único portador de la información.
- **HU07-RF-041**: El sistema DEBE aplicar el valor exacto de un umbral a la banda superior y DEBE usar el porcentaje redondeado que se muestra para asignar el color.
- **HU07-RF-042**: El sistema DEBE incluir una leyenda con los umbrales vigentes y el significado de cada color, y DEBE aplicar los mismos umbrales de forma coherente en todo el dashboard.

### Permisos, actualización, errores y calidad

- **HU07-RF-043**: El sistema DEBE permitir el acceso al dashboard únicamente a supervisores y administradores, con alcance global sobre los datos de todos los equipos, y DEBE denegar el acceso a técnicos y usuarios sin revelar datos agregados.
- **HU07-RF-044**: El sistema DEBE calcular todas las secciones sobre una instantánea coherente y DEBE mostrar la fecha y hora de la última actualización en Europe/Madrid.
- **HU07-RF-045**: El sistema DEBE actualizar los datos automáticamente en un plazo máximo de 60 segundos y DEBE permitir la actualización manual, conservando los filtros.
- **HU07-RF-046**: Si una actualización falla y existen datos previos, el sistema DEBE conservar los últimos datos válidos con un aviso de posible desactualización y una acción de reintento.
- **HU07-RF-047**: Si la carga inicial falla, el sistema DEBE mostrar un error diferenciado con acción de reintento, sin mostrar métricas a cero ni un estado vacío.
- **HU07-RF-048**: El sistema DEBE distinguir los estados de periodo sin datos, filtros sin resultados, periodo sin tickets con SLA, periodo sin vencidos, error de carga, sesión caducada y rango inválido, con mensajes y acciones adecuados.
- **HU07-RF-049**: El sistema DEBE presentar el dashboard completo en menos de 3 segundos para un volumen de hasta 10.000 tickets en el periodo, en al menos el 95 % de las cargas.
- **HU07-RF-050**: El sistema DEBE presentar la vista en español de España, con fechas y horas en Europe/Madrid, formato local de números y cumplimiento de WCAG 2.1 AA, incluida la navegación por teclado y la información no dependiente del color.
- **HU07-RF-051**: El sistema DEBE garantizar que los totales de tickets, vencidos y atendidos cuadren entre la matriz, los totales y el ranking, incluida la fila «Sin asignar».
- **HU07-RF-052**: El sistema DEBE calcular las métricas exclusivamente a partir de los datos históricos de tickets y SLA, sin permitir ajustes manuales ni alterar la evidencia existente.

## Entidades Clave

- **Consulta del dashboard**: combinación de filtros aplicada (rango de fechas, categorías y prioridades), fecha y hora de generación, población resultante y estado de la consulta.
- **Métrica de cumplimiento**: prioridad, categoría, número de tickets, tickets atendidos con SLA, porcentaje de cumplimiento, tiempo medio de respuesta, tickets vencidos, tickets sin SLA, semáforo y estado de datos («con datos» o «sin datos»).
- **Resumen agregado**: total global y totales por prioridad y por categoría, calculados a partir de los tickets subyacentes y no del promedio de celdas.
- **Ranking de técnicos**: técnico, equipo, estado activo o inactivo, número de tickets vencidos acumulados y retraso medio de sus tickets vencidos.
- **Atribución de vencido**: ticket vencido, técnico o «Sin asignar» al que se atribuye, regla de atribución aplicada y periodo.
- **Semáforo**: banda de cumplimiento (verde, ámbar, rojo o sin datos), umbral aplicable, etiqueta textual e icono.
- **Ticket (fuente)**: número, fecha de creación, prioridad y categoría almacenadas, límite de SLA aplicado, estado actual, responsable actual, primera finalización y reaperturas.
- **SLA aplicado**: plazo y límite de SLA vigentes en el momento de creación del ticket, conservados con independencia de cambios posteriores.
- **Técnico**: usuario con rol técnico, nombre, equipo y estado activo o inactivo; es la unidad del ranking.
- **Categoría y prioridad**: clasificaciones del ticket almacenadas en el momento de su creación, con su etiqueta histórica y su estado actual activo o inactivo.

## Casos Límite y Manejo de Errores

| Situación | Comportamiento esperado | Mensaje orientativo |
|---|---|---|
| No hay tickets en el periodo seleccionado | Se muestra un estado vacío informativo con acción para ampliar el rango de fechas. | «No hay tickets en el periodo seleccionado. Prueba con un rango de fechas más amplio.» |
| Los filtros no devuelven ningún ticket | Se muestra un estado específico de «sin resultados», distinto del periodo sin datos, con acción para limpiar filtros. | «No hay resultados para los filtros seleccionados.» |
| Una combinación de prioridad y categoría no tiene tickets | No se muestra como fila; los totales por prioridad, categoría y global siguen visibles. | No aplica. |
| Todos los tickets del periodo carecen de SLA | El porcentaje y el tiempo medio muestran «Sin datos»; se muestra el conteo de «Sin SLA» y no hay vencidos. | «No hay tickets con SLA en el periodo seleccionado.» |
| Un ticket se atiende exactamente en su límite de SLA | Se considera dentro de plazo y no se contabiliza como vencido. | No aplica. |
| Un ticket activo supera su límite de SLA | Se contabiliza como vencido y su retraso sigue creciendo hasta que se atienda o finalice. | No aplica. |
| Un ticket alcanza su primera finalización después del límite de SLA | Se contabiliza como vencido con carácter histórico, aunque se consulte mucho después. | No aplica. |
| Un ticket se reabre después de finalizarse | Se cuenta una sola vez y conserva la primera finalización, conforme a HU04-RN-13. | No aplica. |
| Un ticket vencido se reasigna después del incumplimiento | Se atribuye según la regla mixta de HU07-RN-09 y no se duplica entre técnicos. | No aplica. |
| Un ticket vencido no tiene responsable | Se agrupa en «Sin asignar» y el total del ranking sigue cuadrando con el total de vencidos. | No aplica. |
| Una categoría o prioridad está desactivada | Se muestra con su etiqueta histórica y «(inactiva)», sin mezclarse con otras. | No aplica. |
| Un ticket no tiene categoría | Se agrupa bajo «Sin categoría». | No aplica. |
| La fecha inicial es posterior a la final | Se bloquea la consulta, se conserva el estado anterior y se muestra un mensaje comprensible. | «La fecha inicial no puede ser posterior a la fecha final.» |
| El rango de fechas es futuro | Se permite; si no hay tickets, se muestra el estado vacío correspondiente. | «No hay tickets en el periodo seleccionado.» |
| El volumen de tickets es elevado | Se muestra un indicador de carga y se mantiene el objetivo de tiempo de respuesta; no se truncan datos silenciosamente. | No aplica. |
| El rango cruza un cambio de hora oficial | Los días naturales se calculan en Europe/Madrid y las duraciones sobre instantes absolutos, sin duplicar ni perder tickets. | No aplica. |
| Dos técnicos comparten nombre | Se distinguen por equipo y por su identidad como usuario; sus métricas no se fusionan. | No aplica. |
| Todos los técnicos con vencidos están inactivos | El ranking los muestra con «(inactivo)». | No aplica. |
| No hay tickets vencidos en el periodo | El ranking muestra un estado vacío específico, no una lista de ceros. | «No hay tickets vencidos en el periodo seleccionado.» |
| Se produce un fallo al cargar el dashboard | Se muestra un error diferenciado con acción de reintento, sin métricas a cero ni estado vacío. | «No se pudo cargar el dashboard. Inténtalo de nuevo.» |
| Se produce un fallo al actualizar con datos previos | Se conservan los últimos datos válidos con un aviso de posible desactualización y una acción de reintento. | «No se pudieron actualizar los datos. Se muestran los últimos datos disponibles.» |
| La sesión ha caducado | Se solicita iniciar sesión de nuevo y se regresa al dashboard. | «Tu sesión ha caducado. Inicia sesión de nuevo.» |
| Un técnico o un usuario intenta acceder al dashboard | Se deniega el acceso sin mostrar datos agregados. | «No tienes permiso para acceder a este dashboard.» |
| Un supervisor intenta modificar un dato desde el dashboard | No existe ninguna acción de edición; la vista es de solo lectura. | No aplica. |

## Criterios de Éxito

| ID | Métrica | Objetivo |
|---|---|---|
| HU07-SC-001 | Métricas del dashboard que coinciden con el conjunto de tickets de control, dentro del redondeo definido | 100 % de las combinaciones y totales |
| HU07-SC-002 | Supervisores que ven el dashboard completo en menos de 3 segundos con hasta 10.000 tickets en el periodo | Al menos el 95 % de las cargas |
| HU07-SC-003 | Combinaciones con datos que muestran las tres métricas requeridas: cumplimiento, tiempo medio y vencidos | 100 % |
| HU07-SC-004 | Ranking de técnicos ordenado correctamente por volumen y reglas de desempate | 100 % de las consultas |
| HU07-SC-005 | Secciones y totales que usan el mismo conjunto de tickets tras aplicar filtros | 100 % |
| HU07-SC-006 | Semáforos que coinciden con los umbrales vigentes | 100 % |
| HU07-SC-007 | Indicadores visuales que incluyen texto e icono además del color | 100 % |
| HU07-SC-008 | Accesos no autorizados o exposiciones de datos individuales | 0 casos |
| HU07-SC-009 | Tickets sin SLA contabilizados como vencidos o incluidos en el cumplimiento | 0 casos |
| HU07-SC-012 | Estados de periodo sin datos, filtros sin resultados y error de carga correctamente diferenciados | 100 % |
| HU07-SC-013 | Datos actualizados o aviso de desactualización dentro del plazo definido | 100 % en 60 segundos o menos |
| HU07-SC-014 | Conciliación entre celdas, totales y ranking, incluida la fila «Sin asignar» | 100 % |
| HU07-SC-015 | Tickets atendidos exactamente en el límite contabilizados como dentro de plazo | 100 % |
| HU07-SC-016 | Etiquetas históricas de categorías y prioridades desactivadas conservadas | 100 % |

### Resultados de Negocio (post-lanzamiento, no verificables con la app)

- **HU07-BN-001**: El tiempo medio que tarda un supervisor en identificar las áreas con retrasos se reduce al menos un 50 % respecto al proceso anterior.
- **HU07-BN-002**: Al menos el 90 % de los supervisores encuestados afirma que el dashboard le ayuda a priorizar la revisión de retrasos y responsables.
- **HU07-BN-003**: Las revisiones de cumplimiento se realizan con una periodicidad al menos semanal, sin necesidad de elaborar informes manuales.
- **HU07-BN-004**: Tiempo que tarda un supervisor en identificar al técnico con más vencidos: menos de 10 segundos (métrica de usabilidad post-lanzamiento).
- **HU07-BN-005**: Supervisores que completan una consulta con filtros en el primer intento: al menos el 95 % (métrica de usabilidad post-lanzamiento).

## Supuestos

1. La autenticación y los roles (usuario, técnico, supervisor, administrador) ya existen; esta historia no define el mecanismo de acceso.
2. Supervisores y administradores pueden consultar el dashboard; los técnicos y los usuarios creadores no acceden en esta historia.
3. Cada usuario tiene un rol principal, conforme a los supuestos del sistema.
4. El sistema ya dispone de tickets con fecha de creación, prioridad, categoría, estado, responsable, límite de SLA, línea temporal y asignaciones históricas, según HU-01 a HU-06 y HU-08.
5. El límite de SLA se fija al crear el ticket y se conserva aunque cambie la configuración posterior, conforme a HU04-RN-03 y HU-08.
6. La primera finalización puede obtenerse de la información histórica del ticket como su primer paso a «Resuelto» o «Cerrado», conforme a HU04-RN-13.
7. Los tickets sin SLA no forman parte de los cálculos de cumplimiento ni del tiempo medio, y nunca se consideran vencidos.
8. El rango de fechas se aplica por fecha de creación y por días naturales en Europe/Madrid.
9. El rango por defecto son los últimos 30 días naturales, incluido el día de la consulta.
10. Los tickets reabiertos se cuentan una sola vez y conservan la primera finalización, conforme a HU04-RN-13.
11. La matriz muestra las combinaciones con datos; las combinaciones sin tickets no se muestra como filas.
12. El semáforo se aplica únicamente al porcentaje de cumplimiento; el tiempo medio y los vencidos se muestran con su valor.
13. Los umbrales del semáforo son verde ≥ 90 %, ámbar 70 %–<90 % y rojo < 70 %.
14. La atribución de vencidos sigue la regla mixta de HU07-RN-09: quien ejecutó la primera finalización si el ticket vencido ya la alcanzó, responsable actual si está vencido y pendiente de atención, y «Sin asignar» si no tiene responsable.
15. Los técnicos inactivos con vencidos históricos se muestran con la indicación «(inactivo)».
16. Los tickets vencidos sin responsable se agrupan en «Sin asignar» y no se consideran un técnico.
17. Las categorías y prioridades desactivadas se muestran con su etiqueta histórica y «(inactiva)».
18. Las fechas y horas se muestran en Europe/Madrid y se almacenan en UTC; los días naturales y los cambios de hora se gestionan sin duplicar ni perder tickets.
19. El volumen habitual del periodo es de hasta 10.000 tickets; el objetivo de carga es de menos de 3 segundos en al menos el 95 % de las consultas.
20. La vista está orientada a escritorio y tablet; no se requiere una experiencia específica para móvil en esta historia.
21. El dashboard no incluye exportación, informes programados, drill-down al detalle de tickets ni gráficos de tendencia en esta versión.
22. No se incluyen notificaciones ni alertas automáticas por incumplimiento; el semáforo y la actualización periódica son los mecanismos de aviso.
23. La información del ranking se limita a nombre y equipo del técnico; no se muestran correos ni otros datos personales.
24. Supervisores y administradores acceden con alcance global a todos los equipos; la vista no incorpora filtro ni restricción por equipo.
25. El término «tiempo de respuesta» se refiere al tiempo transcurrido entre la creación del ticket y su primera finalización (primer paso a «Resuelto» o «Cerrado»).

## Fuera de Alcance

- Crear, editar, reasignar, escalar, cerrar o eliminar tickets desde el dashboard.
- Modificar prioridades, categorías, responsables o plazos de SLA desde el dashboard.
- Filtrar el dashboard por equipo o restringir la visibilidad al equipo del supervisor; el alcance es global.
- Exportar los datos a CSV, PDF u otros formatos.
- Programar informes o envíos periódicos por correo.
- Consultar el detalle o la lista de tickets individuales desde una celda o desde el ranking.
- Gráficos de tendencia temporal, comparativas históricas avanzadas, previsiones o análisis predictivo.
- Actualización en tiempo real por streaming; la actualización es periódica y manual.
- Configurar los umbrales del semáforo desde la interfaz; los umbrales son una decisión de negocio.
- Gestión de equipos, turnos, vacaciones o capacidad de los técnicos.
- Evaluación individual del desempeño o uso de las métricas con fines disciplinarios.
- Notificaciones o alertas automáticas por incumplimiento de SLA.
- Pausa del reloj de SLA, calendarios laborales o festivos.
- Multiorganización, multi-tenant o comparación entre organizaciones.
- API pública o integración con herramientas externas de business intelligence.
- Migración o corrección retroactiva de datos históricos.

## Dependencias

- HU-01: creación de tickets y datos iniciales.
- HU-02: consulta del estado y línea temporal del ticket.
- HU-03: respuesta del usuario y transición desde «Pendiente de usuario».
- HU-04: cola de trabajo priorizada, reglas de propiedad, límite de SLA fijo, cálculo del tiempo restante y resultado histórico del SLA (HU04-RN-01, HU04-RN-03, HU04-RN-13).
- HU-05: línea temporal «append-only», cambios de estado, resoluciones y permisos (HU05-RN-02, HU05-RN-05, HU05-RN-07).
- HU-06: reasignación y escalado, histórico de responsables y notificaciones (HU06-RN-07, HU06-RN-09).
- HU-08: configuración de categorías, prioridades y plazos de SLA, y conservación de la configuración vigente al crear cada ticket (HU08-RN-04).
- RF-06 del sistema: dashboard de supervisión.
- RF-07 del sistema: administración de catálogos y SLA.
- Sistema de autenticación y autorización por roles.
- Información histórica de tickets, SLA y asignaciones.

## Trazabilidad de los Criterios de Aceptación

| Criterio de aceptación de HU-07 | Reglas de negocio | Requisitos funcionales |
|---|---|---|
| Vista de dashboard con métricas por prioridad (Crítica, Alta, Media, Baja) y por categoría. | HU07-RN-01, HU07-RN-02, HU07-RN-07 | HU07-RF-001 a HU07-RF-006, HU07-RF-010, HU07-RF-016 a HU07-RF-018 |
| Para cada combinación: % de tickets atendidos dentro de plazo, tiempo medio de respuesta, tickets vencidos. | HU07-RN-03, HU07-RN-04, HU07-RN-05, HU07-RN-06, HU07-RN-07 | HU07-RF-006 a HU07-RF-018 |
| Lista de técnicos con tickets vencidos acumulados, ordenados por volumen. | HU07-RN-08, HU07-RN-09 | HU07-RF-019 a HU07-RF-026 |
| Filtros por rango de fechas, categoría, prioridad. | HU07-RN-02, HU07-RN-10 | HU07-RF-027 a HU07-RF-037 |
| Indicadores visuales (semáforo: verde/ámbar/rojo) por umbrales de cumplimiento. | HU07-RN-11, HU07-RN-14, HU07-RN-15 | HU07-RF-038 a HU07-RF-042, HU07-RF-050 |
| Solo supervisores y administradores acceden a información agregada. | HU07-RN-13, HU07-RN-17 | HU07-RF-043, HU07-RF-052 |
| La vista distingue ausencia de datos, filtros sin resultados y errores. | HU07-RN-16 | HU07-RF-046 a HU07-RF-048 |

## Módulos previos

Los módulos HU-04, HU-05 y HU-06 no se reproducen en este documento; se consultan en `specs/004-prioritized-work-queue/spec.md`, `specs/005-cambio-estado-resolucion/spec.md` y `specs/006-reasignar-escalar-ticket/spec.md`.

