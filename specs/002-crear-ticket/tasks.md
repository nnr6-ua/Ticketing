# Tasks: Creación de tickets de incidencia

**Input**: Design documents from `/specs/002-crear-ticket/`

**Prerequisites**: `plan.md`, `spec.md`, `research.md`, `data-model.md`, `contracts/openapi.yaml`, `quickstart.md`

**Tests**: Incluidos porque el plan técnico define una estrategia de pruebas automatizadas (pytest y Vitest) y el quickstart exige validación end-to-end.

**Organization**: Tareas agrupadas por historia de usuario para permitir implementación y prueba independiente de cada incremento.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Puede ejecutarse en paralelo (archivos distintos, sin dependencias de tareas incompletas)
- **[Story]**: Historia de usuario a la que pertenece la tarea (`US1`, `US2`, `US3`)
- Cada tarea incluye la ruta exacta del archivo o directorio afectado

## Path Conventions

- Backend: `backend/app/`, `backend/tests/`, `backend/alembic/`
- Frontend: `frontend/src/`, `frontend/src/tests/`
- Raíz: `compose.yaml`, `.gitignore`, `README.md`

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Inicialización del monorepo y de las dos aplicaciones.

- [x] T001 Crear la estructura del monorepo (`backend/app/{api,core,db,models,schemas,services,seeds}`, `backend/tests/{unit,contract,integration}`, `frontend/src/{components,composables,services,types,tests}`) y el `.gitignore` raíz excluyendo `backend/.venv/`, `backend/attachments/`, `frontend/node_modules/`, `frontend/dist/`, `.env` y `.env.local`
- [x] T002 Inicializar el backend en `backend/pyproject.toml` con Python 3.12, FastAPI, SQLAlchemy 2.0 síncrono, Alembic, Pydantic v2, `python-multipart`, `psycopg[binary]`, Uvicorn y el extra `dev` con pytest, httpx y coverage
- [x] T003 [P] Inicializar el frontend en `frontend/package.json`, `frontend/vite.config.ts`, `frontend/tsconfig.json`, `frontend/tailwind.config.js` y `frontend/postcss.config.js` con Vue 3, TypeScript, Tailwind CSS, `@headlessui/vue`, `@heroicons/vue`, Vitest, Vue Test Utils y jsdom
- [x] T004 [P] Crear `compose.yaml` con el servicio `db` de PostgreSQL 16, base `ticketing`, volumen persistente y puerto `5432`
- [x] T005 [P] Crear `backend/.env.example` (`DATABASE_URL`, `ATTACHMENTS_DIR`, `CORS_ORIGINS`) y `frontend/.env.example` (`VITE_API_BASE_URL`, `VITE_DEV_EMPLOYEE_ID`) sin secretos reales

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Infraestructura y modelos que bloquean todas las historias.

**⚠️ CRITICAL**: Ninguna historia puede empezar hasta completar esta fase.

- [x] T006 Implementar la configuración en `backend/app/core/config.py` leyendo `DATABASE_URL`, `ATTACHMENTS_DIR` y `CORS_ORIGINS` desde variables de entorno con valores por defecto de desarrollo
- [x] T007 Crear la base declarativa y la sesión de SQLAlchemy en `backend/app/db/base.py` y `backend/app/db/session.py` (engine, `SessionLocal` y dependencia `get_db`)
- [x] T008 [P] Crear el modelo `Employee` en `backend/app/models/employee.py` con `id BIGSERIAL PK`, `name VARCHAR(120) NOT NULL`, `email VARCHAR(255) NOT NULL, UNIQUE`, `is_active BOOLEAN NOT NULL DEFAULT TRUE`, `created_at TIMESTAMPTZ NOT NULL DEFAULT now()`
- [x] T009 [P] Crear el modelo `Category` en `backend/app/models/category.py` con `name VARCHAR(80) NOT NULL, UNIQUE`, `description TEXT`, `keywords TEXT[] NOT NULL DEFAULT '{}'`, `is_active BOOLEAN NOT NULL DEFAULT TRUE`, `is_system BOOLEAN NOT NULL DEFAULT FALSE`, `is_default BOOLEAN NOT NULL DEFAULT FALSE`, `sort_order INTEGER NOT NULL DEFAULT 0`, timestamps, `CHECK (char_length(name) BETWEEN 1 AND 80)` e índice único parcial `ux_categories_single_default ON categories (is_default) WHERE is_default AND is_active AND NOT is_system`
- [x] T010 [P] Crear el modelo `Priority` en `backend/app/models/priority.py` con `name VARCHAR(80) NOT NULL, UNIQUE`, `level SMALLINT NOT NULL, CHECK entre 1 y 5`, `color VARCHAR(7) NOT NULL DEFAULT '#64748b', CHECK '^#[0-9A-Fa-f]{6}$'`, `keywords TEXT[] NOT NULL DEFAULT '{}'`, `is_active`, `is_system`, `is_default`, `sort_order`, timestamps e índice único parcial `ux_priorities_single_default ON priorities (is_default) WHERE is_default AND is_active AND NOT is_system`
- [x] T011 [P] Crear el modelo `Ticket` en `backend/app/models/ticket.py` con `ticket_number VARCHAR(20) NOT NULL, UNIQUE`, `title VARCHAR(120) NOT NULL, CHECK longitud 5–120`, `description TEXT NOT NULL, CHECK longitud 20–5000`, `content_hash CHAR(64) NOT NULL`, `status VARCHAR(30) NOT NULL DEFAULT 'Abierto', CHECK en ('Abierto','En progreso','Pendiente de usuario','Resuelto','Cerrado')`, FKs a `categories`, `priorities` y `employees`, `UNIQUE (creator_id, content_hash)`, timestamps e índices `ix_tickets_creator_created` y `ix_tickets_status`
- [x] T012 [P] Crear el modelo `TicketEvent` en `backend/app/models/ticket_event.py` con `ticket_id BIGINT NOT NULL, FK ON DELETE CASCADE`, `event_type VARCHAR(30) NOT NULL, CHECK en ('created')`, `author_id BIGINT NOT NULL, FK a employees`, `metadata JSONB NOT NULL DEFAULT '{}'`, `created_at TIMESTAMPTZ NOT NULL DEFAULT now()` e índice `ix_ticket_events_ticket_created`
- [x] T013 [P] Crear el modelo `Attachment` en `backend/app/models/attachment.py` con `ticket_id BIGINT NOT NULL, FK ON DELETE CASCADE`, `original_filename VARCHAR(255) NOT NULL`, `stored_filename VARCHAR(255) NOT NULL, UNIQUE`, `mime_type VARCHAR(100) NOT NULL, CHECK en ('image/png','image/jpeg','image/gif')`, `size_bytes BIGINT NOT NULL, CHECK > 0 y <= 5242880`, `relative_path TEXT NOT NULL, UNIQUE`, `created_at` e índice `ix_attachments_ticket`
- [x] T014 Configurar Alembic en `backend/alembic.ini` y `backend/alembic/env.py` y crear la migración inicial en `backend/alembic/versions/` con la secuencia `ticket_number_seq` (`START 1 INCREMENT 1`), las seis tablas, checks, FKs e índices de T008–T013
- [x] T015 Crear el script de siembra idempotente en `backend/app/seeds/seed.py` con el empleado demo, las categorías y prioridades de `data-model.md`, sus palabras clave, los valores `is_default` y las filas de sistema "Sin clasificar"
- [x] T016 [P] Implementar los errores de aplicación y el handler en español en `backend/app/core/errors.py` con la forma `{"error": {"code", "message", "field?", "details?"}}`
- [x] T017 Implementar la dependencia `get_current_employee` en `backend/app/api/deps.py` leyendo `X-Employee-Id`, validando que el empleado existe y está activo, y devolviendo 401 con mensaje en español si falta o no es válido
- [x] T018 [P] Crear los esquemas Pydantic en `backend/app/schemas/catalog.py`, `backend/app/schemas/errors.py`, `backend/app/schemas/suggestion.py` y `backend/app/schemas/ticket.py` para prioridades, categorías, sugerencias, adjuntos, ticket y errores
- [x] T019 [P] Crear el cliente de API y los tipos en `frontend/src/services/api.ts` y `frontend/src/types/api.ts` usando `fetch`, `VITE_API_BASE_URL`, cabecera `X-Employee-Id` desde `VITE_DEV_EMPLOYEE_ID` y parseo del formato de error del contrato
- [x] T020 [P] Crear la base visual en `frontend/src/App.vue`, `frontend/src/main.ts`, `frontend/src/style.css` y `frontend/src/components/AppHeader.vue` con Tailwind, fondo neutro, tarjeta centrada, tipografía del sistema y cabecera "Mesa de ayuda"
- [x] T021 [P] Implementar la resolución de valores por defecto en `backend/app/services/catalogs.py`: categoría/prioridad por defecto activa no sistema, si no existe la primera activa no sistema por `sort_order`/`id`, si no hay ninguna la fila de sistema "Sin clasificar"
- [x] T022 Crear la aplicación FastAPI en `backend/app/main.py` con CORS desde `CORS_ORIGINS`, registro del handler de errores, routers base en `backend/app/api/routes/__init__.py` y arranque de `uvicorn`

**Checkpoint**: Base de datos, modelos, siembra, errores, identidad, esquemas, cliente API y layout listos. Las historias pueden comenzar.

---

## Phase 3: User Story 1 - Registrar una incidencia y obtener número de referencia (Priority: P1) 🎯 MVP

**Goal**: Un empleado crea un ticket con título y descripción, recibe un número `TK-000001`, y el ticket queda registrado con creador, fecha/hora, estado "Abierto" y primer evento de historial. Para esta historia se usan la categoría y prioridad por defecto; las sugerencias llegan en US3.

**Independent Test**: Enviar un título y una descripción válidos, comprobar que la respuesta muestra un número único `TK-XXXXXX`, que la confirmación muestra estado/creador/fecha y que existen un registro en `tickets` y otro en `ticket_events` con `event_type = 'created'`.

### Tests for User Story 1

- [x] T023 [P] [US1] Escribir el test de contrato de creación en `backend/tests/contract/test_create_ticket.py`: `POST /api/v1/tickets` sin adjuntos devuelve 201, `ticket_number` con patrón `^TK-[0-9]{6,}$`, `status = "Abierto"`, `duplicate = false`, creador y `attachments = []`
- [x] T024 [P] [US1] Escribir el test de integración de persistencia en `backend/tests/integration/test_ticket_creation.py`: se crean `tickets` y `ticket_events` con `event_type = 'created'` y `metadata` con `ticket_number` y `status`
- [x] T025 [P] [US1] Escribir el test unitario de numeración en `backend/tests/unit/test_ticket_number.py`: el primer ticket es `TK-000001`, los números son únicos y los huecos de secuencia están permitidos
- [x] T026 [P] [US1] Escribir el test de componente del formulario en `frontend/src/tests/TicketForm.spec.ts`: validación de título 5–120 y descripción 20–5000, estado de carga, error de red conservando datos y paso a confirmación

### Implementation for User Story 1

- [x] T027 [US1] Implementar el hash de duplicados en `backend/app/services/duplicates.py` como `SHA-256(NFC(title.strip()) + "\n" + NFC(description.strip()))`, sensible a mayúsculas/minúsculas
- [x] T028 [US1] Implementar la creación de tickets en `backend/app/services/tickets.py`: insertar ticket con número `'TK-' || lpad(nextval('ticket_number_seq')::text, 6, '0')`, estado `'Abierto'`, categoría/prioridad desde `backend/app/services/catalogs.py`, insertar el evento `created` y devolver el ticket existente con `duplicate = true` si `(creator_id, content_hash)` ya existe
- [x] T029 [US1] Implementar el endpoint `POST /api/v1/tickets` en `backend/app/api/routes/tickets.py` aceptando `multipart/form-data` con `title` y `description`, devolviendo 201 para ticket nuevo y 200 para duplicado según `contracts/openapi.yaml`
- [x] T030 [US1] Añadir la validación de `title` (5–120 caracteres tras `strip()`) y `description` (20–5000 caracteres tras `strip()`) con mensajes en español en `backend/app/schemas/ticket.py` y `backend/app/services/tickets.py`
- [x] T031 [US1] Implementar el formulario y su estado en `frontend/src/components/TicketForm.vue` y `frontend/src/composables/useTicketForm.ts`: campos título/descripción, contadores, validación cliente, envío multipart, botón deshabilitado durante el envío y conservación de datos ante error
- [x] T032 [US1] Implementar la confirmación en `frontend/src/components/TicketConfirmation.vue`: número de ticket destacado en monoespaciado, botón de copiar, estado "Abierto", creador, fecha/hora en es-ES, aviso de duplicado y acción "Crear otro ticket"
- [x] T033 [US1] Implementar `frontend/src/components/ErrorBanner.vue` y los iconos inline necesarios en `frontend/src/components/icons/` con mensajes en español y `aria-live`
- [x] T034 [US1] Integrar formulario, banner de error y confirmación en `frontend/src/App.vue`, incluyendo el aviso de identidad no disponible cuando la API responde 401

**Checkpoint**: US1 funcional y demostrable de extremo a extremo con categoría/prioridad por defecto.

---

## Phase 4: User Story 2 - Adjuntar capturas de pantalla (Priority: P2)

**Goal**: Añadir de 1 a 5 imágenes al ticket con validación de tipo y tamaño, comportamiento todo-o-nada y conservación de datos si algo falla.

**Independent Test**: Crear un ticket con varias imágenes válidas y comprobar que se asocian; enviar un PDF, un archivo renombrado o uno de más de 5 MB y comprobar que se rechaza sin crear ticket y sin perder el resto del formulario.

### Tests for User Story 2

- [x] T035 [P] [US2] Escribir los tests de contrato de adjuntos en `backend/tests/contract/test_ticket_attachments.py`: PNG/JPEG/GIF válidos, extensión no permitida, firma binaria inválida, más de 5 MB, más de 5 archivos y respuesta 422 con `error.code`/`error.message` en español
- [x] T036 [P] [US2] Escribir el test de integración todo-o-nada en `backend/tests/integration/test_attachments.py`: si falla un adjunto no se crea ticket, no quedan filas en `attachments` y se limpian temporales y archivos definitivos
- [x] T037 [P] [US2] Escribir el test de componente de adjuntos en `frontend/src/tests/AttachmentField.spec.ts`: selección múltiple, miniaturas, eliminación, rechazo por tipo/tamaño/cantidad y conservación de datos

### Implementation for User Story 2

- [x] T038 [US2] Implementar el servicio de adjuntos en `backend/app/services/attachments.py`: escribir en `ATTACHMENTS_DIR/tmp/`, validar extensión, `Content-Type` y firma binaria de PNG/JPEG/GIF, máximo 5 archivos y 5 MB por archivo, y mover a `ATTACHMENTS_DIR/attachments/{ticket_number}/{uuid}.{ext}` con `os.replace`
- [x] T039 [US2] Integrar los adjuntos en `backend/app/services/tickets.py` con transacción todo-o-nada: mover archivos antes del `commit`, hacer rollback y borrar temporales/definitivos si falla cualquier validación, la base de datos o el movimiento
- [x] T040 [US2] Extender `POST /api/v1/tickets` en `backend/app/api/routes/tickets.py` para aceptar el campo `attachments` (`multipart/form-data`, máximo 5 archivos) y devolver la lista de adjuntos con `original_filename`, `mime_type` y `size_bytes`
- [x] T041 [US2] Implementar `frontend/src/components/AttachmentField.vue` con zona de arrastre, selector de archivos, miniaturas mediante `URL.createObjectURL`, eliminación, validación cliente de tipo/tamaño/cantidad y mensajes por archivo
- [x] T042 [US2] Integrar `AttachmentField` en `frontend/src/components/TicketForm.vue` y `frontend/src/composables/useTicketForm.ts`, enviando los archivos en el mismo `FormData` del ticket
- [x] T043 [US2] Asegurar en `frontend/src/composables/useTicketForm.ts` que un fallo de subida o de red conserva título, descripción, adjuntos seleccionados y prioridad, y permite reintentar sin duplicar

**Checkpoint**: US1 y US2 funcionan juntas; US2 sigue siendo verificable por API y por el formulario.

---

## Phase 5: User Story 3 - Recibir sugerencias de categoría y prioridad (Priority: P3)

**Goal**: Sugerir una categoría fija y una prioridad editable a partir de palabras clave del título/descripción, usando solo valores activos y con fallback a valores por defecto.

**Independent Test**: Escribir una descripción con términos reconocibles y comprobar que se propone una categoría y prioridad activas; escribir una descripción neutra y comprobar que se usan los valores por defecto; cambiar la prioridad antes de enviar y comprobar que se guarda la elegida.

### Tests for User Story 3

- [x] T044 [P] [US3] Escribir los tests unitarios de sugerencias en `backend/tests/unit/test_suggestions.py`: mayúsculas, acentos, palabras/frases completas, empate por `sort_order`/`id`, exclusión de valores inactivos y de sistema, y cadena de fallback por defecto → primera activa → "Sin clasificar"
- [x] T045 [P] [US3] Escribir los tests de contrato de `GET /api/v1/priorities` y `POST /api/v1/suggestions` en `backend/tests/contract/test_suggestions.py`: solo prioridades activas no sistema, respuesta con `category`, `priority`, `category_is_fallback` y `priority_is_fallback`
- [x] T046 [P] [US3] Escribir el test de componente de sugerencia en `frontend/src/tests/SuggestionPanel.spec.ts`: categoría de solo lectura, prioridad editable con Headless UI, etiqueta de fallback y debounce de la llamada de sugerencia

### Implementation for User Story 3

- [x] T047 [US3] Implementar el servicio de sugerencias en `backend/app/services/suggestions.py`: normalizar texto con NFKD, sin acentos, minúsculas y signos como espacios; buscar palabras/frases completas en `keywords`; puntuar por número de coincidencias; desempatar por `sort_order` y `id`; considerar solo valores activos no sistema y aplicar el fallback de `backend/app/services/catalogs.py`
- [x] T048 [US3] Implementar `GET /api/v1/priorities` en `backend/app/api/routes/priorities.py` y `POST /api/v1/suggestions` en `backend/app/api/routes/suggestions.py` según `contracts/openapi.yaml`
- [x] T049 [US3] Integrar la sugerencia en `backend/app/services/tickets.py`: recalcular la categoría a partir del texto final del servidor (no aceptar `category_id` del cliente) y usar `priority_id` del cliente solo si está activa y no es de sistema; en caso contrario, usar la prioridad sugerida
- [x] T050 [US3] Implementar `frontend/src/components/SuggestionPanel.vue` y `frontend/src/components/PrioritySelect.vue`: categoría fija con icono de bloqueo y etiqueta "Categoría asignada automáticamente", prioridad con `Listbox` de Headless UI y punto de color, aviso de valor por defecto y `aria-live`
- [x] T051 [US3] Integrar la sugerencia en `frontend/src/components/TicketForm.vue` y `frontend/src/composables/useTicketForm.ts`: llamada con debounce de 400 ms al cambiar título/descripción, cancelación de peticiones obsoletas y envío de `priority_id`
- [x] T052 [US3] Completar `frontend/src/services/api.ts` con `getPriorities()` y `getSuggestion(title, description)` y sus tipos en `frontend/src/types/api.ts`

**Checkpoint**: Las tres historias funcionan de extremo a extremo y cada una conserva su prueba independiente.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Calidad, accesibilidad, documentación y validación final.

- [x] T053 [P] Añadir tests de contrato de validación, identidad y forma de error en `backend/tests/contract/test_validation.py`: 401 sin `X-Employee-Id`, 422 por longitudes, prioridad inactiva o de sistema y cuerpo mal formado
- [x] T054 [P] Ampliar `frontend/src/tests/TicketForm.spec.ts` con pérdida de conexión, error 401, error de validación por campo y reintento sin duplicado
- [x] T055 [P] Revisar accesibilidad en `frontend/src/components/`: etiquetas asociadas, foco visible, navegación por teclado, contraste, `aria-live` para errores/sugerencias y textos alternativos de miniaturas
- [x] T056 [P] Crear `README.md` raíz con resumen del stack, requisitos, arranque rápido y enlace a `specs/002-crear-ticket/quickstart.md`
- [x] T057 Ejecutar `pytest` en `backend/` y `npm run test` en `frontend/`, corregir fallos y dejar ambas suites en verde
- [x] T058 Ejecutar los escenarios 1–10 de `specs/002-crear-ticket/quickstart.md` y corregir cualquier desviación de comportamiento o mensaje (validado con pruebas de API, componentes y servidor real; la revisión visual manual en navegador queda opcional)
- [x] T059 Revisar seguridad y configuración en `backend/app/api/deps.py`, `backend/app/main.py`, `backend/app/core/config.py`, `backend/.env.example`, `frontend/.env.example` y `.gitignore`: `X-Employee-Id` solo desde proxy de confianza, CORS con origen concreto, `ATTACHMENTS_DIR` fuera del directorio servido al frontend, ausencia de secretos en código y `.env.example` sin credenciales reales

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: sin dependencias; puede empezar inmediatamente.
- **Foundational (Phase 2)**: depende de Setup y bloquea todas las historias.
- **User Stories (Phase 3–5)**: dependen de Foundational. Se pueden hacer en paralelo si hay equipo, o en orden P1 → P2 → P3.
- **Polish (Phase 6)**: depende de las historias que se quieran entregar.

### User Story Dependencies

- **US1 (P1)**: depende de Foundational. No depende de otras historias. Usa categoría/prioridad por defecto.
- **US2 (P2)**: depende de Foundational y de la base del formulario de US1 para la integración visual. Su API de adjuntos es verificable de forma independiente.
- **US3 (P3)**: depende de Foundational y de la base del formulario de US1 para la integración visual. Su API de sugerencias es verificable de forma independiente.

### Within Each User Story

- Los tests (si se incluyen) se escriben antes de la implementación y deben fallar.
- Modelos/servicios antes que endpoints.
- Endpoints antes de la integración en el frontend.
- La historia debe quedar verificable antes de pasar a la siguiente prioridad.

### Parallel Opportunities

- Setup: T003, T004 y T005 en paralelo tras T001/T002.
- Foundational: T008–T013 en paralelo tras T007; T016, T018, T019, T020 y T021 en paralelo cuando sus dependencias estén listas.
- US1: T023–T026 en paralelo; T027 y T031 en paralelo; T032 y T033 en paralelo.
- US2: T035–T037 en paralelo; T038 y T041 en paralelo.
- US3: T044–T046 en paralelo; T047 y T050 en paralelo.
- Polish: T053–T056 en paralelo.

---

## Parallel Example: User Story 1

```bash
# Tests de US1 en paralelo
Task: "Test de contrato de creación en backend/tests/contract/test_create_ticket.py"
Task: "Test de integración de persistencia en backend/tests/integration/test_ticket_creation.py"
Task: "Test unitario de numeración en backend/tests/unit/test_ticket_number.py"
Task: "Test de componente del formulario en frontend/src/tests/TicketForm.spec.ts"

# Implementación inicial en paralelo
Task: "Hash de duplicados en backend/app/services/duplicates.py"
Task: "Formulario y estado en frontend/src/components/TicketForm.vue y frontend/src/composables/useTicketForm.ts"
```

## Parallel Example: User Story 2

```bash
Task: "Tests de contrato de adjuntos en backend/tests/contract/test_ticket_attachments.py"
Task: "Test de integración todo-o-nada en backend/tests/integration/test_attachments.py"
Task: "Test de componente de adjuntos en frontend/src/tests/AttachmentField.spec.ts"
```

## Parallel Example: User Story 3

```bash
Task: "Tests unitarios de sugerencias en backend/tests/unit/test_suggestions.py"
Task: "Tests de contrato de sugerencias en backend/tests/contract/test_suggestions.py"
Task: "Test de componente de sugerencia en frontend/src/tests/SuggestionPanel.spec.ts"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Completar Phase 1: Setup.
2. Completar Phase 2: Foundational (bloquea todo).
3. Completar Phase 3: US1.
4. **PARAR Y VALIDAR**: probar US1 de forma independiente con el escenario 1 de `quickstart.md`.
5. Demostrar/desplegar si está listo.

### Incremental Delivery

1. Setup + Foundational → base lista.
2. US1 → validar → demo (MVP).
3. US2 → validar adjuntos → demo.
4. US3 → validar sugerencias → demo.
5. Polish → suites en verde y quickstart completo.

### Parallel Team Strategy

1. El equipo completa Setup + Foundational.
2. Tras Foundational:
   - Persona A: US1.
   - Persona B: US2 (API de adjuntos y componente).
   - Persona C: US3 (API de sugerencias y componente).
3. Integrar en el formulario respetando el orden P1 → P2 → P3.

---

## Notes

- `[P]` indica archivos distintos y sin dependencias de tareas incompletas.
- `[US1]`, `[US2]` y `[US3]` mapean cada tarea a la historia correspondiente.
- Cada historia debe poder validarse de forma independiente; US2 y US3 añaden valor sin romper US1.
- No implementar seguimiento, administración de catálogos, notificaciones ni autenticación propia: están fuera de alcance.
- Verificar que los tests fallan antes de implementar y que las suites quedan en verde antes de cerrar cada fase.

---

## Phase 7: Convergence

- [ ] T060 CRITICAL — Añadir pruebas de backend para validación de título/descripción (longitudes tras `strip()`, caracteres especiales y código), primer evento de historial con fecha y autor, sugerencia de prioridad por palabras clave y fallback de catálogos inactivos; cubrir tipo/tamaño/firma de adjuntos (JPEG/GIF, >5 MB, firma inválida), atomicidad con mezcla de archivos válidos e inválidos y limpieza de temporales/definitivos per Constitution IV (partial)
- [ ] T061 CRITICAL — Añadir prueba de concurrencia en PostgreSQL que envíe el mismo creador, título y descripción en paralelo y verifique un único ticket, la misma referencia y ausencia de adjuntos huérfanos per RF-015, CE-006 y Constitution IV (missing)
- [ ] T062 CRITICAL — Añadir pruebas de frontend (Vitest) para `TicketForm`/`useTicketForm`, `AttachmentField`, `SuggestionPanel`/`PrioritySelect` y `TicketConfirmation`: validaciones, conservación de datos ante error de red, límites de adjuntos, categoría fija/prioridad editable, aviso de duplicado y formato es-ES per Constitution IV, US1/AC4, US2/AC1-3 y US3/AC2 (missing)
- [ ] T063 CRITICAL — Proporcionar una entrada visible a la creación de tickets para el rol `usuario`: redirección tras el login y/o enlace de cabecera a `/tickets/new`, sin depender de la cola de trabajo (403 para no técnicos), con prueba de navegación per US1/AC1 y CE-002 (missing)
- [ ] T064 Implementar el fallback final "Sin clasificar": sembrar/garantizar una categoría y prioridad de sistema activas (`is_system = true`, sin palabras clave) y usarlas cuando no haya ningún valor activo, respetando el CHECK de nivel 1–4 o ampliándolo con migración; añadir pruebas per RF-014, US3/AC3-4 y CE-007 (partial)
- [ ] T065 Persistir los adjuntos en Docker Compose mediante volumen nombrado y `ATTACHMENTS_DIR`, y excluir la carpeta de adjuntos en `.gitignore` per plan: storage decision, T001 y Constitution II (missing)
- [ ] T066 Corregir accesibilidad del flujo de creación: asociar etiquetas al selector de prioridad y al campo de adjuntos (`for`/`id`/`aria-labelledby`), nombre accesible en `ListboxButton` y texto alternativo de miniaturas; añadir prueba axe del flujo per Constitution V y T055 (partial)
- [ ] T067 Reconciliar los artefactos de la funcionalidad con la arquitectura integrada: actualizar `data-model.md`, `contracts/openapi.yaml` y `quickstart.md` para reflejar JWT/User UUID, `{"detail": {"code","message"}}`, timeline y `docker compose`/`scripts/seed_dev.py`, sin tocar `spec.md` ni `plan.md` per Constitution II y IV (contradicts)
- [ ] T068 Validar también el `Content-Type` declarado en cada adjunto contra el tipo permitido (además de extensión y firma) o documentar por qué se descarta, con prueba per plan T038 y RF-004 (partial)
- [ ] T069 Formatear la fecha de creación con `timeZone: "Europe/Madrid"` en la confirmación y cubrirlo con prueba per Constitution V (partial)
