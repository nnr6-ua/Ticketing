# Especificación Funcional: Configuración de categorías, prioridades y plazos (HU-08)

**Rama**: `hu-08-configuracion-sla`

**Creado**: 2026-11-15

**Estado**: Borrador

**Entrada**: HU-08 — «Configuración de categorías, prioridades y plazos (SLA)». Un administrador debe poder configurar las categorías, las prioridades y los plazos asociados a cada combinación, con la garantía de que los cambios futuros en los plazos no afectan retroactivamente a los tickets ya cerrados con las reglas anteriores.

## Resumen

La organización necesita que el sistema refleje sus propias reglas de atención. Para ello, un administrador podrá mantener el catálogo de categorías, el catálogo de prioridades con su plazo base y una matriz de plazos por combinación categoría × prioridad. Cada modificación de plazos queda versionada y pasa a aplicarse únicamente a los tickets creados a partir de ese momento.

La garantía central es la no retroactividad: un ticket conserva, de forma inmutable, el plazo y la versión de configuración vigentes en el instante de su creación. Cambiar los plazos después no altera el límite, el resultado de SLA ni la información histórica de tickets abiertos o cerrados. Las categorías y prioridades que ya tienen tickets no se eliminan: se desactivan para que dejen de ofrecerse a nuevos tickets sin romper el histórico.

## Clarifications

### Session 2026-11-15

- Q: ¿Cómo deben contarse las horas de los plazos SLA para calcular el límite de un ticket? → A: En horas naturales continuas (24/7) desde la creación del ticket, sin calendario laboral ni festivos.
- Q: ¿Qué debe ocurrir con el orden de urgencia de los tickets existentes cuando el administrador cambia el nivel numérico de una prioridad? → A: Cada ticket congela el nivel de urgencia que tenía al crearse; los cambios de nivel solo afectan a tickets nuevos.
- Q: ¿Debe el perfil de supervisor poder consultar la configuración y el histórico de cambios, aunque no pueda modificarlos? → A: No; solo el perfil de administración puede consultar la configuración y su histórico. Los demás perfiles solo acceden al catálogo activo necesario para operar con tickets.
- Q: ¿Cómo debe resolverse que dos administradores modifiquen la misma categoría, prioridad o regla de plazo al mismo tiempo? → A: Con bloqueo optimista: la edición que se base en una versión ya superada se rechaza con un aviso de conflicto y debe recargarse y reintentarse.
- Q: ¿Los cambios de plazos deben aplicarse siempre al confirmarse o deben poder programarse para una fecha futura? → A: Siempre al confirmarse; no se permite fechar en el pasado ni programar una fecha futura.
- Q: ¿La unicidad del nivel de prioridad incluye prioridades inactivas o de sistema? → A: Solo se valida entre prioridades no-sistema activas. Una prioridad inactiva libera su nivel para otra prioridad activa; al reactivarla se vuelve a validar. La prioridad de sistema de reserva queda excluida.
- Q: ¿El catálogo operativo de categorías y prioridades activas está restringido a administración? → A: No. Los perfiles autenticados solo acceden al catálogo activo necesario para crear tickets. La configuración administrativa completa, incluidas inactivas, sistema, reglas e histórico, es exclusiva de administración.

## Actores

- **Administrador**: crea, edita, desactiva y reactiva categorías y prioridades; define y versiona los plazos de la matriz SLA; consulta el histórico de cambios. Es el único perfil que puede consultar o modificar la configuración administrativa completa.
- **Usuario, técnico y supervisor**: no pueden consultar ni modificar la configuración administrativa ni su histórico. Consumen el catálogo activo al crear, filtrar o clasificar tickets y conservan la información histórica de los tickets ya registrados.

## Escenarios de Usuario y Pruebas

### Historia 1 — Gestionar el catálogo de categorías (Prioridad: P1)

Como administrador, quiero crear, editar y desactivar categorías, para que el sistema clasifique los tickets según las áreas reales de la organización.

**Por qué esta prioridad**: las categorías son la dimensión básica de clasificación y una de las dos entradas de la matriz de plazos.

**Prueba independiente**: el administrador crea una categoría, edita su descripción, la desactiva y comprueba que deja de ofrecerse para nuevos tickets mientras los tickets existentes siguen mostrándola.

**Escenarios de aceptación**:

1. **Dado** un administrador autenticado, **cuando** crea una categoría con un nombre válido y una descripción opcional, **entonces** la categoría queda disponible para clasificar nuevos tickets.
2. **Dado** una categoría existente, **cuando** el administrador cambia su nombre o descripción, **entonces** el cambio se guarda y queda registrado en el histórico de configuración.
3. **Dado** una categoría existente, **cuando** el administrador intenta crear otra con el mismo nombre ignorando mayúsculas, minúsculas y espacios sobrantes, **entonces** el sistema rechaza la operación y explica el conflicto.
4. **Dado** una categoría en uso por al menos un ticket, **cuando** el administrador intenta eliminarla definitivamente, **entonces** el sistema lo impide y ofrece desactivarla.
5. **Dado** una categoría inactiva, **cuando** el administrador la reactiva, **entonces** vuelve a estar disponible para nuevos tickets.
6. **Dado** una categoría sin tickets ni reglas asociadas, **cuando** el administrador decide eliminarla definitivamente, **entonces** el sistema permite la eliminación y la retira del catálogo.
7. **Dado** cualquier perfil distinto de administración, incluidos usuario, técnico y supervisor, **cuando** intenta crear, editar, desactivar o consultar el catálogo administrativo de categorías, incluidas las inactivas, **entonces** el sistema rechaza la operación por falta de permisos, sin afectar al catálogo activo que se usa para clasificar tickets.

---

### Historia 2 — Gestionar el catálogo de prioridades y su plazo base (Prioridad: P1)

Como administrador, quiero crear, editar y desactivar prioridades con su nivel, color y plazo base de atención, para que la urgencia de un ticket se traduzca en un objetivo de tiempo.

**Por qué esta prioridad**: la prioridad determina el orden de atención y aporta el plazo por defecto cuando no existe una regla específica para la categoría.

**Prueba independiente**: el administrador libera un nivel desactivando una prioridad no referenciada, crea otra prioridad con ese nivel, define su plazo base, la edita y la desactiva; se comprueba que los nuevos tickets dejan de poder seleccionarla y que sus tickets históricos no cambian.

**Escenarios de aceptación**:

1. **Dado** un administrador autenticado, **cuando** crea una prioridad con nombre, nivel numérico libre entre las prioridades no-sistema activas, color y plazo base positivo, **entonces** la prioridad queda disponible para clasificar nuevos tickets. Si no hay ningún nivel libre, el sistema rechaza la creación y explica cómo liberar uno.
2. **Dado** una prioridad existente, **cuando** el administrador modifica su plazo base, **entonces** el cambio genera una nueva versión de configuración y solo se aplica a los tickets creados después.
3. **Dado** el catálogo de prioridades, **cuando** el administrador intenta usar un nivel numérico ya asignado a otra prioridad no-sistema activa, **entonces** el sistema rechaza la operación.
4. **Dado** una prioridad con tickets asociados, **cuando** el administrador intenta eliminarla definitivamente, **entonces** el sistema lo impide y ofrece desactivarla.
5. **Dado** una prioridad inactiva, **cuando** un usuario crea un ticket, **entonces** esa prioridad no aparece entre las opciones seleccionables.
6. **Dado** que la prioridad desactivada es la que se usa por defecto, **cuando** el administrador intenta desactivarla sin designar otra, **entonces** el sistema lo impide para garantizar que siempre exista una prioridad aplicable.
7. **Dado** cualquier perfil distinto de administración, incluidos usuario, técnico y supervisor, **cuando** intenta modificar o consultar el catálogo administrativo de prioridades, incluidas las inactivas, **entonces** el sistema rechaza la operación por falta de permisos, sin afectar al catálogo activo que se usa para crear tickets.

---

### Historia 3 — Configurar la matriz de plazos por categoría y prioridad (Prioridad: P1)

Como administrador, quiero definir el plazo de atención para cada combinación de categoría y prioridad, para que las reglas de la organización se apliquen con la precisión que necesitan.

**Por qué esta prioridad**: es el mecanismo que traduce la política de la organización en plazos concretos por tipo de incidencia y urgencia.

**Prueba independiente**: el administrador define una regla para una categoría y prioridad concretas, crea un ticket con esa combinación y comprueba que el límite aplicado corresponde a la regla específica y no al plazo base de la prioridad.

**Escenarios de aceptación**:

1. **Dado** una categoría y una prioridad activas, **cuando** el administrador define un plazo positivo para esa combinación, **entonces** la regla queda vigente y prevalece sobre el plazo base de la prioridad.
2. **Dado** una combinación sin regla específica, **cuando** se crea un ticket con esa combinación, **entonces** el sistema aplica el plazo base de la prioridad.
3. **Dado** una regla existente, **cuando** el administrador cambia su plazo, **entonces** se crea una nueva versión de la regla con su fecha de aplicación y la anterior se conserva para el histórico.
4. **Dado** una regla existente, **cuando** el administrador la retira, **entonces** los nuevos tickets de esa combinación pasan a usar el plazo base de la prioridad, sin modificar los tickets ya creados.
5. **Dado** una combinación categoría × prioridad, **cuando** el administrador intenta definir dos reglas vigentes simultáneas para la misma combinación, **entonces** el sistema lo impide.
6. **Dado** un plazo de cero, negativo o no numérico, **cuando** el administrador intenta guardarlo, **entonces** el sistema rechaza la operación y muestra un mensaje de validación.
7. **Dado** un administrador que guarda varios cambios de la matriz, **cuando** alguno de ellos no es válido, **entonces** el sistema no aplica parcialmente el conjunto y mantiene la configuración anterior.

---

### Historia 4 — Garantizar la no retroactividad de los plazos (Prioridad: P1)

Como responsable de la organización, quiero que los cambios de plazos solo afecten a tickets nuevos, para que el histórico y los tickets ya cerrados conserven las reglas con las que fueron atendidos.

**Por qué esta prioridad**: es la garantía explícita de la historia y la condición que hace fiable la configuración y la medición de SLA.

**Prueba independiente**: se crea un ticket, se calcula su límite, se modifica la regla aplicable y se comprueba que el límite y el resultado de SLA del ticket no cambian; después se crea otro ticket y se comprueba que sí usa la nueva regla.

**Escenarios de aceptación**:

1. **Dado** un ticket cerrado, **cuando** el administrador modifica el plazo que se le aplicó, **entonces** su límite de SLA, su resultado y su información histórica permanecen exactamente iguales.
2. **Dado** un ticket abierto, **cuando** el administrador modifica la regla que se le aplicó en su creación, **entonces** el ticket mantiene el límite fijado al crearse.
3. **Dado** un ticket creado después de un cambio de plazos, **cuando** se consulta su configuración aplicada en la respuesta del ticket o en el histórico administrativo, **entonces** muestra la nueva versión vigente en el momento de su creación.
4. **Dado** un cambio de plazos confirmado, **cuando** se consultan los tickets creados antes del cambio desde la línea base `v1`, **entonces** todos conservan la versión de configuración anterior. Los tickets anteriores a la línea base conservan su plazo y nivel, pero pueden no tener una versión de configuración fiable.
5. **Dado** un ticket con una categoría o prioridad posteriormente desactivada, **cuando** se consulta su detalle o su histórico, **entonces** la categoría y la prioridad siguen mostrándose correctamente y el plazo aplicado no cambia.
6. **Dado** un cálculo histórico basado en el SLA de tickets de un periodo pasado, **cuando** se recalcula tras un cambio de plazos, **entonces** los resultados de ese periodo no varían.
7. **Dado** un ticket existente, **cuando** el administrador cambia el nivel numérico de su prioridad, **entonces** el ticket conserva su nivel de urgencia original y no cambia de posición en la cola ni en los cálculos históricos.

---

### Historia 5 — Consultar el histórico de cambios de configuración (Prioridad: P2)

Como administrador, quiero consultar quién cambió cada categoría, prioridad o plazo y con qué valores, para poder explicar y revisar la configuración aplicada en cada momento.

**Por qué esta prioridad**: aporta trazabilidad y confianza, pero no bloquea la configuración ni la creación de tickets.

**Prueba independiente**: el administrador realiza varios cambios y comprueba que el histórico muestra autor, fecha, entidad, valores anteriores, valores nuevos y versión resultante, sin posibilidad de editar entradas pasadas.

**Escenarios de aceptación**:

1. **Dado** cualquier cambio de configuración confirmado, **cuando** el administrador consulta el histórico, **entonces** ve el autor, la fecha y hora, la entidad afectada, la acción, los valores anteriores y los nuevos.
2. **Dado** una versión de configuración pasada, **cuando** el administrador intenta modificarla o eliminarla, **entonces** el sistema lo impide; cualquier corrección se realiza creando una nueva versión.
3. **Dado** un rango de fechas, **cuando** el administrador filtra el histórico, **entonces** obtiene los cambios realizados en ese periodo.
4. **Dado** un ticket histórico, **cuando** el administrador consulta la versión de configuración que se le aplicó, **entonces** puede localizar en el histórico las reglas que estaban vigentes en su fecha de creación.
5. **Dado** un supervisor o cualquier otro perfil distinto de administración, **cuando** intenta consultar la configuración o su histórico, **entonces** el sistema rechaza el acceso y no expone ningún dato de configuración.
6. **Dado** un administrador que intenta fechar un cambio en el pasado o programarlo para una fecha futura, **cuando** confirma la operación, **entonces** el sistema lo rechaza y mantiene la configuración vigente sin cambios.

---

### Casos límite

- Cambiar el plazo base de una prioridad cuando existen tickets abiertos y cerrados: solo los tickets creados después usan el nuevo plazo.
- Cambiar el nivel numérico de una prioridad: los tickets existentes conservan el nivel de urgencia con el que se crearon y mantienen su posición en la cola y en los cálculos históricos.
- Retirar una regla de la matriz: los tickets existentes de esa combinación mantienen el plazo ya fijado; los nuevos usan el plazo base.
- Desactivar una categoría o prioridad con tickets: se permite la desactivación, nunca la eliminación, y el histórico sigue siendo consultable.
- Intentar eliminar una categoría o prioridad referenciada por una regla de la matriz: el sistema lo impide y propone desactivarla o retirar antes la regla.
- Nombres duplicados con diferencias de mayúsculas, minúsculas o espacios: se consideran el mismo nombre.
- Plazos con decimales: se admiten siempre que sean positivos y representen horas con precisión de minutos.
- Dos administradores modificando la misma regla al mismo tiempo: se aplica bloqueo optimista; la edición basada en una versión ya superada se rechaza con un aviso de conflicto, no se guarda parcialmente y el administrador debe recargar y reintentar.
- Desactivar la última categoría o prioridad activa: se impide para que no queden tickets sin opciones de clasificación.
- Ticket creado justo en el instante de un cambio de configuración: se aplica una única versión, determinada por el instante de creación, sin mezclar valores antiguos y nuevos.

## Requisitos

### Requisitos Funcionales

- **HU08-RF-001**: El sistema MUST permitir únicamente al perfil de administración consultar o modificar la configuración administrativa: catálogos completos, incluidas entidades inactivas y de sistema, reglas de plazo e histórico. El catálogo operativo de categorías y prioridades activas necesario para crear tickets sigue disponible para los perfiles autenticados.
- **HU08-RF-002**: El sistema MUST rechazar cualquier intento de consulta o modificación de la configuración administrativa o de su histórico realizado por un perfil distinto de administración, sin bloquear el catálogo operativo de creación de tickets.
- **HU08-RF-003**: El sistema MUST permitir crear y editar categorías con nombre obligatorio y descripción opcional.
- **HU08-RF-004**: El sistema MUST validar que el nombre de una categoría sea único, ignorando mayúsculas, minúsculas y espacios sobrantes.
- **HU08-RF-005**: El sistema MUST permitir desactivar y reactivar categorías sin eliminar su información histórica.
- **HU08-RF-006**: El sistema MUST impedir la eliminación definitiva de una categoría o prioridad que esté asociada a tickets o a reglas de plazo.
- **HU08-RF-007**: El sistema MUST permitir crear y editar prioridades con nombre, nivel numérico, color y plazo base de atención.
- **HU08-RF-008**: El sistema MUST validar que el nivel de prioridad esté dentro del rango 1–4 y sea único entre prioridades no-sistema activas. Las prioridades inactivas no reservan nivel y la prioridad de sistema de reserva queda excluida.
- **HU08-RF-009**: El sistema MUST validar que el plazo base de una prioridad sea un número positivo expresado en horas.
- **HU08-RF-010**: El sistema MUST permitir desactivar y reactivar prioridades sin eliminar su información histórica.
- **HU08-RF-011**: El sistema MUST impedir que se desactive la última categoría activa o la última prioridad activa disponible para nuevos tickets.
- **HU08-RF-012**: El sistema MUST mantener una categoría por defecto y una prioridad por defecto entre las activas, y MUST exigir designar un reemplazo antes de desactivar la vigente.
- **HU08-RF-013**: El sistema MUST permitir definir un plazo de atención para cada combinación de categoría y prioridad.
- **HU08-RF-014**: El sistema MUST validar que el plazo de una regla de matriz sea un número positivo expresado en horas.
- **HU08-RF-015**: El sistema MUST impedir que existan dos reglas vigentes simultáneas para la misma combinación de categoría y prioridad.
- **HU08-RF-016**: El sistema MUST aplicar, para cada nuevo ticket, el plazo de la regla de matriz de su combinación categoría × prioridad y, si no existe, el plazo base de su prioridad, contando las horas de forma continua desde la creación.
- **HU08-RF-017**: El sistema MUST fijar y conservar de forma inmutable, en el momento de creación de cada ticket, el plazo aplicado, el límite de atención resultante, el nivel de urgencia de la prioridad y la versión de configuración utilizada. La respuesta del ticket MUST exponer la versión aplicada y los valores congelados para su consulta.
- **HU08-RF-018**: El sistema MUST garantizar que ningún cambio posterior de categorías, prioridades o reglas de plazo modifique el plazo aplicado, el límite de atención, el nivel de urgencia, el orden en la cola ni el resultado de SLA de un ticket ya creado, esté abierto o cerrado.
- **HU08-RF-019**: El sistema MUST aplicar los cambios de configuración únicamente a los tickets creados después de su confirmación.
- **HU08-RF-020**: El sistema MUST permitir retirar una regla de la matriz conservando su histórico, de modo que los nuevos tickets de esa combinación usen el plazo base de la prioridad.
- **HU08-RF-021**: El sistema MUST impedir que una categoría o prioridad desactivada se ofrezca en el catálogo operativo para clasificar nuevos tickets, manteniéndola visible en los tickets que ya la tenían asociada.
- **HU08-RF-022**: El sistema MUST registrar cada cambio de configuración de forma append-only con identificador de versión, autor, fecha y hora, entidad afectada, acción, valores anteriores y valores nuevos.
- **HU08-RF-023**: El sistema MUST impedir la modificación o eliminación de versiones de configuración pasadas; cualquier corrección MUST realizarse mediante una nueva versión.
- **HU08-RF-024**: El sistema MUST aplicar cada cambio de configuración de forma atómica: o se guardan todos sus efectos, o no se guarda ninguno.
- **HU08-RF-025**: El sistema MUST resolver conflictos de edición concurrente sobre la misma entidad mediante bloqueo optimista, rechazando con un error de conflicto toda edición basada en una versión ya superada y sin sobrescribir silenciosamente cambios confirmados.
- **HU08-RF-026**: El sistema MUST mostrar los plazos, fechas y horas en español de España y en la zona horaria `Europe/Madrid`, conservando internamente los instantes en UTC.
- **HU08-RF-027**: El sistema MUST exponer los errores de validación y de permisos con mensajes comprensibles en español y códigos estables, sin filtrar detalles internos.
- **HU08-RF-028**: El sistema MUST aplicar todo cambio de configuración en el instante de su confirmación y MUST impedir fecharlo en el pasado o programarlo para una fecha futura.

### Entidades Clave

- **Categoría**: identifica un tipo de incidencia; tiene nombre único, descripción, estado activo/inactivo y marca de categoría por defecto.
- **Prioridad**: identifica el grado de urgencia; tiene nombre único, nivel numérico único entre prioridades no-sistema activas, color, plazo base de atención, estado activo/inactivo y marca de prioridad por defecto.
- **Regla de plazo (matriz SLA)**: fija el plazo de atención para una combinación concreta de categoría y prioridad; tiene identificador de versión, fecha desde la que aplica y estado de vigencia.
- **Versión de configuración**: agrupa los valores vigentes en un momento dado y permite identificar exactamente las reglas que se aplicaron a un ticket.
- **Ticket**: conserva de forma permanente el plazo aplicado, el límite de atención, el nivel de urgencia de la prioridad, la categoría y la prioridad utilizadas y la versión de configuración vigente en su creación, con independencia de cambios posteriores.
- **Registro de auditoría de configuración**: recoge de forma inmutable cada alta, edición, desactivación, reactivación, retirada o cambio de plazo, con autor, fecha y valores anteriores y nuevos.

## Criterios de Éxito

### Resultados Medibles

- **HU08-SC-001**: El 100 % de los tickets cerrados conserva exactamente el mismo límite y resultado de SLA después de cualquier cambio de configuración posterior.
- **HU08-SC-002**: El 100 % de los tickets abiertos conserva el límite fijado en su creación tras un cambio de plazos.
- **HU08-SC-003**: El 100 % de los tickets creados después de un cambio utilizan la nueva versión de configuración vigente.
- **HU08-SC-004**: El 100 % de los intentos de eliminar categorías o prioridades en uso son rechazados y se ofrece la alternativa de desactivación.
- **HU08-SC-005**: El 100 % de los cambios de configuración quedan registrados con autor, fecha y valores anteriores y nuevos.
- **HU08-SC-006**: Un administrador puede crear una categoría o prioridad en menos de 2 minutos y actualizar una regla de la matriz en menos de 3 minutos, contando desde que abre el formulario hasta que recibe confirmación.
- **HU08-SC-007**: Al menos el 95 % de las operaciones de configuración válidas se completan en el primer intento sin errores de validación inesperados.
- **HU08-SC-008**: Cero tickets históricos modificados por cambios de configuración en las pruebas de regresión de la historia.
- **HU08-SC-009**: El 100 % de los tickets existentes conserva su nivel de urgencia y su posición relativa en la cola tras cambiar el nivel numérico de una prioridad.
- **HU08-SC-010**: El 100 % de las ediciones concurrentes basadas en una versión superada se rechazan con un aviso de conflicto y no producen pérdida silenciosa de cambios.

## Supuestos

- Cada combinación categoría × prioridad tiene un único plazo de atención; esta historia no contempla plazos separados de primera respuesta y de resolución.
- Los plazos se expresan en horas y se cuentan de forma continua desde la creación del ticket; la exclusión de festivos y horarios laborales queda fuera del alcance de esta versión.
- La no retroactividad se aplica a todos los tickets, no solo a los cerrados: cada ticket fija su configuración en el instante de creación, tal como establece la especificación general.
- Los cambios de configuración son efectivos desde su confirmación y no pueden fecharse en el pasado ni programarse para una fecha futura.
- El catálogo inicial mantiene cuatro prioridades no-sistema (Crítica, Alta, Media y Baja) que ocupan los niveles 1–4, siendo 1 el más crítico. No se añaden nuevos niveles en esta historia: para crear otra prioridad hay que liberar un nivel desactivando o eliminando una prioridad no referenciada. La prioridad de sistema `Sin clasificar` comparte el nivel 4, no reserva nivel y no aparece en el catálogo operativo.
- Renombrar una categoría o prioridad no altera el plazo aplicado ni la versión de configuración de los tickets existentes; los tickets históricos conservan la referencia a la entidad.
- El nivel de urgencia de la prioridad se congela por ticket en el momento de su creación; los cambios de nivel solo afectan a tickets nuevos.
- Los perfiles de usuario, técnico, supervisor y administrador ya existen y la autenticación se reutiliza del sistema actual.
- La interfaz de configuración se ofrece en español de España y cumple los requisitos de accesibilidad del proyecto.
- No se contempla la importación masiva de configuración ni la programación de cambios de plazo para una fecha futura; los cambios se aplican al confirmarse.
- No se implementa un módulo de informes en esta historia; las garantías de no retroactividad se aplican a la cola, los listados y cualquier cálculo derivado del snapshot del ticket.
