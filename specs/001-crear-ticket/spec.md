# Especificación de Funcionalidad: Creación de tickets de incidencia

**Rama de la funcionalidad**: `hu-01-crear-ticket`

**Creada**: 2026-10-29

**Estado**: Borrador

**Entrada**: Descripción del usuario: "Sistema de gestión de incidencias de soporte técnico (mesa de ayuda). Esta primera funcionalidad es la creación de tickets de incidencia. Un empleado de la organización puede registrar una incidencia describiendo su problema con un título y una descripción, y adjuntando opcionalmente una o más capturas de pantalla. Al enviarla recibe un número de ticket único que le sirve como referencia para su seguimiento posterior. El sistema sugiere automáticamente una categoría y una prioridad iniciales a partir del texto descrito; ambas deben pertenecer a las configuradas por la administración. Si no se puede determinar una sugerencia, el ticket se crea igualmente con valores por defecto, sin bloquear al usuario. El ticket registra quién lo creó y cuándo, nace en un estado inicial definido, y su creación queda registrada como primer evento de su historial. El sistema debe validar tipo y tamaño de los adjuntos y evitar tickets duplicados por doble envío o reintentos de red."

## Clarifications

### Session 2026-10-29

- Q: ¿Qué debe considerar el sistema como un envío duplicado que no genere un ticket nuevo? → A: Mismo creador y contenido siempre, sin límite de tiempo.
- Q: Si falla la subida de uno de varios adjuntos durante el envío, ¿qué debe hacer el sistema con el ticket? → A: Todo o nada: no crear el ticket hasta que todos los adjuntos suban, conservando los datos y permitiendo reintentar.
- Q: ¿Qué formato debe tener el número único de ticket que se muestra al empleado? → A: Secuencial con prefijo, por ejemplo TK-000001.
- Q: ¿Cómo debe elegir el sistema la categoría y la prioridad por defecto cuando no hay sugerencia? → A: Defecto configurado con respaldo: valor por defecto activo, si no existe el primer valor activo, y si no hay ninguno, "Sin clasificar".
- Q: ¿Qué margen tiene el empleado para cambiar la categoría y la prioridad sugeridas antes de enviar el ticket? → A: La prioridad es editable; la categoría sugerida queda fija y no editable.

## Escenarios de Usuario y Pruebas *(obligatorio)*

### Historia de Usuario 1 - Registrar una incidencia y obtener número de referencia (Prioridad: P1)

Un empleado de la organización describe su problema con un título y una descripción, envía el ticket y recibe un número único que podrá usar como referencia en el seguimiento posterior. El ticket queda registrado con el empleado como creador, la fecha y hora de creación y un estado inicial definido.

**Por qué esta prioridad**: Es el núcleo de la funcionalidad. Sin la creación y el número de referencia no existe ningún ticket que atender ni que consultar después.

**Prueba independiente**: Se puede probar por completo iniciando sesión como empleado, rellenando título y descripción, enviando el ticket y comprobando que se muestra un número único y que el ticket aparece registrado con su creador, fecha y estado inicial.

**Escenarios de aceptación**:

1. **Dado** un empleado autenticado, **cuando** introduce un título y una descripción válidos y envía el ticket, **entonces** el sistema crea el ticket, le asigna un número único y se lo muestra como referencia.
2. **Dado** un ticket recién creado, **cuando** se consulta su información, **entonces** muestra el empleado creador, la fecha y hora de creación y el estado inicial definido.
3. **Dado** un ticket recién creado, **cuando** se revisa su historial, **entonces** existe una primera entrada que registra su creación con fecha y hora.
4. **Dado** un empleado que intenta enviar un ticket sin título o sin descripción, **cuando** confirma el envío, **entonces** el sistema no crea el ticket e indica qué campo falta.

---

### Historia de Usuario 2 - Adjuntar capturas de pantalla (Prioridad: P2)

Un empleado puede añadir una o varias capturas de pantalla al ticket para ilustrar la incidencia. El sistema valida que los archivos sean del tipo permitido y no superen el tamaño máximo, y descarta los que no cumplan sin perder los datos ya introducidos.

**Por qué esta prioridad**: Las capturas aceleran el diagnóstico, pero el ticket sigue siendo útil sin ellas; por eso complementa a la historia principal sin bloquearla.

**Prueba independiente**: Se puede probar creando un ticket con varios adjuntos válidos y comprobando que quedan asociados, y repitiendo el envío con un archivo de tipo o tamaño no permitido y comprobando que se rechaza con un mensaje claro.

**Escenarios de aceptación**:

1. **Dado** un empleado rellenando un ticket, **cuando** adjunta una o varias imágenes de tipo y tamaño permitidos, **entonces** el sistema las acepta y las muestra asociadas al ticket.
2. **Dado** un empleado que adjunta un archivo de tipo no permitido, **cuando** intenta añadirlo, **entonces** el sistema lo rechaza e indica los tipos admitidos.
3. **Dado** un empleado que adjunta un archivo que supera el tamaño máximo, **cuando** intenta añadirlo, **entonces** el sistema lo rechaza e indica el límite permitido.
4. **Dado** un empleado con datos ya introducidos, **cuando** un adjunto es rechazado, **entonces** el título, la descripción y los demás adjuntos se conservan.
5. **Dado** un empleado que crea un ticket sin adjuntos, **cuando** lo envía, **entonces** el ticket se crea correctamente.

---

### Historia de Usuario 3 - Recibir sugerencias de categoría y prioridad (Prioridad: P3)

Al describir la incidencia, el sistema propone una categoría y una prioridad iniciales a partir del texto introducido. Las sugerencias solo pueden ser valores activos configurados por la administración. La categoría propuesta queda fija, mientras que el empleado puede cambiar la prioridad antes de confirmar. Si no hay sugerencia posible, el ticket se crea igualmente con valores por defecto.

**Por qué esta prioridad**: Mejora la clasificación y la rapidez de atención, pero la creación del ticket no debe depender de que exista una sugerencia.

**Prueba independiente**: Se puede probar escribiendo descripciones con términos reconocibles y comprobando que se propone una categoría y una prioridad activas, y escribiendo una descripción neutra y comprobando que el ticket se crea con los valores por defecto sin bloquearse.

**Escenarios de aceptación**:

1. **Dado** un empleado que escribe una descripción con términos reconocibles, **cuando** el sistema analiza el texto, **entonces** propone una categoría y una prioridad que están activas en la configuración de la administración.
2. **Dado** un empleado que recibe una sugerencia, **cuando** envía el ticket, **entonces** la categoría sugerida se aplica sin posibilidad de cambio y la prioridad se aplica con el valor que el empleado haya elegido.
3. **Dado** un empleado cuya descripción no permite determinar una sugerencia, **cuando** envía el ticket, **entonces** el sistema crea el ticket con los valores por defecto y sin bloquear el envío.
4. **Dado** que la categoría o la prioridad sugerida ha sido desactivada por la administración, **cuando** el sistema genera la sugerencia, **entonces** no la propone y recurre al valor por defecto activo, o en su defecto al primer valor activo, o a "Sin clasificar" si no hay ninguno activo.
5. **Dado** un empleado que no modifica las sugerencias, **cuando** envía el ticket, **entonces** el ticket se crea con la categoría y prioridad sugeridas.

---

### Casos Límite

- **Descripción muy corta**: un texto por debajo del mínimo debe impedir el envío con un mensaje que indique la longitud mínima.
- **Descripción muy larga**: un texto por encima del máximo debe impedir el envío con un mensaje que indique la longitud máxima, sin truncar silenciosamente el contenido.
- **Título muy corto o muy largo**: se aplican límites equivalentes y el sistema informa del rango admitido.
- **Varios adjuntos**: se admiten varios archivos válidos hasta el máximo definido; al superar el número máximo se rechazan los adicionales con un mensaje claro.
- **Fallo de subida a mitad**: si un adjunto no termina de subirse, el ticket no se crea; se informa del fallo y se permite reintentar conservando el título, la descripción y todos los adjuntos seleccionados. El ticket solo se crea cuando todos los adjuntos se han subido correctamente.
- **Pérdida de conexión durante el envío**: el empleado recibe un aviso de que el ticket no se ha confirmado y puede reintentar sin generar un ticket duplicado.
- **Categoría sugerida desactivada**: la sugerencia nunca apunta a una categoría o prioridad inactiva; se usa la categoría o prioridad por defecto activa, o en su defecto el primer valor activo, o "Sin clasificar" si no hay ninguno activo.
- **Caracteres especiales y código pegado**: el título, la descripción y el texto de la sugerencia se conservan y muestran tal cual, sin que los caracteres especiales ni el código pegado rompan el guardado ni la visualización.
- **Doble envío, reintento de red o reenvío posterior**: cualquier intento del mismo empleado con el mismo título y la misma descripción produce un único ticket, sin importar cuánto tiempo haya pasado; el intento posterior devuelve la referencia ya creada en lugar de duplicarla.

## Requisitos *(obligatorio)*

### Requisitos Funcionales

- **RF-001**: El sistema DEBE permitir a un empleado autenticado crear un ticket indicando un título y una descripción.
- **RF-002**: El sistema DEBE validar que el título y la descripción están presentes y dentro de las longitudes mínima y máxima definidas.
- **RF-003**: El sistema DEBE permitir adjuntar cero, uno o varios archivos de imagen al ticket.
- **RF-004**: El sistema DEBE validar el tipo de cada adjunto contra los tipos de imagen permitidos e informar de los tipos admitidos cuando lo rechace.
- **RF-005**: El sistema DEBE validar el tamaño de cada adjunto y el número máximo de adjuntos por ticket, informando del límite incumplido.
- **RF-006**: El sistema DEBE generar un número de ticket único e irrepetible con formato secuencial y prefijo (por ejemplo, TK-000001), y mostrarlo al empleado como referencia.
- **RF-007**: El sistema DEBE registrar en el ticket el empleado creador y la fecha y hora de creación.
- **RF-008**: El sistema DEBE asignar al ticket un estado inicial definido en el momento de su creación.
- **RF-009**: El sistema DEBE registrar la creación del ticket como primer evento de su historial, con fecha y hora.
- **RF-010**: El sistema DEBE sugerir una categoría inicial a partir del texto del título y la descripción.
- **RF-011**: El sistema DEBE sugerir una prioridad inicial a partir del texto del título y la descripción.
- **RF-012**: El sistema DEBE limitar las sugerencias a categorías y prioridades activas configuradas por la administración.
- **RF-013**: El sistema DEBE aplicar la categoría sugerida sin permitir su modificación y DEBE permitir al empleado cambiar la prioridad antes de confirmar el envío.
- **RF-014**: El sistema DEBE crear el ticket sin bloquear al empleado cuando no sea posible determinar una sugerencia, usando la categoría y prioridad por defecto activas; si no existe valor por defecto, el primer valor activo; si no hay ningún valor activo, "Sin clasificar".
- **RF-015**: El sistema DEBE evitar la creación de tickets duplicados cuando el mismo empleado envía el mismo título y la misma descripción, sin límite de tiempo, devolviendo la referencia del ticket ya creado.
- **RF-016**: El sistema DEBE conservar los datos introducidos cuando falle la subida de un adjunto o se pierda la conexión durante el envío, permitiendo reintentar.
- **RF-017**: El sistema NO DEBE crear el ticket hasta que todos los adjuntos seleccionados se hayan subido correctamente, ni dejar tickets en estado parcial; si falla alguno, conserva los datos introducidos y permite reintentar.
- **RF-018**: El sistema DEBE conservar y mostrar correctamente caracteres especiales y código pegado en el título y la descripción.

### Entidades Clave

- **Ticket**: representa la incidencia registrada. Incluye número único, título, descripción, estado, categoría, prioridad, empleado creador, fecha y hora de creación, y adjuntos asociados.
- **Adjunto**: representa una captura de pantalla asociada al ticket. Incluye nombre de archivo, tipo, tamaño y referencia al ticket.
- **Evento de historial**: representa un cambio o hecho relevante del ticket. Para esta funcionalidad, el evento de creación con fecha, hora y autor.
- **Empleado creador**: persona autenticada que registra la incidencia; el sistema conserva su identidad como responsable de la creación.
- **Categoría**: clasificación configurada por la administración, con un estado activo o inactivo, que puede ser sugerida y se aplica al ticket sin edición por parte del empleado.
- **Prioridad**: nivel de urgencia configurado por la administración, con un estado activo o inactivo, que puede ser sugerido y modificado por el empleado antes de enviar el ticket.

## Criterios de Éxito *(obligatorio)*

### Resultados Medibles

- **CE-001**: Un empleado puede crear un ticket completo en menos de 60 segundos desde que empieza a rellenarlo.
- **CE-002**: El 100% de los tickets creados reciben un número de referencia único y visible para el empleado.
- **CE-003**: El 100% de los tickets creados registran creador, fecha y hora, estado inicial y primer evento de historial.
- **CE-004**: Al menos el 70% de las prioridades sugeridas son aceptadas por el empleado sin cambios.
- **CE-005**: El 100% de los intentos con adjuntos de tipo o tamaño no permitido son rechazados con un mensaje que explica el motivo.
- **CE-006**: El 100% de los envíos repetidos del mismo empleado con idéntico título y descripción, incluidos dobles envíos y reintentos de red, producen un único ticket y devuelven la misma referencia.
- **CE-007**: El 100% de los tickets creados sin sugerencia disponible se crean correctamente con los valores por defecto o, en su defecto, con "Sin clasificar", sin bloqueo.
- **CE-008**: Ninguna pérdida de conexión ni fallo de subida deja tickets parciales o duplicados; el 100% de los fallos de subida conserva los datos y permite reintentar sin crear el ticket.

## Supuestos

- El empleado está autenticado antes de crear el ticket; el inicio de sesión no forma parte de esta funcionalidad.
- Existe una configuración de categorías y prioridades gestionada por la administración, aunque su pantalla de configuración queda fuera de esta funcionalidad.
- Se consideran imágenes permitidas PNG, JPG/JPEG y GIF.
- El tamaño máximo por adjunto es de 5 MB y el máximo es de 5 adjuntos por ticket, salvo que la organización configure otro valor.
- El título admite entre 5 y 120 caracteres y la descripción entre 20 y 5000 caracteres.
- Existe una categoría y una prioridad por defecto activas configuradas por la administración para cuando no haya sugerencia; si no existen, se usa el primer valor activo y, si no hay ninguno, "Sin clasificar".
- La sugerencia se basa en la coincidencia de términos del título y la descripción con las categorías y prioridades configuradas, sin modelos de aprendizaje automático. La categoría sugerida no es editable por el empleado; la prioridad sí.
- La detección de duplicados se basa en el mismo empleado, mismo título y misma descripción, sin límite de tiempo: un reenvío posterior del mismo contenido devuelve el ticket existente.
- El número de ticket es único, secuencial, no reutilizable y con prefijo (por ejemplo, TK-000001).
- El estado inicial del ticket es un valor definido por la organización; para esta funcionalidad se asume "Abierto".
- Los adjuntos se conservan asociados al ticket tras la creación, aunque su visualización detallada pertenece a funcionalidades posteriores.
- Todo el producto está en español de España.

## Fuera de Alcance

- Seguimiento y línea temporal del ticket más allá del evento de creación.
- Respuesta a peticiones de información del técnico.
- Cola de trabajo técnica.
- Resolución, cierre, reasignación y escalado de tickets.
- Panel de SLA y cálculo de plazos de atención.
- Configuración de categorías, prioridades y plazos.
- Notificaciones al técnico o al empleado.
- Autenticación y gestión de usuarios.
- Decisiones de tecnología, arquitectura o implementación.
