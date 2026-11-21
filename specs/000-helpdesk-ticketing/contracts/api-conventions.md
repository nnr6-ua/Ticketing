# Convenciones de API — Spec `000`

## Base

- Prefijo: `/api/v1`.
- Autenticación: `Authorization: Bearer <JWT>`.
- CORS: orígenes configurables; métodos permitidos `GET` y `POST`; cabeceras `Authorization`, `Accept`, `Content-Type`; respuesta con `Vary: Authorization` cuando proceda.
- Idioma: español de España en mensajes y ejemplos.

## Formato de error

```json
{
  "detail": {
    "code": "invalid_request",
    "message": "La solicitud no es válida. Revisa los datos e inténtalo de nuevo."
  }
}
```

Códigos compartidos: `not_authenticated` (401), `forbidden` (403), `not_found` (404), `invalid_request` (422), `conflict` (409), `internal_error` (500). Cada historia puede añadir códigos específicos documentados en su contrato.

## Convenciones de respuesta

- Las colecciones incluyen `items` y `pagination` cuando aplique.
- Las fechas se serializan en ISO 8601 con zona horaria; la interfaz las muestra en `Europe/Madrid`.
- Los identificadores son UUID salvo el número de ticket (`TK-000001`).
- Los agregados del dashboard usan `data`, `meta` y `filters` con nulabilidad explícita.

## Endpoints por historia

| Historia | Recurso principal |
|---|---|
| HU-01 | `GET /priorities`, `POST /suggestions`, `POST /tickets` |
| HU-02 | `GET /tickets/{id}/timeline`, `GET /my-tickets` |
| HU-03 | `POST /tickets/{id}/information-request`, `POST /tickets/{id}/information-response`, `GET /notifications` |
| HU-04 | `GET /work-queue` |
| HU-05 | `POST /tickets/{id}/status-transitions`, `POST /tickets/{id}/resolution` |
| HU-06 | `POST /tickets/{id}/assignee`, `POST /tickets/{id}/escalation` |
| HU-07 | `GET /sla-dashboard`, `GET /sla-dashboard/options` |
| HU-08 | `GET/POST/PATCH/DELETE /admin/categories`, `/admin/priorities`, `/admin/sla-rules`, `GET /admin/history` |

Las rutas definitivas son las de cada contrato; esta tabla es un índice de consistencia, no una sustitución del OpenAPI.
