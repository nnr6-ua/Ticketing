# Propuesta de reparto: 2 personas × 4 historias

| Persona | Historias | Spec | Tema |
|---|---|---|---|
| Nayara | 1 + 2 + 3 + 8 | [001](../specs/001-crear-ticket/spec.md), [002](../specs/002-ticket-timeline-history/spec.md), [003](../specs/003-responder-peticion-tecnico/spec.md), [008](../specs/008-configuracion-plazos-sla/spec.md) | Ciclo del solicitante y base de configuración: alta del ticket, consulta de estado e historial, petición/respuesta de información y catálogos/plazos SLA |
| José Miguel Sáez Castro | 4 + 5 + 6 + 7 | [004](../specs/004-prioritized-work-queue/spec.md), [005](../specs/005-cambio-estado-resolucion/spec.md), [006](../specs/006-reasignar-escalar-ticket/spec.md), [007](../specs/007-dashboard-cumplimiento-sla/spec.md) | Ciclo del equipo técnico y supervisión: cola priorizada, cambio de estado y resolución, reasignación/escalado y dashboard de cumplimiento |

Especificación compartida, propiedad de Nayara y utilizada por las ocho historias: [000](../specs/000-helpdesk-ticketing/spec.md). La constitución ratificada está en [`.specify/memory/constitution.md`](../.specify/memory/constitution.md); `CONSTITUTION.md` en la raíz es solo un resumen informativo.

## Por qué así

- Nayara agrupa las historias del creador del ticket y la configuración que las alimenta: HU-01 captura la categoría, la prioridad y el SLA vigente; HU-02 y HU-03 leen lo que el técnico escribe; HU-08 define los catálogos y los plazos que HU-01 congela en cada ticket.
- José Miguel agrupa el trabajo operativo del técnico: HU-04 ordena la cola, HU-05 ejecuta transiciones y resoluciones, HU-06 mueve la responsabilidad y HU-07 agrega el resultado para el supervisor.
- Las dos mitades se acoplan por tres puntos concretos: la respuesta de HU-03 devuelve el ticket a la cola colectiva de HU-04; HU-05 valida la transición automática que dispara HU-03; HU-06 y HU-05 escriben las entradas que HU-07 consume sin modificarlas.
- La paralelización por historia explica las migraciones `merge` `0007_merge_hu06_hu08` y `0009_merge_public_comments`, y la ratificación explícita de la constitución en el commit `810d8d7`.

## Dependencias entre personas

1. La spec `000` y la constitución son la base común: ninguna historia redefine los estados, los roles, el formato de error ni la línea temporal inmutable.
2. Nayara necesita HU-08 para fijar la matriz SLA y los valores por defecto de HU-01; mientras tanto usa datos de ejemplo deterministas de `backend/scripts/seed_dev.py`.
3. José Miguel necesita los catálogos y el plazo capturado en HU-01/HU-08 para ordenar HU-04 y calcular HU-07.
4. Nayara necesita que HU-05 y HU-06 escriban las entradas de la línea temporal que HU-02 muestra y que HU-07 agrega.
5. José Miguel necesita la transición de HU-03 para devolver a la cola colectiva los tickets pendientes de usuario ya respondidos.
6. Integración final: Nayara unifica navegación por rol, renumera las carpetas de specs y prepara la demo en vídeo; José Miguel conserva la constitución y resuelve los conflictos de backend/frontend resultantes de los merges.

## Acuerdos cerrados antes de empezar

1. **Estados del ticket**: `abierto`, `en_progreso`, `pendiente_usuario`, `resuelto`, `cerrado`; las transiciones inválidas se rechazan y `cerrado` es terminal.
2. **Cálculo del plazo**: horas naturales continuas (24/7) desde la creación del ticket, sin calendario laboral ni festivos; cada ticket congela la versión de configuración vigente (HU-08).
3. **Notificaciones**: solo avisos en aplicación (campana); correo electrónico y preferencias fuera de alcance en v1, de modo que HU-03 y HU-06 no dependen de SMTP.
4. **Sugerencias de HU-01**: categoría sugerida fija y prioridad editable; el número de ticket es secuencial con formato `TK-000001`.
5. **Cola de trabajo**: los tickets asignados son propiedad de un único técnico; la única excepción es la cola colectiva de tickets sin responsable en `en_progreso` que HU-03 devuelve al equipo.
6. **Dashboard**: la métrica temporal es tiempo hasta la primera finalización; semáforo verde ≥ 90 %, ámbar 70 %–< 90 %, rojo < 70 %, no configurable desde la interfaz.
7. **Autoridad**: la identidad se obtiene solo del JWT; la autorización se aplica siempre en servidor; la línea temporal es `append-only` e inmutable.

## Orden sugerido

- Semana 1: `000` y constitución, seguidas de HU-08 (Nayara) y HU-04 (José Miguel), que fijan catálogos, SLA y orden de la cola.
- Semana 2: HU-01, HU-02 y HU-03 (Nayara) en paralelo con HU-05 y HU-06 (José Miguel).
- Semana 3: HU-07 (José Miguel), integración de ramas, validación manual de los `quickstart.md` y demo (Nayara).

La ejecución real reconstruida en `docs/memoria.md` siguió este orden, con las desviaciones propias de los merges: HU-05 y HU-04 se integraron antes que HU-01/HU-02, y HU-07 se cerró después de HU-08.
