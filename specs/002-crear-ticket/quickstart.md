# Quickstart: Creación de tickets de incidencia

**Feature**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md) | **Contrato**: [contracts/openapi.yaml](./contracts/openapi.yaml)

Guía de validación end-to-end. No contiene la implementación; describe cómo arrancar y comprobar la funcionalidad cuando esté construida.

## Requisitos previos

- Docker y Docker Compose.
- Python 3.12.
- Node.js 18+ y npm.
- Navegador moderno.

## Puesta en marcha

### 1. Base de datos

```bash
docker compose up -d db
```

PostgreSQL queda disponible en `localhost:5432` con la base `ticketing` (usuario y contraseña definidos en `compose.yaml` para desarrollo).

### 2. Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env
alembic upgrade head
python -m app.seeds.seed
uvicorn app.main:app --reload --port 8000
```

Comprobar que la API responde:

```bash
curl -s http://localhost:8000/api/v1/priorities \
  -H "X-Employee-Id: 1" | python -m json.tool
```

Resultado esperado: lista de prioridades activas (Crítica, Alta, Media, Baja) con `level` y `color`.

### 3. Frontend

```bash
cd frontend
npm install
cp .env.example .env.local
npm run dev
```

Abrir `http://localhost:5173`. El formulario debe cargar sin errores y mostrar la cabecera "Mesa de ayuda".

## Variables de entorno

Backend (`.env`, basado en `.env.example`):

| Variable | Ejemplo | Uso |
|----------|---------|-----|
| `DATABASE_URL` | `postgresql+psycopg://ticketing:ticketing@localhost:5432/ticketing` | Conexión a PostgreSQL |
| `ATTACHMENTS_DIR` | `./attachments` | Carpeta local de adjuntos |
| `CORS_ORIGINS` | `http://localhost:5173` | Origen permitido en desarrollo |

Frontend (`.env.local`, basado en `.env.example`):

| Variable | Ejemplo | Uso |
|----------|---------|-----|
| `VITE_API_BASE_URL` | `http://localhost:8000/api/v1` | Base de la API |
| `VITE_DEV_EMPLOYEE_ID` | `1` | Empleado demo para la cabecera `X-Employee-Id` |

No hay secretos reales en los archivos de ejemplo.

## Pruebas automatizadas

```bash
# Backend: pytest inicia un PostgreSQL embebido automáticamente con pgserver.
cd backend
pytest

# Frontend
cd frontend
npm run test
npm run build
```

Resultado esperado: todas las pruebas en verde.

## Escenarios de validación manual

### Escenario 1 — Creación correcta (HU-1, CE-001, CE-002, CE-003)

1. Abrir el formulario.
2. Introducir título `No puedo conectarme a la VPN` y descripción `Desde esta mañana, al conectar la VPN recibo un error de autenticación y no puedo acceder a los recursos internos.`
3. Esperar la sugerencia: debe aparecer una categoría asignada (previsiblemente "Red y conectividad") y una prioridad editable.
4. Enviar.
5. Comprobar:
   - Se muestra un número con formato `TK-000001`.
   - La confirmación muestra el estado "Abierto", el creador y la fecha/hora.
   - En base de datos existe un registro en `tickets` y otro en `ticket_events` con `event_type = 'created'`.

### Escenario 2 — Sugerencia y prioridad editable (HU-3)

1. Escribir una descripción con términos reconocibles (`wifi`, `vpn`, `contraseña`, etc.).
2. Comprobar que la categoría aparece fijada (sin selector) y con etiqueta de sugerencia.
3. Cambiar la prioridad en el selector y enviar.
4. Comprobar que el ticket se crea con la prioridad elegida y la categoría sugerida.

### Escenario 3 — Sin sugerencia y fallback (HU-3, CE-007)

1. Escribir un título y descripción neutros, sin palabras clave (`Necesito ayuda con una gestión`, `Me gustaría que alguien revise este asunto cuando sea posible, gracias.`).
2. Comprobar que se muestran los valores por defecto (categoría "Otros" y prioridad "Media").
3. Enviar y comprobar que el ticket se crea sin bloqueo.

### Escenario 4 — Adjuntos válidos (HU-2)

1. Adjuntar 1–5 imágenes PNG/JPG/GIF de menos de 5 MB.
2. Comprobar las miniaturas y que se pueden quitar antes de enviar.
3. Enviar.
4. Comprobar que la confirmación lista los adjuntos y que los archivos existen en `ATTACHMENTS_DIR/attachments/TK-XXXXXX/`.

### Escenario 5 — Adjunto inválido (HU-2, CE-005)

1. Intentar adjuntar un PDF o un archivo renombrado a `.png` que no sea una imagen real.
2. Comprobar que se rechaza con un mensaje que indica los tipos permitidos.
3. Intentar adjuntar una imagen de más de 5 MB y comprobar el mensaje del límite.
4. Comprobar que el título, la descripción y los adjuntos válidos se conservan.

### Escenario 6 — Todo o nada en adjuntos (HU-2, CE-008)

1. Seleccionar dos adjuntos válidos.
2. Provocar un fallo en uno de ellos (por ejemplo, detener el backend justo después de iniciar el envío o usar un archivo que falle la validación de firma).
3. Comprobar que no se crea ningún ticket y que el formulario conserva los datos.
4. Reintentar con archivos válidos y comprobar que se crea un único ticket.

### Escenario 7 — Duplicado (CE-006)

1. Crear un ticket con un título y descripción.
2. Volver a enviar exactamente el mismo título y descripción (doble clic o reenvío posterior).
3. Comprobar que se devuelve el mismo número de ticket, que la interfaz lo indica como duplicado y que no aparece un segundo registro en `tickets`.

### Escenario 8 — Validaciones de longitud y caracteres especiales (RF-002, RF-018)

1. Enviar un título de 4 caracteres o una descripción de 19: debe bloquearse con mensaje en español.
2. Enviar un título de 121 caracteres o una descripción de 5001: debe bloquearse con mensaje en español.
3. Pegar código con `<script>`, acentos, emojis y saltos de línea en la descripción: debe guardarse y mostrarse tal cual, sin ejecutar HTML.
4. Comprobar que el contador de caracteres refleja el valor.

### Escenario 9 — Pérdida de conexión (CE-008)

1. Rellenar el formulario y desconectar la red (o detener el backend) antes de enviar.
2. Comprobar que se muestra un aviso de que el ticket no se ha confirmado y que los datos siguen en el formulario.
3. Restaurar la conexión y reintentar.
4. Comprobar que se crea un único ticket.

### Escenario 10 — Identidad no disponible

1. Abrir el frontend sin `VITE_DEV_EMPLOYEE_ID` o llamar a la API sin `X-Employee-Id`.
2. Comprobar que la API responde 401 con un mensaje claro y que el formulario no permite enviar.

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

- `X-Employee-Id` debe ser inyectada por un gateway o middleware de autenticación de confianza. No aceptar esta cabecera directamente desde Internet.
- `ATTACHMENTS_DIR` debe apuntar a una ruta fuera del directorio servido por el frontend y con permisos de escritura solo para el proceso backend.
- Configurar CORS con el origen real del frontend, no con `*`.
