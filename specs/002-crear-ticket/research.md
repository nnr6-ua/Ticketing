# Research: Creación de tickets de incidencia

**Fecha**: 2026-10-29 | **Plan**: [plan.md](./plan.md) | **Spec**: [spec.md](./spec.md)

No quedan incógnitas marcadas como `NEEDS CLARIFICATION`. Las decisiones siguientes resuelven el contexto técnico y los puntos que la especificación dejó abiertos.

## 1. Stack de frontend

- **Decisión**: Vue 3 con Composition API y `<script setup lang="ts">`, compilado con Vite y tipado con TypeScript. Estilos con Tailwind CSS y componentes accesibles con Headless UI (`Listbox`, `Dialog` si hiciera falta). Iconos con `@heroicons/vue`. Sin router, sin Pinia y sin axios.
- **Rationale**: Es el stack pedido y el más directo para una única pantalla. Vite ofrece arranque y recarga rápidos; TypeScript reduce errores en el contrato con la API; Headless UI aporta comportamiento accesible sin imponer estilos; Tailwind permite una interfaz profesional y consistente sin CSS artesanal extenso.
- **Alternativas consideradas**: Vue 2 (descartado, fin de soporte), Nuxt (SSR innecesario para una pantalla interna), Vuetify (sistema visual pesado y menos control estético), CSS Modules (más trabajo para un diseño consistente).

## 2. Stack de backend

- **Decisión**: FastAPI con Pydantic v2 y SQLAlchemy 2.0 en modo síncrono, servido con Uvicorn. Migraciones con Alembic. Driver `psycopg[binary]`.
- **Rationale**: FastAPI genera documentación OpenAPI y valida entrada/salida con poco código. SQLAlchemy síncrono es suficiente para el volumen previsto y mantiene la implementación simple; FastAPI ejecuta endpoints síncronos en un pool de hilos. Pydantic v2 permite mensajes de validación en español.
- **Alternativas consideradas**: SQLAlchemy asíncrono con `asyncpg` (complejidad innecesaria para el volumen), Django (más pesado y con más piezas), Flask (menos validación y documentación integradas).

## 3. Base de datos y numeración de tickets

- **Decisión**: PostgreSQL 16. Número de ticket generado por una secuencia de base de datos y formateado como `TK-` + 6 dígitos (`TK-000001`). La secuencia no se reutiliza; los huecos por transacciones fallidas son aceptables.
- **Rationale**: La secuencia garantiza unicidad y evita carreras entre peticiones concurrentes sin bloqueos de aplicación. El prefijo hace la referencia legible y fácil de dictar. Los huecos no incumplen "único e irrepetible".
- **Alternativas consideradas**: UUID (difícil de dictar y recordar), contador en aplicación con bloqueo (más frágil y con contención), `MAX(id)+1` (propenso a carreras).

## 4. Detección de duplicados

- **Decisión**: Hash SHA-256 de `title.strip()` + `\n` + `description.strip()` normalizado a NFC, junto al `creator_id`, con restricción única `(creator_id, content_hash)` en PostgreSQL. Si el hash ya existe para el empleado, se devuelve el ticket existente con `duplicate: true` y HTTP 200. La comparación es sensible a mayúsculas/minúsculas y no tiene ventana temporal.
- **Rationale**: La restricción única resuelve también carreras entre dos peticiones simultáneas: una inserta y la otra recibe violación de unicidad y recupera el ticket existente. El hash evita índices gigantes sobre descripciones largas. Recortar espacios evita duplicados accidentales por espacios al inicio/final.
- **Alternativas consideradas**: Comparar título/descripción completos (índice grande y comparación costosa), ventana temporal (descartada por la clarificación: duplicado siempre), token de idempotencia por formulario (no cubre reenvíos posteriores y añade estado en cliente).

## 5. Sugerencia de categoría y prioridad

- **Decisión**: Coincidencia determinista de palabras clave almacenadas en PostgreSQL. El texto del título y la descripción se normaliza (NFKD, sin acentos, minúsculas, signos convertidos en espacios) y se buscan palabras/frases completas configuradas por categoría y prioridad. Gana la categoría/prioridad con más coincidencias; empate por `sort_order` y luego `id`. Solo se consideran valores activos y no marcados como sistema. Si no hay coincidencia, se usa el valor por defecto activo; si no existe, el primer activo por `sort_order`/`id`; si no hay ninguno, la categoría/prioridad reservada "Sin clasificar".
- **Rationale**: Cumple "palabras clave sencillas" sin modelos ni dependencias. Es explicable, testeable y determinista. La categoría sugerida se aplica fija; la prioridad se puede cambiar en el formulario.
- **Alternativas consideradas**: Motor de reglas externo (sobreingeniería), similitud semántica/ML (fuera de alcance y no determinista), sugerencia solo en cliente (expondría el catálogo y duplicaría lógica).

## 6. Adjuntos y comportamiento todo-o-nada

- **Decisión**: Los archivos llegan en la misma petición `multipart/form-data` que crea el ticket. Se escriben primero en `ATTACHMENTS_DIR/tmp/`, se validan por extensión, `Content-Type`, firma binaria (PNG/JPEG/GIF) y tamaño máximo de 5 MB, y solo si todos son válidos se crea el ticket. Los archivos se mueven con `os.replace` a `ATTACHMENTS_DIR/attachments/{ticket_number}/{uuid}.{ext}` antes del `commit`; si algo falla, se hace rollback y se eliminan temporales y definitivos movidos. Máximo 5 archivos.
- **Rationale**: Una sola petición simplifica el todo-o-nada y evita tickets huérfanos. Guardar en temporal permite limpiar si falla la validación o la base de datos. La firma binaria evita aceptar archivos renombrados. El nombre final con UUID evita colisiones y ataques de rutas.
- **Alternativas consideradas**: Subida previa con endpoint de adjuntos y posterior creación (más estados y limpieza de huérfanos), almacenamiento en base de datos (peor rendimiento), S3 (fuera del requisito de carpeta local).
- **Limitación asumida**: un cierre inesperado del proceso entre el movimiento y el `commit` puede dejar archivos huérfanos. La limpieza automática de huérfanos no forma parte de esta historia.

## 7. Identidad del empleado y autenticación

- **Decisión**: La autenticación queda fuera de alcance. El backend expone una dependencia `get_current_employee` que lee la cabecera `X-Employee-Id` y resuelve un empleado activo. En producción, esa cabecera la establece el gateway/middleware de autenticación existente. En desarrollo, el frontend envía el id del empleado demo sembrado (`VITE_DEV_EMPLOYEE_ID=1`). Si falta o no es válido, se responde 401.
- **Rationale**: Permite completar el flujo y probar la autoría sin inventar un sistema de login (alcance fantasma). Deja un punto de integración claro para la autenticación real.
- **Alternativas consideradas**: Incluir login local (fuera de alcance), confiar en un `creator_id` del cuerpo (inseguro y no representa identidad autenticada), JWT propio (demasiada complejidad para v1).
- **Nota de seguridad**: La cabecera debe ser inyectada por un proxy de confianza y no aceptada directamente desde Internet en producción. Queda documentado en `quickstart.md` y en el contrato.

## 8. Catálogos iniciales

- **Decisión**: Script de siembra idempotente con:
  - Empleado demo (`demo@empresa.local`).
  - Categorías activas: "Red y conectividad", "Hardware", "Software", "Accesos y contraseñas", "Correo", "Impresoras", "Otros"; más la categoría de sistema "Sin clasificar".
  - Prioridades activas: "Crítica" (nivel 1), "Alta" (2), "Media" (3), "Baja" (4); más la prioridad de sistema "Sin clasificar" (nivel 5).
  - Palabras clave en español para cada categoría y prioridad (por ejemplo, "wifi", "vpn", "contraseña", "urgente", "no puedo trabajar").
  - Una categoría y una prioridad marcadas como `is_default`.
- **Rationale**: La administración de catálogos está fuera de alcance, pero la creación necesita valores reales. La siembra es reproducible y permite probar sugerencias y fallbacks.
- **Alternativas consideradas**: Catálogos hardcodeados en código (peor mantenimiento), pedir al usuario que los introduzca (fuera de alcance).

## 9. Contrato de API y errores

- **Decisión**: API REST bajo `/api/v1`:
  - `GET /api/v1/priorities?active=true` → prioridades activas no sistema.
  - `POST /api/v1/suggestions` → categoría fija y prioridad sugerida para un título/descripción.
  - `POST /api/v1/tickets` → creación multipart; 201 nuevo, 200 duplicado.
  - Errores con forma `{"error": {"code", "message", "field?, "details?"}}` y mensajes en español.
- **Rationale**: El formulario necesita la lista de prioridades para permitir el cambio y la sugerencia antes de enviar. Una forma de error única simplifica el manejo en el frontend y las pruebas de contrato.
- **Alternativas consideradas**: Calcular la sugerencia en cliente (expone catálogo y duplica reglas), GraphQL (innecesario), devolver 409 en duplicado (el requisito pide devolver la referencia existente; 200 con `duplicate: true` es más directo).

## 10. Estrategia de pruebas

- **Decisión**:
  - Backend: `pytest` con PostgreSQL de pruebas dedicado; pruebas unitarias de sugerencias, hash, validación de adjuntos y numeración; pruebas de contrato con `TestClient`; pruebas de integración de transacción, rollback y limpieza de archivos.
  - Frontend: Vitest + Vue Test Utils + jsdom, mockeando el módulo `services/api`; cubrir validación, debounce de sugerencia, cambio de prioridad, estado de carga, error de red, duplicado y confirmación.
  - Validación end-to-end manual en `quickstart.md`.
- **Rationale**: Cubre la lógica crítica sin introducir Playwright ni infraestructura E2E en v1. El backend concentra las reglas que no deben depender del navegador.
- **Alternativas consideradas**: Playwright/Cypress (valioso pero añade complejidad y tiempo de CI), SQLite en pruebas (no reproduce secuencias, arrays ni restricciones de PostgreSQL).

## 11. Configuración y ejecución local

- **Decisión**: `compose.yaml` con PostgreSQL 16 y volumen nombrado. Backend y frontend se ejecutan en local con Uvicorn y Vite. Variables en `.env` (backend) y `.env.local` (frontend); `.env.example` sin secretos. Migraciones y siembra por comandos documentados.
- **Rationale**: Un solo contenedor para la base de datos mantiene el arranque simple y evita reconstruir imágenes en cada cambio de código.
- **Alternativas consideradas**: Compose completo con backend/frontend (más lento para desarrollo), base de datos instalada en el host (menos reproducible).

## 12. Interfaz y estética

- **Decisión**: Una sola vista centrada, fondo neutro, tarjeta blanca con sombra suave, tipografía del sistema, color primario azul/índigo, estados de foco visibles, mensajes de error en rojo, badges de prioridad con color configurado. Cabecera con marca textual "Mesa de ayuda". Confirmación con el número de ticket en tipografía monoespaciada y botón de copiar. Sin modo oscuro, sin animaciones complejas, sin fuentes externas.
- **Rationale**: Profesional y sobria sin dependencias visuales adicionales. Accesible y responsive por defecto con Tailwind y Headless UI.
- **Alternativas consideradas**: Biblioteca de componentes completa (más peso y menos control), fuentes de Google (dependencia de red), modo oscuro (alcance no solicitado).
