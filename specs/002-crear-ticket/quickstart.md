# Quickstart: Creación de tickets de incidencia

**Feature**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md) | **Contrato**: [contracts/openapi.yaml](./contracts/openapi.yaml)

Guía de validación end-to-end sobre la arquitectura integrada del proyecto:
FastAPI + PostgreSQL + JWT, y Vue 3 + Pinia + vue-router.

## Requisitos previos

- Docker y Docker Compose (recomendado para la validación completa).
- Python 3.12 y Node.js 18+ si se ejecuta en local sin contenedores.
- Navegador moderno.

## Puesta en marcha con Docker Compose

Desde la raíz del repositorio:

```bash
cp .env.example .env
docker compose up -d --build
docker compose exec backend python scripts/seed_dev.py
```

Servicios publicados:

- Frontend: `http://localhost:8080`
- Backend/OpenAPI: `http://localhost:8000/docs`
- PostgreSQL: `localhost:5432` (credenciales de `.env`)

El backend aplica `alembic upgrade head` al arrancar. Los adjuntos se guardan
en el volumen nombrado `ticketing_attachments`, montado en `/app/attachments`
del contenedor.

## Puesta en marcha en local

### 1. Base de datos

```bash
docker compose up -d db
```

### 2. Backend

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env
alembic upgrade head
python scripts/seed_dev.py
uvicorn app.main:app --reload --port 8000
```

### 3. Autenticación de desarrollo

El proyecto usa JWT. El stub `POST /api/v1/dev/login` solo está registrado si
`AUTH_DEV_STUB_ENABLED=true` y sirve para obtener un token de un usuario del
seed:

```bash
TOKEN=$(curl -s http://localhost:8000/api/v1/dev/login \
  -H "Content-Type: application/json" \
  -d '{"email":"usuario@example.com"}' | python3 -c 'import json,sys; print(json.load(sys.stdin)["access_token"])')

curl -s http://localhost:8000/api/v1/priorities \
  -H "Authorization: Bearer $TOKEN" | python3 -m json.tool
```

Resultado esperado: prioridades activas seleccionables (Crítica, Alta, Media,
Baja) con `id`, `level` y `color`. La prioridad de sistema «Sin clasificar» no
se lista.

### 4. Frontend

```bash
cd frontend
npm install
cp .env.example .env.local
npm run dev
```

Abrir `http://localhost:5173/login`. Con el usuario
`usuario@example.com` (rol `usuario`) el login redirige directamente a
`/tickets/new`. Con un técnico se entra a la cola de trabajo.

## Variables de entorno

Backend (`.env`, basado en `backend/.env.example`):

| Variable | Ejemplo | Uso |
|----------|---------|-----|
| `DATABASE_URL` | `postgresql+psycopg://ticketing:ticketing@localhost:5432/ticketing` | Conexión a PostgreSQL |
| `JWT_SECRET` | `dev-only-secret` | Firma y validación del Bearer JWT |
| `JWT_ALGORITHM` | `HS256` | Algoritmo del JWT |
| `AUTH_ISSUER` / `AUTH_AUDIENCE` | vacío | Claims opcionales que se validan si están configurados |
| `AUTH_DEV_STUB_ENABLED` | `true` | Habilita `/api/v1/dev/login` solo en desarrollo |
| `FRONTEND_ORIGINS` | `http://localhost:5173` | Orígenes permitidos por CORS, separados por coma |
| `ATTACHMENTS_DIR` | `./attachments` | Directorio raíz de los adjuntos |

Frontend (`.env.local`, basado en `frontend/.env.example`):

| Variable | Ejemplo | Uso |
|----------|---------|-----|
| `VITE_API_BASE_URL` | vacío | Vacío usa el proxy de Vite/Nginx; también admite `http://localhost:8000` |

No hay secretos reales en los archivos de ejemplo. `dev-only-secret` no debe
usarse fuera de desarrollo.

## Pruebas automatizadas

```bash
# Backend: SQLite por defecto.
cd backend
python3 -m pytest -q

# Backend: PostgreSQL real (incluye las pruebas de concurrencia).
TEST_DATABASE_URL=postgresql+psycopg://ticketing:ticketing@localhost:5432/ticketing \
  python3 -m pytest -q -m postgres

# Frontend.
cd frontend
npm test
npm run build
```

Resultado esperado: todas las pruebas en verde.

## Escenarios de validación manual

### Escenario 1 — Creación correcta (HU-1, CE-001, CE-002, CE-003)

1. Entrar en `/login` con `usuario@example.com`.
2. Introducir título `No puedo conectarme a la VPN` y descripción `Desde esta mañana, al conectar la VPN recibo un error de autenticación y no puedo acceder a los recursos internos.`
3. Esperar la sugerencia: debe aparecer la categoría «Red» y una prioridad
   editable (previsiblemente «Media»).
4. Enviar.
5. Comprobar:
   - Se muestra un número con formato `TK-000001`.
   - La confirmación muestra el estado «Abierto», el creador y la fecha/hora
     en zona `Europe/Madrid`.
   - En base de datos existe un registro en `tickets` y otro en
     `ticket_timeline_entries` con `event_type = 'created'`.

### Escenario 2 — Sugerencia y prioridad editable (HU-3)

1. Escribir una descripción con términos reconocibles (`wifi`, `vpn`, etc.).
2. Comprobar que la categoría aparece fijada (sin selector) y con etiqueta de
   sugerencia.
3. Cambiar la prioridad en el selector y enviar.
4. Comprobar que el ticket se crea con la prioridad elegida y la categoría
   sugerida.

### Escenario 3 — Sin sugerencia y fallback (HU-3, CE-007)

1. Escribir un título y descripción neutros, sin palabras clave (`Necesito ayuda con una gestión`, `Me gustaría que alguien revise este asunto cuando sea posible, gracias.`).
2. Comprobar que se muestran los valores por defecto (categoría «Otros» y
   prioridad «Media»).
3. Enviar y comprobar que el ticket se crea sin bloqueo.
4. Si un administrador desactiva todos los catálogos personalizados, la
   creación sigue funcionando con las filas de sistema «Sin clasificar».

### Escenario 4 — Adjuntos válidos (HU-2)

1. Adjuntar 1–5 imágenes PNG/JPG/GIF de menos de 5 MB.
2. Comprobar las miniaturas y que se pueden quitar antes de enviar.
3. Enviar.
4. Comprobar que la confirmación lista los adjuntos y que los archivos existen
   en `ATTACHMENTS_DIR/TK-XXXXXX/`.

### Escenario 5 — Adjunto inválido (HU-2, CE-005)

1. Intentar adjuntar un PDF o un archivo renombrado a `.png` que no sea una
   imagen real.
2. Comprobar que se rechaza con un mensaje que indica los tipos permitidos.
3. Intentar adjuntar una imagen de más de 5 MB y comprobar el mensaje del
   límite.
4. Comprobar que el título, la descripción y los adjuntos válidos se conservan.

### Escenario 6 — Todo o nada en adjuntos (HU-2, CE-008)

1. Seleccionar dos adjuntos válidos.
2. Provocar un fallo en uno de ellos (por ejemplo, un archivo con extensión
   `.png` y firma binaria inválida).
3. Comprobar que no se crea ningún ticket, que no quedan archivos temporales y
   que el formulario conserva los datos.
4. Reintentar con archivos válidos y comprobar que se crea un único ticket.

### Escenario 7 — Duplicado (CE-006)

1. Crear un ticket con un título y descripción.
2. Volver a enviar exactamente el mismo título y descripción (doble clic o
   reenvío posterior), incluso en paralelo.
3. Comprobar que se devuelve el mismo número de ticket, que la interfaz lo
   indica como duplicado, que los adjuntos del segundo envío se descartan y que
   no aparece un segundo registro en `tickets`.

### Escenario 8 — Validaciones de longitud y caracteres especiales (RF-002, RF-018)

1. Enviar un título de 4 caracteres o una descripción de 19: debe bloquearse
   con mensaje en español.
2. Enviar un título de 121 caracteres o una descripción de 5001: debe
   bloquearse con mensaje en español.
3. Enviar un título compuesto solo por espacios: debe rechazarse tras
   `strip()`.
4. Pegar código con `<script>`, acentos, emojis y saltos de línea en la
   descripción: debe guardarse y mostrarse tal cual, sin ejecutar HTML.
5. Comprobar que el contador de caracteres refleja el valor.

### Escenario 9 — Pérdida de conexión (CE-008)

1. Rellenar el formulario y desconectar la red (o detener el backend) antes de
   enviar.
2. Comprobar que se muestra un aviso de que el ticket no se ha confirmado y que
   los datos siguen en el formulario.
3. Restaurar la conexión y reintentar.
4. Comprobar que se crea un único ticket.

### Escenario 10 — Identidad no disponible

1. Llamar a la API sin `Authorization: Bearer` o con un token caducado.
2. Comprobar que la API responde `401` con
   `{"detail":{"code":"not_authenticated","message":"La sesión no es válida o ha caducado."}}`.
3. Comprobar que el frontend no permite crear tickets sin sesión.

## Criterios de aceptación cubiertos

| Escenario | Requisitos |
|-----------|------------|
| 1 | RF-001, RF-006, RF-007, RF-008, RF-009, CE-001, CE-002, CE-003 |
| 2 | RF-010, RF-011, RF-013, CE-004 |
| 3 | RF-014, CE-007 |
| 4 | RF-003, RF-004, RF-005 |
| 5 | RF-004, RF-005, CE-005 |
| 6 | RF-016, RF-017, CE-008 |
| 7 | RF-015, CE-006 |
| 8 | RF-002, RF-018 |
| 9 | RF-016, CE-008 |
| 10 | RF-001 (identidad) |

## Notas de seguridad para producción

- Validar el JWT con el secreto, emisor y audiencia reales del proveedor de
  autenticación. Nunca habilitar `AUTH_DEV_STUB_ENABLED` fuera de desarrollo.
- `ATTACHMENTS_DIR` debe apuntar fuera del contenido servido por el frontend y
  tener permisos de escritura solo para el proceso backend. En Compose se
  respalda con el volumen `ticketing_attachments`.
- Configurar CORS con el origen real del frontend, no con `*`.
- Mantener los adjuntos accesibles solo a través de la API autenticada; el
  `relative_path` no se expone al cliente.
