from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routes import priorities, suggestions, tickets
from app.core.config import settings
from app.core.errors import AppError


@asynccontextmanager
async def lifespan(_: FastAPI):
    settings.attachments_dir.mkdir(parents=True, exist_ok=True)
    yield


app = FastAPI(title="Mesa de ayuda", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(AppError)
async def app_error_handler(_, exc: AppError) -> JSONResponse:
    return JSONResponse(status_code=exc.status_code, content=exc.payload())


@app.exception_handler(HTTPException)
async def http_error_handler(_, exc: HTTPException) -> JSONResponse:
    if isinstance(exc.detail, dict) and "error" in exc.detail:
        content = exc.detail
    else:
        content = {
            "error": {
                "code": "http_error",
                "message": str(exc.detail),
            }
        }
    return JSONResponse(status_code=exc.status_code, content=content, headers=exc.headers)


@app.exception_handler(RequestValidationError)
async def validation_error_handler(_, exc: RequestValidationError) -> JSONResponse:
    first = exc.errors()[0] if exc.errors() else {}
    location = [str(part) for part in first.get("loc", []) if part not in ("body", "query", "path")]
    return JSONResponse(
        status_code=422,
        content={
            "error": {
                "code": "validation_error",
                "message": first.get("msg", "Datos inválidos."),
                "field": ".".join(location) if location else None,
            }
        },
    )


@app.get("/health", tags=["health"])
def health() -> dict[str, str]:
    return {"status": "ok"}


app.include_router(priorities.router, prefix="/api/v1")
app.include_router(suggestions.router, prefix="/api/v1")
app.include_router(tickets.router, prefix="/api/v1")
