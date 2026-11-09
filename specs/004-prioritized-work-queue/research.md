# Investigación y Decisiones Técnicas: Cola de Trabajo Priorizada (HU-04)

**Funcionalidad**: `specs/004-prioritized-work-queue`
**Fecha**: 2026-10-29
**Estado**: Fase 0 completada; no quedan `NEEDS CLARIFICATION`.

Este documento registra las decisiones que sostienen [plan.md](./plan.md). Cada decisión indica qué se eligió, por qué y qué alternativas se descartaron.

---

## Contexto de partida

El repositorio no contiene todavía código de aplicación: solo especificaciones, configuración de Spec Kit y `CONSTITUTION.md`. La pila compartida del proyecto está fijada por el usuario: **Vue 3, FastAPI, PostgreSQL y Tailwind**. El modelo de datos base procede de `specs/001-helpdesk-ticketing/spec.md`:

- `Ticket`: id, número, título, estado, prioridad, categoría, creador, asignado, fecha_creación, fecha_límite_SLA, fecha_cierre, versión_SLA_aplicada.
- `Prioridad`: id, nombre, nivel (1-4), color, plazo_base_horas, activa.
- `Categoría`: id, nombre, descripción, activa.
- `Usuario`: id, nombre, email, rol, equipo, activo.

La HU-04 es de solo lectura. No crea tickets, no cambia estados, no reasigna y no modifica el SLA.

---

## D-01. Filtrado, orden y paginación en el servidor

**Decisión**: el endpoint aplica visibilidad, filtros, orden y paginación en PostgreSQL. El frontend no filtra ni ordena el conjunto completo.

**Razón**:
- Garantiza que la primera página contenga siempre los tickets más urgentes del conjunto (FR-017).
- Evita enviar tickets que no se van a mostrar y mantiene la respuesta pequeña.
- La regla de propiedad se aplica una sola vez, en la consulta base, lo que reduce el riesgo de fuga (FR-001, FR-002, FR-029).
- Con ≤ 100 tickets por técnico el coste es trivial y los índices cubren la consulta.

**Alternativas descartadas**:
- *Cargar todo y filtrar en Vue*: rompe la paginación correcta, expone tickets no necesarios y duplica la lógica de orden.
- *Ordenar en cliente tras paginar en servidor*: produciría páginas incorrectas.
- *GraphQL*: complejidad innecesaria para una única consulta de lectura.

---

## D-02. Identidad del técnico desde la autenticación

**Decisión**: el endpoint `GET /api/v1/me/work-queue` obtiene el técnico del token JWT enviado en `Authorization: Bearer`. No existe parámetro `technician_id` ni equivalente. La consulta siempre incluye `assignee_id = current_user.id`.

**Razón**:
- Cumple FR-001/FR-002 y el principio de datos con respeto.
- Elimina una clase entera de vulnerabilidades IDOR: no hay identificador que manipular.
- Simplifica el contrato y las pruebas.

**Alternativas descartadas**:
- *`GET /technicians/{id}/tickets`*: permitiría a un técnico cambiar el id y ver tickets ajenos; exigiría autorización adicional y pruebas negativas.
- *Filtrar por email o nombre*: identificadores no estables y potencialmente ambiguos.

**Nota**: si el proyecto ya expone un endpoint de autenticación (`/me`), se reutiliza para obtener la identidad; esta historia no implementa autenticación ni emisión de tokens.

---

## D-03. Un único endpoint con metadatos frente a un endpoint `/meta`

**Decisión**: una sola respuesta incluye `items`, `pagination`, `counts`, `available_filters`, `applied_filters` y `meta.server_time`.

**Razón**:
- Evita una segunda llamada y una ventana de inconsistencia entre opciones de filtro y datos.
- El número de resultados y las opciones de filtro se calculan sobre la cola del técnico y cambian con ella; mantenerlos en la misma transacción lógica es más simple y correcto.
- Menos superficie de API y menos código.

**Alternativas descartadas**:
- *`GET /me/work-queue` + `GET /me/work-queue/meta`*: dos peticiones, dos estados de carga y posible desincronización de opciones de filtro.
- *Reutilizar endpoints de catálogos (`/statuses`, `/priorities`)*: devolverían prioridades globales, no las prioridades presentes en la cola del técnico.

---

## D-04. Almacenamiento de fechas en UTC y cálculo relativo

**Decisión**:
- Columnas temporales `TIMESTAMPTZ` en PostgreSQL y `DateTime(timezone=True)` en SQLAlchemy.
- El backend calcula `remaining_seconds` contra `datetime.now(timezone.utc)`.
- La respuesta incluye `server_time` y segundos restantes; el frontend usa esos segundos, no la hora local.
- Europe/Madrid se usa solo para formatear fechas absolutas con `Intl`.

**Razón**:
- Un instante absoluto es inmune a la zona horaria del servidor, del navegador y al cambio de hora oficial.
- Enviar una duración relativa evita comparar relojes distintos.
- `Intl` con `timeZone: 'Europe/Madrid'` resuelve DST sin lógica manual.

**Alternativas descartadas**:
- *Guardar hora local de Madrid*: ambigua en el cambio de otoño (02:00-02:59 se repite) y depende de la configuración del servidor.
- *Enviar solo `deadline` y calcular en el cliente con `new Date()`*: un reloj de cliente desajustado produce cuentas atrás erróneas.
- *Usar `datetime.utcnow()`*: devuelve un datetime naive y es una fuente clásica de errores; se prohíbe.

**Detalle**: `remaining_seconds = floor((deadline - now_utc).total_seconds())`, puede ser negativo. La clasificación usa segundos exactos; la visualización redondea a la baja (RN-04).

---

## D-05. Reloj monotónico en el frontend y resincronización

**Decisión**: entre polls, la cuenta atrás se decrementa con `performance.now()` partiendo del `remaining_seconds` recibido. Cada 60 s y al recuperar foco/visibilidad se vuelve a consultar el servidor.

**Razón**:
- `performance.now()` es monotónico y no retrocede si el usuario cambia la hora del sistema.
- El servidor sigue siendo la autoridad: cada poll reemplaza el ancla.
- Cumple FR-005 y RN-14 sin WebSockets ni temporizadores de servidor.

**Alternativas descartadas**:
- *`setInterval` restando 1 s a un contador*: deriva con pestañas en segundo plano y suspensión del equipo.
- *WebSockets/SSE*: complejidad de infraestructura y reconexión para un requisito de 60 s.
- *Recargar la página cada minuto*: pierde filtros y foco, y contradice la experiencia esperada.

---

## D-06. Umbral de aviso piecewise

**Decisión**:

```text
si duración_total < 60 min:  umbral = duración_total / 2
si duración_total >= 60 min: umbral = max(60 min, 25 % de duración_total)
```

**Razón**:
- Evita que un SLA corto nazca ya en ámbar (con `max(60 min, 25 %)` un SLA de 30 min sería ámbar desde el primer segundo).
- Mantiene proporcionalidad en SLA cortos y un mínimo útil en SLA largos.
- Ejemplos: 30 min → 15 min; 60 min → 60 min; 4 h → 60 min; 24 h → 6 h.
- Es la respuesta aceptada en la clarificación de la spec.

**Alternativas descartadas**:
- *Solo `max(60 min, 25 %)`*: SLA cortos siempre en alarma.
- *Solo 25 %*: SLA de 24 h avisaría con 6 h, pero SLA de 4 h avisaría con 1 h; se pierde el mínimo de 60 min en SLA medios.
- *Umbral configurable por el técnico*: fuera de alcance (spec lo excluye).

---

## D-07. `finalized_at` para el resultado histórico y el orden final

**Decisión**: añadir `tickets.finalized_at TIMESTAMPTZ NULL`, fijado en la primera transición a `resuelto` o `cerrado` y no sobrescrito después. Se usa para:
- Calcular el resultado histórico (`finalized_at <= sla_deadline` → cumplido).
- Calcular `breach_delay_seconds = finalized_at - sla_deadline`.
- Ordenar los finalizados por `finalized_at DESC`.

**Razón**:
- El modelo base tiene `fecha_cierre`, pero no garantiza que se rellene al pasar a `Resuelto` (solo al cerrar). RN-13 exige el primer paso a cualquiera de los dos estados finales.
- Sin una fecha fiable no se puede mostrar "Dentro de plazo"/"Incumplido" ni ordenar finalizados de forma determinista.
- Es una columna de soporte, no funcionalidad nueva.

**Alternativas descartadas**:
- *Reutilizar `closed_at`/`fecha_cierre`*: insuficiente para `Resuelto` y potencialmente reescrita.
- *Inferir la fecha del histórico de estados*: requiere una tabla de auditoría que puede no existir o no ser completa; más costoso.
- *Usar `updated_at`*: cambia por cualquier edición posterior y falsea el resultado.

**Migración**: backfill desde `closed_at` si existe; en su defecto, desde `updated_at` para tickets ya finalizados. Restricción: estado final ⇒ `finalized_at IS NOT NULL`.

---

## D-08. Orden con estados finales

**Decisión**: los activos siempre primero; dentro de ellos, prioridad ASC (nivel 1 = Crítica), deadline ASC con `NULLS LAST`, número ASC. Los finalizados después, sin ordenar por prioridad, por `finalized_at DESC` y número ASC de desempate.

**Razón**:
- El trabajo accionable debe estar arriba; el historial no debe competir con él.
- `finalized_at DESC` responde a "qué he terminado recientemente", que es el uso esperado del filtro de estados finales.
- El desempate por número da un orden total y estable para paginar.

**Alternativas descartadas**:
- *Intercalar finalizados por prioridad*: mezcla trabajo pendiente con historial y dificulta la lectura.
- *Finalizados por deadline*: no representa cuándo se terminó.
- *Finalizados por número*: no refleja recencia.

**Convención**: `priority.level` 1 = Crítica, 4 = Baja. Se documenta y se prueba; si el esquema real usara la inversa, se cambia solo el término `ORDER BY` y los fixtures.

---

## D-09. Paginación por offset

**Decisión**: `page` + `page_size` (25 por defecto, máximo 100), con `COUNT(*)` para el total y orden total con desempate por número.

**Razón**:
- Volumen máximo previsto: 100 tickets por técnico; offset es suficiente y mucho más simple.
- La UI necesita "página X de Y" y el total filtrado (FR-026).
- El orden total evita duplicados/huecos entre páginas.

**Alternativas descartadas**:
- *Keyset/cursor*: más eficiente a gran escala, pero añade complejidad de cursor, total y navegación no justificada aquí.
- *Scroll infinito*: dificulta volver a una posición y no aporta con ≤ 100 tickets.

**Nota**: si en el futuro el volumen crece, se puede migrar a keyset sin cambiar el contrato de la UI (el contrato expone paginación, no el mecanismo).

---

## D-10. Polling cada 60 s frente a tiempo real

**Decisión**: `setInterval` de 60 s en el store, pausado cuando la pestaña está oculta, con recarga inmediata al volver a visible o al recuperar foco.

**Razón**:
- Cumple FR-005/RN-14 con la infraestructura más simple.
- El volumen es bajo y la vista es de consulta.
- No requiere servidor de eventos ni reconexión.

**Alternativas descartadas**:
- *WebSockets*: sobreingeniería para una vista de 100 filas.
- *SSE*: algo más simple que WebSockets, pero sigue requiriendo gestión de conexión, proxies y reconexión.
- *Refresco manual*: incumple FR-005.

**Detalle**: cada petición cancela la anterior con `AbortController`; solo se aplica la respuesta de la última petición.

---

## D-11. Estado de filtros en URL + Pinia

**Decisión**: los filtros y la página se reflejan en la query string (`estado`, `prioridad`, `pagina`) y en un store Pinia. El store es la fuente de verdad durante la sesión; la URL permite recarga, atrás/adelante y enlaces.

**Razón**:
- FR-028 exige mantener los filtros durante la navegación.
- La URL hace el estado observable y compartible sin añadir persistencia local.
- Evita duplicar estado entre componentes.

**Alternativas descartadas**:
- *Solo estado local del componente*: se pierde al navegar o recargar.
- *`localStorage`*: persiste más de lo pedido y complica la limpieza; la spec habla de la sesión de navegación.
- *Solo store sin URL*: se pierde al recargar y no permite atrás/adelante.

**Normalización**: valores desconocidos en la URL se descartan y se reescribe la URL; nunca se envían al backend valores inválidos.

---

## D-12. Mapas estáticos de clases Tailwind

**Decisión**: `slaStyles.ts` contiene objetos `Record<SlaState, string>` con clases completas (`bg-red-50`, `border-amber-500`, etc.). No se generan clases por concatenación.

**Razón**:
- Tailwind solo incluye en el build las clases que puede detectar literalmente; `bg-${color}-100` no se genera.
- Centraliza la semántica visual y evita que cada componente invente colores.
- Facilita auditoría de contraste y cambios futuros.

**Alternativas descartadas**:
- *Interpolar con el color de la base de datos*: impredecible y rompe el purge.
- *Estilos inline con hex*: dificulta el tema y el contraste; el color de prioridad no garantiza accesibilidad.
- *`@apply` por estado*: válido, pero los mapas explícitos son más fáciles de rastrear y testear.

---

## D-13. SQLAlchemy síncrono

**Decisión**: SQLAlchemy 2.0 en modo síncrono con psycopg 3, ejecutado por FastAPI en el threadpool de las rutas `def`.

**Razón**:
- Una sola consulta de lectura; no hay necesidad de async.
- Menos piezas (sin `asyncpg`, sin sesión async, sin `pytest-asyncio`).
- Alineado con el principio de simplicidad.

**Alternativas descartadas**:
- *SQLAlchemy async + asyncpg*: útil con muchas conexiones concurrentes o IO externo, no aquí.
- *Consultas SQL crudas*: perderíamos tipado y composición de filtros; el `ORDER BY` puede expresarse con SQLAlchemy sin problema.

---

## D-14. Pruebas de paridad backend/frontend

**Decisión**: mantener una tabla de vectores de SLA (duración total, restante, estado esperado) en ambos lados. Backend y frontend implementan la misma función y se prueban contra los mismos valores.

**Razón**:
- El cliente reclasifica entre polls; una divergencia mostraría un color distinto al que el servidor considera correcto.
- No se introduce un paquete compartido ni generación de código para una fórmula de pocas líneas.
- Los vectores documentan los casos límite (0, −1, 60 min, SLA corto).

**Alternativas descartadas**:
- *Solo confiar en el estado del servidor y no reclasificar*: entre polls el ticket podría seguir ámbar cuando ya venció, hasta 60 s.
- *Compartir código Python/TS*: capa de build y mantenimiento desproporcionados.

---

## D-15. Accesibilidad sin depender del color

**Decisión**: cada estado de SLA combina color + icono + texto; la tabla es semántica; los filtros son `fieldset`/`legend` con checkboxes; foco visible; contraste ≥ 4.5:1; el número de resultados no se anuncia cada segundo.

**Razón**:
- FR-022 y RN-16 exigen que el riesgo sea perceptible sin color.
- Una tabla real permite navegación por lector de pantalla y encabezados asociados.
- Anunciar cada tick sería ruidoso; se anuncia el cambio de estado, no cada segundo.

**Alternativas descartadas**:
- *Solo color de fondo*: incumple accesibilidad y la spec.
- *`div` con roles ARIA manuales*: más frágil que una tabla HTML nativa.
- *`aria-live` en cada actualización del contador*: saturaría al usuario.

---

## Resumen de resolución de incógnitas

| Incógnita | Resolución |
|-----------|------------|
| ¿Dónde se filtra y ordena? | Servidor (D-01). |
| ¿Cómo se identifica al técnico? | Token JWT, sin parámetro (D-02). |
| ¿Un endpoint o dos? | Uno con metadatos (D-03). |
| ¿Cómo evitar desajustes horarios? | UTC + segundos restantes + reloj monotónico (D-04, D-05). |
| ¿Umbral con SLA < 60 min? | Mitad del total (D-06). |
| ¿Cómo se sabe cuándo se finalizó? | `finalized_at` (D-07). |
| ¿Dónde van los finalizados? | Al final, por `finalized_at DESC` (D-08). |
| ¿Offset o cursor? | Offset (D-09). |
| ¿Tiempo real? | Polling 60 s (D-10). |
| ¿Dónde viven los filtros? | URL + Pinia (D-11). |
| ¿Cómo se aplica Tailwind condicional? | Mapas estáticos (D-12). |
| ¿Sync o async? | Sync (D-13). |
| ¿Cómo se evita divergencia de SLA? | Vectores de paridad (D-14). |
| ¿Cómo se cumple accesibilidad? | Color + icono + texto y tabla semántica (D-15). |

**Salida**: no quedan `NEEDS CLARIFICATION`. Se puede pasar a Fase 1 (data model, contrato y quickstart).
