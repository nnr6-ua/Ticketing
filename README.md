# Ticketing · Mesa de ayuda

Aplicación web de mesa de ayuda con backend **FastAPI**, frontend **Vue 3** y
**PostgreSQL 16**. El proyecto está preparado para arrancar de forma reproducible
con Docker Compose: base de datos, migraciones, API y SPA se levantan juntos sin
instalar Python, Node ni PostgreSQL en la máquina.

## Arranque rápido

Requisitos: Docker Engine 24+ y Docker Compose v2.

```bash
# 1. (Opcional) Crea tu configuración local a partir del ejemplo.
cp .env.example .env
# En Windows PowerShell: Copy-Item .env.example .env

# 2. Levanta todos los servicios. La primera vez construye las imágenes.
docker compose up
```

Cuando los contenedores estén sanos:

| Servicio | URL | Descripción |
|----------|-----|-------------|
| Frontend | <http://localhost:8080> | Aplicación Vue servida por Nginx |
| API      | <http://localhost:8000> | FastAPI |
| Swagger  | <http://localhost:8000/docs> | Documentación interactiva de la API |
| PostgreSQL | `db:5432` (solo red interna) | Base de datos |

Para ejecutarlo en segundo plano:

```bash
docker compose up --build -d
docker compose ps
docker compose logs -f backend
```

`docker compose up` sin `--build` también funciona la primera vez: Compose
construye las imágenes que aún no existen. Usa `--build` después de cambiar
código, dependencias o el Dockerfile.

> La autenticación se delega en un proveedor JWT externo. Para pruebas locales,
> Compose habilita un stub de autenticación que permite entrar desde `/login`
> sin proveedor externo (ver «Acceso de desarrollo»). Para usar un proveedor
> real, define `JWT_SECRET` (y, si aplica, `AUTH_ISSUER` y `AUTH_AUDIENCE`) en
> `.env` y desactiva `AUTH_DEV_STUB_ENABLED`. Sin secreto, la API arranca
> correctamente pero devuelve `401` en las peticiones autenticadas.

## Servicios y arquitectura

```text
Navegador
   │  http://localhost:8080
   ▼
┌─────────────────────────┐        /api/*         ┌──────────────────────┐
│ frontend (Nginx)        │ ────────────────────▶ │ backend (FastAPI)    │
│ SPA Vue + proxy /api    │                       │ Uvicorn + Alembic    │
└─────────────────────────┘                       └──────────┬───────────┘
                                                             │ SQL
                                                             ▼
                                                  ┌──────────────────────┐
                                                  │ db (PostgreSQL 16)   │
                                                  │ volumen db_data      │
                                                  └──────────────────────┘
```

- **frontend**: imagen multi-etapa. `node:20-alpine` compila la SPA con Vite y
  `nginx:1.27-alpine` la sirve. Nginx resuelve las rutas de Vue (`try_files`) y
  hace de proxy inverso de `/api/` hacia `backend:8000`, por lo que el navegador
  trabaja en un solo origen y no necesita CORS.
- **backend**: imagen multi-etapa con Python 3.12. Las dependencias se instalan
  en un virtualenv en la etapa de construcción; la imagen final ejecuta como
  usuario `app` sin privilegios. El entrypoint aplica `alembic upgrade head`
  con reintentos y después lanza Uvicorn.
- **db**: PostgreSQL 16 con healthcheck. No publica el puerto en el host; el
  backend accede por la red interna de Compose.

## Configuración por variables de entorno

Copia `.env.example` a `.env` y ajusta los valores. Compose lee `.env`
automáticamente. Las variables principales son:

| Variable | Por defecto | Uso |
|----------|-------------|-----|
| `FRONTEND_PORT` | `8080` | Puerto del host para la SPA |
| `BACKEND_PORT` | `8000` | Puerto del host para la API |
| `POSTGRES_DB` | `ticketing` | Nombre de la base de datos |
| `POSTGRES_USER` | `ticketing` | Usuario de PostgreSQL |
| `POSTGRES_PASSWORD` | `ticketing` | Contraseña de PostgreSQL |
| `DATABASE_URL` | Construida por Compose | URL SQLAlchemy; permite apuntar a una base externa |
| `APP_ENV` | `production` | Entorno de la aplicación |
| `JWT_SECRET` | vacío | Secreto para validar los JWT |
| `JWT_ALGORITHM` | `HS256` | Algoritmo de firma |
| `AUTH_ISSUER` | vacío | Emisor esperado del token |
| `AUTH_AUDIENCE` | vacío | Audiencia esperada del token |
| `AUTH_DEV_STUB_ENABLED` | `true` | Habilita el login falso de desarrollo; poner `false` fuera de local |
| `FRONTEND_ORIGINS` | `http://localhost:8080` | Orígenes CORS, separados por coma |
| `MIGRATION_MAX_ATTEMPTS` | `30` | Reintentos de migración al arrancar |
| `MIGRATION_RETRY_SECONDS` | `2` | Espera entre reintentos |
| `VITE_API_BASE_URL` | vacío | URL del API compilada en la SPA; vacío = mismo origen |

`VITE_API_BASE_URL` se hornea en el bundle durante la construcción. Si cambias
su valor, reconstruye el frontend:

```bash
docker compose build frontend
docker compose up -d frontend
```

No se incluyen secretos reales en el repositorio. `.env` está ignorado por Git;
solo se versiona `.env.example`.

> PostgreSQL solo aplica `POSTGRES_PASSWORD` al inicializar un volumen vacío. Si
> cambias la contraseña después del primer arranque, actualízala también dentro
> de la base (`ALTER USER ... WITH PASSWORD ...`) o recrea el volumen con
> `docker compose down -v`. Si la contraseña contiene caracteres reservados de
> URL (`@`, `:`, `/`, `#`, etc.), codifícala en `DATABASE_URL`.

## Persistencia de datos

PostgreSQL guarda sus datos en el volumen nombrado `ticketing_db_data`
(declarado como `db_data` en `docker-compose.yml`). Los datos sobreviven a
`docker compose down` y a la recreación de contenedores.

```bash
# Detener y eliminar contenedores, conservando la base de datos.
docker compose down

# Detener y borrar también el volumen: se pierden todos los datos.
docker compose down -v

# Abrir una consola SQL.
docker compose exec db sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB"'
```

Las migraciones de Alembic se aplican automáticamente en cada arranque del
backend (`backend/docker/entrypoint.sh`), por lo que no hay pasos manuales de
inicialización.

## Datos de demostración (opcional)

El proyecto incluye un seed determinista e idempotente para validar la cola de
trabajo. Con los servicios levantados:

```bash
docker compose exec backend python scripts/seed_dev.py
```

El seed crea técnicos, prioridades, categorías y tickets de ejemplo. No se
ejecuta automáticamente en producción.

## Acceso de desarrollo (solo local)

Con `AUTH_DEV_STUB_ENABLED=true` (valor por defecto en `docker-compose.yml`),
el backend expone un endpoint temporal de login falso:

```bash
curl -s -X POST http://localhost:8000/api/v1/dev/login \
  -H "Content-Type: application/json" \
  -d '{"email": "tecnico.a@example.com"}'
```

La respuesta incluye un `access_token` JWT válido para ese usuario. La forma
más cómoda de usarlo es abrir `http://localhost:8080/login`, elegir un usuario
del seed en «Acceso de desarrollo» y pulsar «Entrar con token de prueba»: la
SPA guarda el token en `localStorage` y redirige a la cola de trabajo.

Usuarios disponibles tras ejecutar el seed: `tecnico.a@example.com`,
`tecnico.b@example.com`, `tecnico.c@example.com`, `tecnico.d@example.com`,
`supervisor@example.com` y `usuario@example.com`. Los dos últimos permiten
comprobar el `403` de roles no autorizados.

> El stub es una herramienta exclusiva de desarrollo. Si `JWT_SECRET` está
> vacío, el entrypoint genera un secreto efímero en cada arranque: los tokens
> dejan de ser válidos al reiniciar el backend y basta con volver a entrar.
> Para desactivarlo, define `AUTH_DEV_STUB_ENABLED=false` y configura un
> `JWT_SECRET` real.

## Comandos habituales

```bash
# Arrancar y reconstruir si cambió el código.
docker compose up --build

# Arrancar en segundo plano.
docker compose up -d

# Ver estado y salud de los servicios.
docker compose ps

# Seguir logs de un servicio.
docker compose logs -f backend
docker compose logs -f frontend
docker compose logs -f db

# Reiniciar un servicio.
docker compose restart backend

# Ejecutar comandos dentro de un contenedor.
docker compose exec backend alembic current
docker compose exec backend alembic history
docker compose exec backend python -c "import app.main; print('ok')"

# Detener sin borrar datos.
docker compose down

# Detener y borrar contenedores, redes y volumen de datos.
docker compose down -v
```

## Pruebas

Las pruebas no forman parte de las imágenes finales. Ejecútalas en el entorno
local habitual:

```bash
# Backend
cd backend
python -m venv .venv
# Windows: .venv\Scripts\activate
# Linux/macOS: source .venv/bin/activate
pip install -r requirements.txt
pytest -q

# Frontend
cd frontend
npm ci
npm run test:unit
npm run test:components
```

La compilación de producción del frontend (`npm run build`) se ejecuta también
durante la construcción de la imagen, de modo que un error de TypeScript o de
Vite detiene el build de Docker.

## Desarrollo sin contenedores

Si se prefiere el flujo nativo, los comandos son:

```bash
# Backend (requiere PostgreSQL accesible y DATABASE_URL)
cd backend
python -m venv .venv
pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --reload --port 8000

# Frontend
cd frontend
npm ci
npm run dev
```

En ese caso el frontend de Vite escucha en `http://localhost:5173` y su proxy
de desarrollo redirige `/api` a `http://localhost:8000`.

## Solución de problemas

| Síntoma | Comprobación |
|---------|--------------|
| `port is already allocated` | Cambia `FRONTEND_PORT` o `BACKEND_PORT` en `.env`. |
| El backend reinicia en bucle | Revisa `docker compose logs backend`; suele ser `DATABASE_URL` mal formada o PostgreSQL aún no listo. |
| `401` en la aplicación | Entra desde `/login` con el stub de desarrollo o define `JWT_SECRET` y usa un token válido del proveedor de autenticación. |
| `/api/v1/dev/login` devuelve 404 | Comprueba que `AUTH_DEV_STUB_ENABLED=true` y reinicia el backend. |
| El login de desarrollo dice que el usuario no existe | Ejecuta el seed con `docker compose exec backend python scripts/seed_dev.py`. |
| El frontend llama a otro origen | Revisa `VITE_API_BASE_URL`; con el valor vacío usa el proxy de Nginx. Si lo cambiaste, reconstruye la imagen. |
| Quiero empezar de cero | `docker compose down -v` y vuelve a levantar. |
| La base no refleja una migración nueva | `docker compose build backend && docker compose up -d backend`; el entrypoint aplica `alembic upgrade head`. |

## Documentación de la funcionalidad

- Especificación del sistema: [`specs/001-helpdesk-ticketing/spec.md`](specs/001-helpdesk-ticketing/spec.md)
- Cola de trabajo priorizada (HU-04): [`specs/004-prioritized-work-queue/spec.md`](specs/004-prioritized-work-queue/spec.md)
- Plan técnico: [`specs/004-prioritized-work-queue/plan.md`](specs/004-prioritized-work-queue/plan.md)
- Guía de validación: [`specs/004-prioritized-work-queue/quickstart.md`](specs/004-prioritized-work-queue/quickstart.md)
