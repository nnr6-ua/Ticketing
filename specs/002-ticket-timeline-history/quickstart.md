# Quickstart: Seguimiento de la evolución del ticket (estado y línea temporal)

**Feature**: `002-ticket-timeline-history`
**Date**: 2026-11-13
**Spec**: `specs/002-ticket-timeline-history/spec.md`

## Purpose

Runnable validation scenarios that prove the feature works end-to-end: a ticket
creator can view the current status and the full chronological timeline of their
own ticket (status changes, resolutions, and public technician comments), while
internal technician comments stay hidden and other users cannot read the ticket.

This is a validation/run guide. It references the contracts and data model
without duplicating them. Implementation details (service bodies, migrations,
complete test suites) belong in `tasks.md` and the implementation phase.

## Prerequisites

- Backend running (FastAPI) against a PostgreSQL database with the HU-05 schema
  already migrated (`tickets`, `ticket_timeline_entries`, `users`, enums).
- A JWT token for an authenticated user who is the creator of an existing ticket.
- Frontend built/served (Vue 3 + Vite) pointing at the backend API base URL.
- At least one ticket in a non-`cerrado` state with timeline entries created by
  HU-05 (status changes, a resolution, and at least one public and one internal
  technician comment).

## Backend validation scenarios

Run against `http://localhost:8000` (adjust host/port as configured). Replace
`<TICKET_ID>` with a ticket owned by the authenticated user and `<JWT_TOKEN>` with
a valid bearer token.

### Scenario 1: Ticket creator reads current status

Request:

```http
GET /api/v1/tickets/<TICKET_ID>
Authorization: Bearer <JWT_TOKEN>
```

Expected outcome:

- HTTP 200.
- Body contains `ticket.number`, `ticket.title`, `ticket.status` (the last
  registered status), `ticket.creator_id` equals the authenticated user id, and
  `ticket.allowed_transitions` lists the permitted destination states per HU-05.

### Scenario 2: Ticket creator reads the full timeline

Request:

```http
GET /api/v1/tickets/<TICKET_ID>/timeline?page=1&page_size=50
Authorization: Bearer <JWT_TOKEN>
```

Expected outcome:

- HTTP 200.
- `items` contains one entry per timeline event, ordered chronologically
  (`created_at` ascending, then `event_order`, then `id`).
- Each entry shows `type` (`status_change`, `resolution`, or `internal_comment`),
  `author` (id, name, role), `created_at`, and, for `status_change`,
  `from_status`/`to_status`; for `resolution`, `body`; for public comments,
  `body`.
- Entries with `is_internal = true` are NOT present in `items`.
- `pagination.total_items`, `pagination.total_pages`, `pagination.has_next`,
  `pagination.has_previous` are consistent.

### Scenario 3: Non-creator cannot read the ticket

Request: same as Scenario 1 or 2 with a JWT token of a user who is not the
ticket creator and has no `tecnico`/`supervisor`/`admin` role.

Expected outcome:

- HTTP 403 (or 404 to avoid leaking existence), body
  `{"detail": {"code": "...", "message": "..."}}` in Spanish.
- No status or timeline data is returned.

### Scenario 4: Internal comments are never returned to the creator

Request: Scenario 2 with a ticket that has at least one internal technician
comment (`is_internal = true`).

Expected outcome:

- HTTP 200 and `items` contains no entry with `is_internal = true`.
- Internal comments remain visible only to the assigned technician, supervisors
  and admins (covered by HU-05 permission tests).

## Frontend validation scenarios

Open the ticket detail page in the browser as the ticket creator.

### Scenario 5: Status and timeline render in the UI

Expected outcome:

- The page shows the ticket number, title and current status label (es-ES,
  e.g. "En progreso").
- A chronological timeline lists each event with author name/role and date/time
  shown in Europe/Madrid.
- Timeline entries are visually distinguishable by type (status change,
  resolution, comment).
- No internal technician comment appears in the timeline.
- When there are no entries, an empty-state message is shown instead of a blank
  list.

### Scenario 6: Pagination works

Expected outcome:

- With more entries than one page, page controls appear and navigating pages
  loads the next set of entries without reloading the whole page.

## Commands

Backend (from `backend/`):

```bash
# Install dependencies
pip install -r requirements.txt

# Run backend
uvicorn app.main:app --reload

# Run backend tests (contract + integration for timeline visibility)
pytest tests/contract tests/integration -q
```

Frontend (from `frontend/`):

```bash
# Install dependencies
npm install

# Run frontend tests
npm test

# Build for production
npm run build
```

## Expected outcomes (Definition of Done for validation)

- The ticket creator sees the current status and the complete chronological
  timeline of their ticket without contacting the technician.
- Internal technician comments are never visible to the ticket creator.
- Users cannot read tickets they did not create (unless they hold an operative
  role).
- Timeline entries include author and date/time; are ordered chronologically.
- Responses are in Spanish; dates display in Europe/Madrid.
- Backend p95 for status/timeline reads is under 300 ms.

## References

- Feature specification: `spec.md`
- Data model: `data-model.md`
- API contract: `contracts/ticket-timeline.query.openapi.yaml`
- Related feature (writing side): `specs/005-cambio-estado-resolucion/spec.md`
