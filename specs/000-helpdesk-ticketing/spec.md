# Especificación: Sistema de Mesa de Ayuda (Helpdesk Ticketing)

## Resumen

Sistema web para la gestión de incidencias mediante tickets que permite a empleados reportar problemas, a técnicos resolverlos y a supervisores/administradores monitorizar y configurar el proceso. El sistema cubre el ciclo de vida completo: creación, seguimiento, resolución, escalado y reporte.

## Actores

- **Usuario/Empleado**: Crea tickets, consulta estado, responde peticiones de información
- **Técnico**: Gestiona cola de trabajo, resuelve tickets, reasigna/escalda
- **Supervisor**: Monitoriza cumplimiento de SLA, identifica retrasos
- **Administrador**: Configura categorías, prioridades y plazos (SLA)

## Historias de Usuario

### HU-01: Crear ticket con sugerencia automática
**Como** usuario, **quiero** crear un ticket describiendo mi incidencia, adjuntar capturas de pantalla y recibir un número de referencia, **para que** mi problema quede registrado y pueda ser atendido.

**Criterios de aceptación:**
- El usuario puede escribir una descripción libre de la incidencia
- El usuario puede adjuntar uno o varios archivos de imagen (capturas de pantalla)
- Al enviar, el sistema genera y muestra un número de ticket único
- El sistema sugiere automáticamente una categoría basada en el texto de la descripción
- El sistema sugiere automáticamente una prioridad inicial basada en el texto de la descripción
- El usuario puede aceptar o modificar las sugerencias antes de confirmar

### HU-02: Consultar estado e historial del ticket
**Como** usuario, **quiero** consultar el estado actual de mi ticket y ver su historial completo con línea temporal, **para que** sepa en qué fase está sin tener que preguntar.

**Criterios de aceptación:**
- El usuario ve el estado actual del ticket (ej: Abierto, En progreso, Pendiente de usuario, Resuelto, Cerrado)
- El usuario accede a una línea temporal cronológica con todos los cambios de estado
- La línea temporal muestra cada comentario añadido por el técnico
- Cada entrada muestra fecha, hora, autor y tipo de cambio

### HU-03: Responder a petición de información del técnico
**Como** usuario, **quiero** responder a una petición concreta de información del técnico directamente desde el ticket, **para que** el proceso continúe y quede claro que la pelota vuelve al equipo técnico.

**Criterios de aceptación:**
- El técnico puede marcar un ticket como "Pendiente de usuario" solicitando información específica
- El usuario recibe notificación de que se requiere su respuesta
- El usuario responde desde la vista del ticket
- Al responder, el estado cambia automáticamente a "En progreso" (o equivalente)
- La respuesta queda registrada en la línea temporal

### HU-04: Ver cola de trabajo priorizada
**Como** técnico, **quiero** ver mis tickets asignados ordenados por urgencia y proximidad al incumplimiento del plazo, **para que** atienda primero lo más crítico.

**Criterios de aceptación:**
- El técnico ve solo los tickets que tiene asignados
- La lista muestra: número de ticket, título/resumen, categoría, prioridad, tiempo restante hasta límite SLA
- El orden por defecto prioriza: mayor prioridad primero, y dentro de misma prioridad, menor tiempo restante primero
- Se destaca visualmente (color, icono) los tickets próximos a incumplir su plazo
- El técnico puede filtrar por estado y prioridad

### HU-05: Cambiar estado y documentar resolución
**Como** técnico, **quiero** cambiar el estado del ticket y dejar por escrito cómo se resolvió, **para que** quede documentado como referencia futura.

**Criterios de aceptación:**
- El técnico puede cambiar el estado entre valores definidos (ej: Abierto → En progreso → Resuelto → Cerrado)
- Al mover a "Resuelto", el sistema requiere obligatoriamente una descripción de la solución
- La solución queda guardada y visible en la línea temporal
- El técnico puede añadir comentarios internos en cualquier momento

### HU-06: Reasignar o escalar ticket
**Como** técnico, **quiero** reasignar el ticket a otro técnico o escalarlo a un nivel superior, **para que** la persona adecuada se haga cargo y sea notificada de inmediato.

**Criterios de aceptación:**
- El técnico puede seleccionar otro técnico de la lista del equipo para reasignar
- El técnico puede escalar a un nivel superior (ej: "Nivel 2", "Especialista")
- Al reasignar/escalar, el nuevo responsable recibe notificación inmediata
- El cambio de responsable queda registrado en la línea temporal con autor y motivo
- El ticket pasa a la cola de trabajo del nuevo responsable

### HU-07: Dashboard de cumplimiento de SLA
**Como** supervisor, **quiero** ver de forma agregada el cumplimiento de tiempos de respuesta según prioridad y categoría, **para que** identifique retrasos y responsables de un vistazo.

**Criterios de aceptación:**
- Vista de dashboard con métricas por prioridad (Crítica, Alta, Media, Baja) y por categoría
- Para cada combinación: % de tickets atendidos dentro de plazo, tiempo medio de respuesta, tickets vencidos
- Lista de técnicos con tickets vencidos acumulados, ordenados por volumen
- Filtros por rango de fechas, categoría, prioridad
- Indicadores visuales (semáforo: verde/ámbar/rojo) por umbrales de cumplimiento

### HU-08: Configuración de categorías, prioridades y plazos (SLA)
**Como** administrador, **quiero** configurar las categorías, prioridades y sus plazos de atención asociados, **para que** el sistema refleje las reglas de la organización y los cambios no afecten retroactivamente a tickets ya cerrados.

**Criterios de aceptación:**
- CRUD de categorías (nombre, descripción, activa/inactiva)
- CRUD de prioridades (nombre, nivel numérico, color, plazo de respuesta en horas)
- Asociación de plazos por combinación categoría × prioridad (matriz SLA)
- Al modificar plazos, los tickets ya cerrados conservan los plazos que tenían al crearse
- Los tickets abiertos usan los plazos vigentes en su fecha de creación
- Validación: no se pueden borrar categorías/prioridades con tickets asociados (solo desactivar)

## Requisitos Funcionales

### RF-01: Gestión de tickets
- RF-01.1: Crear ticket con descripción, adjuntos, categoría y prioridad
- RF-01.2: Generar número de ticket único secuencial
- RF-01.3: Sugerir categoría y prioridad automáticamente (basado en palabras clave de la descripción)
- RF-01.4: Listar tickets con filtros (estado, prioridad, categoría, asignado, fechas)
- RF-01.5: Ver detalle de ticket con línea temporal completa

### RF-02: Flujo de estados
- RF-02.1: Estados definidos: Abierto, En progreso, Pendiente de usuario, Resuelto, Cerrado
- RF-02.2: Transiciones válidas entre estados (no se puede ir de Cerrado a Abierto directamente)
- RF-02.3: Cambio automático a "En progreso" cuando usuario responde a "Pendiente de usuario"
- RF-02.4: Requerir descripción de solución al pasar a "Resuelto"

### RF-03: Asignación y escalado
- RF-03.1: Asignar ticket a técnico (manual o automático por categoría)
- RF-03.2: Reasignar a otro técnico del mismo nivel
- RF-03.3: Escalar a nivel superior
- RF-03.4: Notificación inmediata al nuevo responsable (en app y email)
- RF-03.5: Registro en línea temporal de cada cambio de responsable

### RF-04: Cola de trabajo del técnico
- RF-04.1: Vista personalizada con tickets asignados al técnico logueado
- RF-04.2: Ordenación por prioridad (desc) + tiempo restante SLA (asc)
- RF-04.3: Indicador visual de urgencia (próximo a vencer, vencido)
- RF-04.4: Filtros por estado y prioridad

### RF-05: Adjuntos
- RF-05.1: Subir imágenes (PNG, JPG, GIF) al crear ticket o comentar
- RF-05.2: Límite de tamaño por archivo (ej: 5 MB) y total por ticket
- RF-05.3: Visualización inline de imágenes en ticket y línea temporal

### RF-06: Dashboard de supervisión
- RF-06.1: Métricas agregadas por prioridad y categoría
- RF-06.2: % cumplimiento SLA, tiempo medio respuesta, tickets vencidos
- RF-06.3: Ranking de técnicos con tickets vencidos
- RF-06.4: Filtros temporales y por dimensión (categoría, prioridad, técnico)
- RF-06.5: Semáforo visual por umbrales configurables

### RF-07: Administración de catálogos y SLA
- RF-07.1: CRUD Categorías
- RF-07.2: CRUD Prioridades (con nivel numérico y plazo base en horas)
- RF-07.3: Matriz SLA: plazo por categoría × prioridad (sobrescribe plazo base de prioridad)
- RF-07.4: Versionado de SLA: cada ticket guarda la configuración vigente al crearse
- RF-07.5: Desactivar (no borrar) categorías/prioridades en uso

### RF-08: Notificaciones
- RF-08.1: Notificación en app (campana) para eventos clave
- RF-08.2: Email opcional para eventos críticos (asignación, escalado, SLA próximo a vencer)
- RF-08.3: Preferencias de notificación por usuario

## Requisitos No Funcionales

- **RNF-01**: Interfaz 100% en español de España
- **RNF-02**: Moneda en euros (si aplica en futuras extensiones)
- **RNF-03**: Accesibilidad WCAG 2.1 AA
- **RNF-04**: Responsive (funciona en desktop y tablet)
- **RNF-05**: Tiempo de carga de vistas principales < 2 segundos
- **RNF-06**: Disponibilidad 99.5% en horario laboral
- **RNF-07**: Sin claves ni secretos en código (configuración por variables de entorno)
- **RNF-08**: Solo datos imprescindibles del usuario (nombre, email, rol, equipo)
- **RNF-09**: Despliegue reproducible con Docker Compose. `docker compose up` DEBE levantar la aplicación y sus dependencias (PostgreSQL) sin pasos manuales previos, salvo disponer de Docker.
- **RNF-10**: Los datos de PostgreSQL DEBEN persistir en un volumen nombrado. `docker compose down` no DEBE borrarlos; solo una acción explícita (`docker compose down -v`) puede eliminarlos.
- **RNF-11**: Toda configuración sensible o dependiente del entorno (credenciales de base de datos, secreto JWT, emisor/audiencia, puertos y orígenes CORS) DEBE recibirse por variables de entorno. El repositorio solo incluye un `.env.example` sin secretos reales.
- **RNF-12**: Las imágenes DEBEN construirse en múltiples etapas, ejecutar el backend con un usuario sin privilegios y declarar healthchecks para que Compose espere a que cada servicio esté listo.
- **RNF-13**: Las migraciones de Alembic DEBEN aplicarse automáticamente al arrancar el backend, con reintentos mientras PostgreSQL termina de iniciarse, de modo que la base quede lista sin comandos manuales.

## Despliegue con contenedores

La aplicación se empaqueta en una única imagen multi-etapa con dos destinos construibles (`backend` y `frontend`) y se orquesta con `docker-compose.yml`:

| Servicio | Imagen / construcción | Responsabilidad | Persistencia |
|----------|-----------------------|-----------------|--------------|
| `db` | `postgres:16-alpine` | Base de datos relacional | Volumen `ticketing_db_data` |
| `backend` | Etapa `backend` del `Dockerfile` | FastAPI + Uvicorn + Alembic | Sin estado propio |
| `frontend` | Etapa `frontend` del `Dockerfile` | SPA Vue compilada + Nginx y proxy `/api` | Sin estado propio |

**Criterios de aceptación del despliegue**:

1. **Dado** un equipo con Docker y sin Python, Node ni PostgreSQL instalados, **cuando** se ejecuta `docker compose up`, **entonces** la aplicación queda disponible en `http://localhost:8080` y la API en `http://localhost:8000`, con el esquema de base de datos migrado.
2. **Dado** un arranque previo con datos, **cuando** se ejecuta `docker compose down` y después `docker compose up`, **entonces** los tickets y usuarios creados siguen existiendo.
3. **Dado** un cambio en `JWT_SECRET`, `FRONTEND_PORT`, `FRONTEND_ORIGINS` o en las credenciales de PostgreSQL (recreando el volumen si la base ya estaba inicializada), **cuando** se recrean los contenedores, **entonces** la configuración nueva se aplica sin modificar el código ni la imagen.
4. **Dado** un fallo temporal de PostgreSQL durante el arranque, **cuando** la base termina de iniciarse, **entonces** el backend aplica las migraciones y arranca sin intervención manual.
5. **Dado** el repositorio clonado, **cuando** se revisa el historial, **entonces** no contiene `.env`, contraseñas, secretos JWT ni el volumen de datos.

Los comandos concretos y las variables disponibles se documentan en el [`README.md`](../../README.md) de la raíz.

## Entidades Clave

- **Ticket**: id, número, título, descripción, estado, prioridad, categoría, creador, asignado, fecha_creación, fecha_límite_SLA, fecha_cierre, versión_SLA_aplicada
- **Usuario**: id, nombre, email, rol (usuario/técnico/supervisor/admin), equipo, activo
- **Categoría**: id, nombre, descripción, activa
- **Prioridad**: id, nombre, nivel (1-4), color, plazo_base_horas, activa
- **SLA_Regla**: id, categoría_id, prioridad_id, plazo_horas, vigente_desde, vigente_hasta
- **Comentario**: id, ticket_id, autor, texto, tipo (público/interno), fecha, adjuntos
- **Adjunto**: id, ticket_id, comentario_id, nombre_archivo, tipo_mime, tamaño, url
- **Notificación**: id, usuario_id, ticket_id, tipo, leída, fecha

## Supuestos

1. Autenticación/autorización ya existe o se integra con proveedor externo (no parte de este spec)
2. El sistema de sugerencia automática usa coincidencia de palabras clave simples (v1), no ML
3. Notificaciones email requieren configuración SMTP externa
4. Un usuario tiene un solo rol principal
5. Los plazos SLA se cuentan en horas laborables (configurable en v2)
6. Adjuntos se almacenan en almacenamiento de objetos (S3-compatible) o filesystem local
7. No hay portal de cliente externo; solo empleados de la organización

## Criterios de Éxito

| Métrica | Objetivo |
|---------|----------|
| Tiempo medio creación ticket | < 60 segundos |
| % tickets con categoría/prioridad sugerida aceptada sin cambios | > 70% |
| Tiempo medio primera respuesta (SLA Crítica) | < 1 hora |
| % tickets resueltos dentro de SLA | > 90% |
| Tickets reabiertos tras cierre | < 5% |
| Satisfacción usuario (encuesta post-cierre) | > 4/5 |
| Tiempo de carga dashboard supervisor | < 3 segundos |
| Cambios de configuración SLA sin afectar tickets cerrados | 100% casos |

## Fuera de Alcance (v1)

- Portal de autoservicio / base de conocimiento
- App móvil nativa
- Integración con sistemas de monitorización (alertas automáticas)
- Gestión de cambios / problemas / activos (ITIL completo)
- Workflow personalizado por categoría
- Firmas digitales / aprobaciones
- Multiorganización / multi-tenant
- Horarios laborales y festivos en cálculo SLA
- Reportes programados por email
- API pública para integraciones

## Dependencias

- Sistema de autenticación (SSO/OAuth2/LDAP)
- Servidor de correo SMTP para notificaciones email
- Almacenamiento de archivos (S3, Azure Blob, o filesystem)
- Base de datos relacional (PostgreSQL/MySQL)