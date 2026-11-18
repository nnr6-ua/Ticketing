"""Servicio de solo lectura del dashboard de cumplimiento de SLA (HU-07).

El módulo es un consumidor puro de los datos existentes:

* una única sentencia ``SELECT`` sobre ``tickets``, ``priorities``,
  ``categories``, la primera entrada ``status_change -> resuelto`` de
  ``ticket_timeline_entries`` y el ``users`` del técnico atribuido (solo
  lectura) construye la proyección ``poblacion``;
* las agregaciones (resumen, matriz, totales y ranking) se calculan en memoria
  sobre esa misma proyección, de forma pura y determinista.

No se escribe nunca en la base de datos ni se recalcula el SLA con el catálogo
vigente: se usa el límite histórico estampado en cada ticket.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import NamedTuple
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy import Select, String, func, or_, select
from sqlalchemy.orm import Session, aliased

from app.core.errors import ApiError
from app.models import (
    Category,
    Priority,
    Ticket,
    TicketStatus,
    TicketTimelineEntry,
    TimelineEventType,
    User,
)
from app.schemas.sla_dashboard import (
    ComplianceMetrics,
    EffectiveFilters,
    FilterCategoryOption,
    FilterPriorityOption,
    MatrixRow,
    RankingBlock,
    RankingEntry,
    SlaDashboardData,
    SlaDashboardMeta,
    SlaDashboardOptions,
    SlaDashboardResponse,
    Thresholds,
    TotalsEntry,
)
from app.utils.sla import (
    SLA_AMBER_THRESHOLD_PCT,
    SLA_GREEN_THRESHOLD_PCT,
    as_utc,
    compliance_band,
)

MADRID = ZoneInfo("Europe/Madrid")
UTC = timezone.utc
SIN_CATEGORIA = "Sin categoría"
SIN_ASIGNAR = "Sin asignar"
DEFAULT_PERIOD_DAYS = 30
INVALID_REQUEST_MESSAGE = "Revisa los filtros e inténtalo de nuevo."
INVALID_DATE_RANGE_MESSAGE = (
    "La fecha inicial no puede ser posterior a la fecha final."
)

_ONE_DECIMAL = Decimal("0.1")


# ---------------------------------------------------------------------------
# Filtros de entrada
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class DashboardQuery:
    """Filtros tal y como llegan de la query string (sin validar)."""

    desde: str | None = None
    hasta: str | None = None
    categorias: str | None = None
    prioridades: str | None = None


@dataclass(frozen=True)
class DashboardFilters:
    """Filtros validados y fechas efectivas del dashboard."""

    desde: date
    hasta: date
    categorias: list[str] = field(default_factory=list)
    prioridades: list[int] = field(default_factory=list)


def _parse_date(value: str | None) -> date | None:
    if value is None or not value.strip():
        return None
    try:
        return date.fromisoformat(value.strip())
    except ValueError as exc:
        raise ApiError(422, "invalid_request", INVALID_REQUEST_MESSAGE) from exc


def _parse_categorias(value: str | None) -> list[str]:
    if value is None or not value.strip():
        return []
    parsed: list[str] = []
    for part in value.split(","):
        token = part.strip()
        if not token:
            raise ApiError(422, "invalid_request", INVALID_REQUEST_MESSAGE)
        if token == "sin_categoria":
            normalized = token
        else:
            try:
                normalized = str(UUID(token))
            except (TypeError, ValueError) as exc:
                raise ApiError(
                    422, "invalid_request", INVALID_REQUEST_MESSAGE
                ) from exc
        if normalized not in parsed:
            parsed.append(normalized)
    return parsed


def _parse_prioridades(value: str | None) -> list[int]:
    if value is None or not value.strip():
        return []
    parsed: list[int] = []
    for part in value.split(","):
        token = part.strip()
        if not token or not token.isdigit() or not 1 <= int(token) <= 4:
            raise ApiError(422, "invalid_request", INVALID_REQUEST_MESSAGE)
        level = int(token)
        if level not in parsed:
            parsed.append(level)
    return sorted(parsed)


def resolve_period(
    desde: date | None,
    hasta: date | None,
    *,
    now: datetime | None = None,
) -> tuple[date, date, datetime, datetime, datetime]:
    """Resuelve el periodo efectivo y su semirrango UTC.

    Los días naturales se interpretan en ``Europe/Madrid``. El rango es
    ``[desde 00:00 Madrid, (hasta + 1 día) 00:00 Madrid)`` en UTC.
    """

    ahora = as_utc(now) if now is not None else datetime.now(UTC)
    today_madrid = ahora.astimezone(MADRID).date()

    effective_desde = desde or (today_madrid - timedelta(days=DEFAULT_PERIOD_DAYS - 1))
    effective_hasta = hasta or today_madrid

    if effective_desde > effective_hasta:
        raise ApiError(422, "invalid_date_range", INVALID_DATE_RANGE_MESSAGE)

    start_local = datetime.combine(effective_desde, time.min, tzinfo=MADRID)
    end_local = datetime.combine(
        effective_hasta + timedelta(days=1), time.min, tzinfo=MADRID
    )
    desde_utc = start_local.astimezone(UTC)
    hasta_utc = end_local.astimezone(UTC)
    return effective_desde, effective_hasta, desde_utc, hasta_utc, ahora


def parse_filters(
    query: DashboardQuery, *, now: datetime | None = None
) -> tuple[DashboardFilters, datetime, datetime, datetime]:
    """Valida los filtros y devuelve también el semirrango UTC y ``ahora``."""

    desde = _parse_date(query.desde)
    hasta = _parse_date(query.hasta)
    categorias = _parse_categorias(query.categorias)
    prioridades = _parse_prioridades(query.prioridades)

    effective_desde, effective_hasta, desde_utc, hasta_utc, ahora = resolve_period(
        desde, hasta, now=now
    )
    return (
        DashboardFilters(
            desde=effective_desde,
            hasta=effective_hasta,
            categorias=categorias,
            prioridades=prioridades,
        ),
        desde_utc,
        hasta_utc,
        ahora,
    )


# ---------------------------------------------------------------------------
# Proyección ``poblacion``
# ---------------------------------------------------------------------------
class PopulationTicket(NamedTuple):
    """Un ticket de la población con sus métricas derivadas (no persistidas).

    ``technician_name``, ``team`` e ``is_active`` llegan de la misma
    proyección ``poblacion`` (un único join a ``users``), de modo que el
    ranking no necesita ninguna consulta adicional.
    """

    priority_id: str
    priority_level: int
    priority_name: str
    priority_is_active: bool
    category_id: str | None
    category_name: str
    category_is_active: bool | None
    con_sla: bool
    atendido: bool
    atendido_con_sla: bool
    dentro_de_plazo: bool
    vencido: bool
    tiempo_respuesta_s: float | None
    retraso_s: float | None
    atribuido_a: str | None
    technician_name: str = SIN_ASIGNAR
    team: str | None = None
    is_active: bool | None = None


POPULATION_COLUMNS = (
    "atribuido_a",
    "created_at",
    "sla_deadline",
    "priority_id",
    "priority_level",
    "priority_name",
    "priority_is_active",
    "category_id",
    "category_name",
    "category_is_active",
    "primera_finalizacion",
    "technician_name",
    "technician_team",
    "technician_is_active",
)
"""Orden de columnas de la proyección ``poblacion``.

``_derive_values`` desempaqueta cada fila por posición en este mismo orden, de
modo que la sentencia y la derivación no pueden desalinearse sin que lo detecte
el test que compara esta tupla con las columnas seleccionadas.
"""


def _first_resolution_subquery(column):
    """Primera entrada ``status_change -> resuelto`` de un ticket.

    El orden determinista es ``(created_at, event_order, id)`` y se apoya en el
    índice ``ix_timeline_ticket_created``. La subconsulta es correlacionada y
    de solo lectura.
    """

    return (
        select(column)
        .where(
            TicketTimelineEntry.ticket_id == Ticket.id,
            TicketTimelineEntry.event_type == TimelineEventType.status_change,
            TicketTimelineEntry.to_status == TicketStatus.resuelto,
        )
        .order_by(
            TicketTimelineEntry.created_at.asc(),
            TicketTimelineEntry.event_order.asc(),
            TicketTimelineEntry.id.asc(),
        )
        .limit(1)
        .scalar_subquery()
    )


def _population_statement(
    filters: DashboardFilters,
    desde_utc: datetime,
    hasta_utc: datetime,
) -> Select:
    """Construye la única ``SELECT`` de población, en modo solo lectura.

    El técnico que recibe un ticket vencido se resuelve en esta misma sentencia
    con un único ``LEFT JOIN`` a ``users``: la clave es el autor de la primera
    finalización y, si no lo hay, el responsable vigente. Así la proyección ya
    trae nombre, equipo y estado activo del técnico atribuido y el ranking se
    construye sin una segunda consulta a la base de datos (R6).

    La subconsulta correlacionada localiza solo el ``id`` de la primera entrada
    ``status_change -> resuelto``; la entrada se une después por clave primaria
    y de ella se toman tanto ``created_at`` como ``author_id``. Así la búsqueda
    ordenada sobre ``ix_timeline_ticket_created`` se evalúa una única vez por
    ticket, en lugar de dos (una por cada columna que necesita el dashboard).
    """

    first_entry = aliased(TicketTimelineEntry, name="first_entry")
    first_entry_id = _first_resolution_subquery(TicketTimelineEntry.id)
    primera_finalizacion = func.coalesce(
        first_entry.created_at, Ticket.finalized_at
    ).label("primera_finalizacion")

    technician = aliased(User, name="technician")
    technician_id = func.coalesce(first_entry.author_id, Ticket.assignee_id)

    statement = (
        select(
            func.cast(technician_id, String).label("atribuido_a"),
            Ticket.created_at.label("created_at"),
            Ticket.sla_deadline.label("sla_deadline"),
            func.cast(Priority.id, String).label("priority_id"),
            Priority.level.label("priority_level"),
            Priority.name.label("priority_name"),
            Priority.is_active.label("priority_is_active"),
            func.cast(Category.id, String).label("category_id"),
            Category.name.label("category_name"),
            Category.is_active.label("category_is_active"),
            primera_finalizacion,
            technician.name.label("technician_name"),
            technician.team.label("technician_team"),
            technician.is_active.label("technician_is_active"),
        )
        .join(Priority, Priority.id == Ticket.priority_id)
        .outerjoin(Category, Category.id == Ticket.category_id)
        .outerjoin(first_entry, first_entry.id == first_entry_id)
        .outerjoin(technician, technician.id == technician_id)
        .where(Ticket.created_at >= desde_utc)
        .where(Ticket.created_at < hasta_utc)
    )

    if filters.categorias:
        category_ids: list[UUID] = []
        include_sin_categoria = False
        for value in filters.categorias:
            if value == "sin_categoria":
                include_sin_categoria = True
            else:
                category_ids.append(UUID(value))
        conditions = []
        if category_ids:
            conditions.append(Ticket.category_id.in_(category_ids))
        if include_sin_categoria:
            conditions.append(Ticket.category_id.is_(None))
        statement = statement.where(or_(*conditions))

    if filters.prioridades:
        statement = statement.where(Priority.level.in_(filters.prioridades))

    return statement


def _utc(value: datetime) -> datetime:
    """Normaliza a UTC con un camino rápido para los valores habituales."""

    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    if value.tzinfo is UTC:
        return value
    return value.astimezone(UTC)


def _derive_values(row, ahora: datetime, ahora_naive: datetime | None):
    """Deriva los indicadores de SLA de una fila en el orden de la proyección.

    ``row`` es cualquier secuencia con las columnas de ``POPULATION_COLUMNS`` en
    ese mismo orden: una ``Row`` del cursor (que se desempaqueta en C) o la
    tupla que construye ``_derive_ticket`` para objetos con atributos. Trabajar
    por posición en lugar de por nombre reduce a la mitad el coste del recorrido
    de 10.000 tickets.

    Cuando el motor devuelve fechas sin zona (SQLite), la comparación se hace
    en UTC ingenuo usando ``ahora_naive`` precalculado por el recorrido: así se
    evita crear tres ``datetime`` con zona por ticket. Con fechas con zona
    (PostgreSQL) se normaliza a UTC como antes.
    """

    (
        atribuido_a_origen,
        created_at,
        deadline,
        priority_id,
        priority_level,
        priority_name,
        priority_is_active,
        category_id,
        category_name,
        category_is_active,
        primera,
        technician_name,
        technician_team,
        technician_is_active,
    ) = row

    if created_at.tzinfo is None:
        referencia = (
            ahora_naive if ahora_naive is not None else ahora.replace(tzinfo=None)
        )
        if deadline is not None and deadline.tzinfo is not None:
            deadline = _utc(deadline).replace(tzinfo=None)
        if primera is not None and primera.tzinfo is not None:
            primera = _utc(primera).replace(tzinfo=None)
    else:
        created_at = _utc(created_at)
        if deadline is not None:
            deadline = _utc(deadline)
        if primera is not None:
            primera = _utc(primera)
        referencia = _utc(ahora)

    con_sla = deadline is not None
    atendido = primera is not None
    atendido_con_sla = atendido and con_sla
    dentro_de_plazo = bool(
        atendido_con_sla and deadline is not None and primera <= deadline
    )

    vencido = bool(
        con_sla
        and deadline is not None
        and (
            (atendido and primera > deadline)
            or (not atendido and referencia > deadline)
        )
    )

    tiempo_respuesta_s: float | None = None
    if atendido_con_sla and primera is not None:
        tiempo_respuesta_s = max(0.0, (primera - created_at).total_seconds())

    retraso_s: float | None = None
    if vencido and deadline is not None:
        if atendido and primera is not None:
            retraso_s = max(0.0, (primera - deadline).total_seconds())
        else:
            retraso_s = max(0.0, (referencia - deadline).total_seconds())

    atribuido_a: str | None = None
    nombre_tecnico = SIN_ASIGNAR
    equipo: str | None = None
    activo: bool | None = None
    if vencido:
        atribuido_a = atribuido_a_origen
        nombre_tecnico = technician_name or SIN_ASIGNAR
        equipo = technician_team
        activo = technician_is_active

    return PopulationTicket(
        priority_id,
        int(priority_level),
        priority_name,
        bool(priority_is_active),
        category_id,
        category_name or SIN_CATEGORIA,
        bool(category_is_active) if category_id is not None else None,
        con_sla,
        atendido,
        atendido_con_sla,
        dentro_de_plazo,
        vencido,
        tiempo_respuesta_s,
        retraso_s,
        atribuido_a,
        nombre_tecnico,
        equipo,
        activo,
    )


def _derive_ticket(
    row, ahora: datetime, ahora_naive: datetime | None = None
) -> PopulationTicket:
    """Deriva los indicadores de SLA de un objeto con atributos (tests).

    Reconstruye la tupla en el orden de ``POPULATION_COLUMNS`` eligiendo las
    etiquetas del técnico atribuido con la misma regla que la sentencia: autor
    de la primera finalización si existe y, si no, responsable vigente.
    """

    atendido = row.primera_finalizacion is not None
    usa_autor = bool(atendido and row.first_author_id is not None)
    atribuido_a = row.first_author_id if usa_autor else row.assignee_id
    sufijo = "author" if usa_autor else "assignee"

    return _derive_values(
        (
            atribuido_a,
            row.created_at,
            row.sla_deadline,
            row.priority_id,
            row.priority_level,
            row.priority_name,
            row.priority_is_active,
            row.category_id,
            row.category_name,
            row.category_is_active,
            row.primera_finalizacion,
            getattr(row, f"{sufijo}_name", None),
            getattr(row, f"{sufijo}_team", None),
            getattr(row, f"{sufijo}_is_active", None),
        ),
        ahora,
        ahora_naive,
    )


def iter_population(
    session: Session,
    filters: DashboardFilters,
    desde_utc: datetime,
    hasta_utc: datetime,
    ahora: datetime,
) -> Iterator[PopulationTicket]:
    """Itera la proyección derivada sin materializarla por completo.

    El resultado se consume por lotes de 1.000 filas con ``fetchmany`` en C y
    cada fila se deriva desempaquetándola por posición: con 10.000 tickets, el
    recorrido fila a fila con acceso por nombre añadía una llamada Python y una
    búsqueda de atributo por columna, y disparaba el p95 por encima del
    presupuesto de 300 ms.
    """

    statement = _population_statement(filters, desde_utc, hasta_utc)
    result = session.connection().execute(statement)
    ahora_naive = ahora.replace(tzinfo=None) if ahora.tzinfo is not None else ahora
    try:
        for partition in result.partitions(1_000):
            for row in partition:
                yield _derive_values(row, ahora, ahora_naive)
    finally:
        result.close()


def load_population(
    session: Session,
    filters: DashboardFilters,
    desde_utc: datetime,
    hasta_utc: datetime,
    ahora: datetime,
) -> list[PopulationTicket]:
    """Ejecuta la proyección y devuelve la población derivada."""

    return list(
        iter_population(session, filters, desde_utc, hasta_utc, ahora)
    )


# ---------------------------------------------------------------------------
# Agregaciones puras
# ---------------------------------------------------------------------------
def _compliance_pct(on_time: int, attended_with_sla: int) -> float | None:
    if attended_with_sla <= 0:
        return None
    value = Decimal(100 * on_time) / Decimal(attended_with_sla)
    return float(value.quantize(_ONE_DECIMAL, rounding=ROUND_HALF_UP))


class MetricsAccumulator:
    """Acumulador mutable de las métricas de cumplimiento de un conjunto.

    Es la única implementación de las fórmulas: la usan tanto las funciones
    puras sobre listas (``aggregate_metrics``, matriz y totales) como el
    recorrido en una sola pasada del snapshot, de modo que ambas rutas no
    pueden divergir.
    """

    __slots__ = (
        "ticket_count",
        "no_sla_count",
        "attended_with_sla",
        "on_time",
        "overdue_count",
        "response_seconds",
    )

    def __init__(self) -> None:
        self.ticket_count = 0
        self.no_sla_count = 0
        self.attended_with_sla = 0
        self.on_time = 0
        self.overdue_count = 0
        self.response_seconds = 0.0

    def add(self, ticket: PopulationTicket) -> None:
        self.ticket_count += 1
        if not ticket.con_sla:
            self.no_sla_count += 1
        if ticket.atendido_con_sla:
            self.attended_with_sla += 1
            if ticket.tiempo_respuesta_s is not None:
                self.response_seconds += ticket.tiempo_respuesta_s
        if ticket.dentro_de_plazo:
            self.on_time += 1
        if ticket.vencido:
            self.overdue_count += 1

    def merge(self, other: MetricsAccumulator) -> None:
        """Suma los contadores de otro acumulador (agregación aditiva).

        Los indicadores publicados se derivan siempre de estos contadores
        (proporción y media), de modo que fusionar grupos produce exactamente el
        mismo resultado que acumular sus tickets uno a uno.
        """

        self.ticket_count += other.ticket_count
        self.no_sla_count += other.no_sla_count
        self.attended_with_sla += other.attended_with_sla
        self.on_time += other.on_time
        self.overdue_count += other.overdue_count
        self.response_seconds += other.response_seconds

    def metrics(self) -> ComplianceMetrics:
        compliance_pct = _compliance_pct(self.on_time, self.attended_with_sla)
        avg_response_seconds: float | None = None
        if self.attended_with_sla:
            avg_response_seconds = (
                self.response_seconds / self.attended_with_sla
            )

        return ComplianceMetrics(
            ticket_count=self.ticket_count,
            no_sla_count=self.no_sla_count,
            attended_with_sla=self.attended_with_sla,
            on_time=self.on_time,
            compliance_pct=compliance_pct,
            avg_response_seconds=avg_response_seconds,
            overdue_count=self.overdue_count,
            semaphore=compliance_band(compliance_pct),
        )


GroupSample = tuple[PopulationTicket, MetricsAccumulator]


def accumulate_group(
    groups: dict, key, ticket: PopulationTicket
) -> None:
    """Añade un ticket a un grupo de agregación (creándolo si es el primero).

    El primer ticket del grupo se conserva como muestra de sus etiquetas
    históricas (prioridad, categoría) y el resto solo actualiza contadores.
    """

    entry = groups.get(key)
    if entry is None:
        accumulator = MetricsAccumulator()
        accumulator.add(ticket)
        groups[key] = (ticket, accumulator)
    else:
        entry[1].add(ticket)


def aggregate_metrics(tickets: list[PopulationTicket]) -> ComplianceMetrics:
    """Calcula la métrica de cumplimiento de un conjunto de tickets."""

    accumulator = MetricsAccumulator()
    for ticket in tickets:
        accumulator.add(ticket)
    return accumulator.metrics()


def _priority_sort_key(level: int, name: str) -> tuple[int, str]:
    return (level, name.casefold())


def _matrix_from_groups(
    groups: dict[tuple[str, str | None], GroupSample],
) -> list[MatrixRow]:
    """Ensambla la matriz ordenada a partir de los grupos prioridad/categoría."""

    entries: list[tuple[int, str, bool, str, MatrixRow]] = []
    for sample, accumulator in groups.values():
        metrics = accumulator.metrics()
        row = MatrixRow(
            **metrics.model_dump(),
            priority_level=sample.priority_level,
            priority_name=sample.priority_name,
            priority_is_active=sample.priority_is_active,
            category_id=sample.category_id,
            category_name=sample.category_name,
            category_is_active=sample.category_is_active,
        )
        entries.append(
            (
                sample.priority_level,
                sample.priority_name.casefold(),
                sample.category_id is None,
                sample.category_name.casefold(),
                row,
            )
        )

    entries.sort(key=lambda item: (item[0], item[1], item[2], item[3]))
    return [entry[4] for entry in entries]


def build_matrix(tickets: list[PopulationTicket]) -> list[MatrixRow]:
    """Matriz prioridad × categoría, solo con combinaciones con datos."""

    groups: dict[tuple[str, str | None], GroupSample] = {}
    for ticket in tickets:
        accumulate_group(
            groups, (ticket.priority_id, ticket.category_id), ticket
        )
    return _matrix_from_groups(groups)


def _priority_totals_from_groups(
    groups: dict[str, GroupSample],
) -> list[TotalsEntry]:
    """Ensambla los totales por prioridad a partir de sus grupos."""

    rows: list[TotalsEntry] = []
    for sample, accumulator in groups.values():
        metrics = accumulator.metrics()
        rows.append(
            TotalsEntry(
                **metrics.model_dump(),
                scope="priority",
                priority_level=sample.priority_level,
                priority_name=sample.priority_name,
                priority_is_active=sample.priority_is_active,
            )
        )
    rows.sort(
        key=lambda row: _priority_sort_key(row.priority_level or 0, row.priority_name or "")
    )
    return rows


def build_priority_totals(tickets: list[PopulationTicket]) -> list[TotalsEntry]:
    """Totales por prioridad recalculados desde los tickets subyacentes."""

    groups: dict[str, GroupSample] = {}
    for ticket in tickets:
        accumulate_group(groups, ticket.priority_id, ticket)
    return _priority_totals_from_groups(groups)


def _category_totals_from_groups(
    groups: dict[str | None, GroupSample],
) -> list[TotalsEntry]:
    """Ensambla los totales por categoría a partir de sus grupos."""

    rows: list[TotalsEntry] = []
    for sample, accumulator in groups.values():
        metrics = accumulator.metrics()
        rows.append(
            TotalsEntry(
                **metrics.model_dump(),
                scope="category",
                category_id=sample.category_id,
                category_name=sample.category_name,
                category_is_active=sample.category_is_active,
            )
        )
    rows.sort(
        key=lambda row: (
            row.category_id is None,
            (row.category_name or SIN_CATEGORIA).casefold(),
        )
    )
    return rows


def build_category_totals(tickets: list[PopulationTicket]) -> list[TotalsEntry]:
    """Totales por categoría recalculados desde los tickets subyacentes."""

    groups: dict[str | None, GroupSample] = {}
    for ticket in tickets:
        accumulate_group(groups, ticket.category_id, ticket)
    return _category_totals_from_groups(groups)


def _totals_from_matrix(
    groups: dict[tuple[str, str | None], GroupSample],
) -> tuple[list[TotalsEntry], list[TotalsEntry]]:
    """Totales por prioridad y por categoría derivados de la matriz.

    Los grupos de la matriz particionan la población por prioridad y categoría,
    y todos los contadores son aditivos, así que fusionarlos equivale a
    recorrer los tickets una segunda vez. El snapshot completo aprovecha esta
    propiedad para acumular una sola vez por ticket.
    """

    priority_merged: dict[str, GroupSample] = {}
    category_merged: dict[str | None, GroupSample] = {}

    for sample, accumulator in groups.values():
        priority_entry = priority_merged.get(sample.priority_id)
        if priority_entry is None:
            priority_total = MetricsAccumulator()
            priority_total.merge(accumulator)
            priority_merged[sample.priority_id] = (sample, priority_total)
        else:
            priority_entry[1].merge(accumulator)

        category_entry = category_merged.get(sample.category_id)
        if category_entry is None:
            category_total = MetricsAccumulator()
            category_total.merge(accumulator)
            category_merged[sample.category_id] = (sample, category_total)
        else:
            category_entry[1].merge(accumulator)

    return (
        _priority_totals_from_groups(priority_merged),
        _category_totals_from_groups(category_merged),
    )


def _canonical_id(raw: str | None) -> str | None:
    """Normaliza un identificador UUID al formato canónico con guiones.

    El motor puede devolver el UUID como texto sin guiones (SQLite) o con
    guiones (PostgreSQL). Ambas formas se reconocen sin construir un ``UUID``,
    que era el coste dominante del ranking; solo las formas inesperadas pasan
    por el analizador.
    """

    if raw is None:
        return None
    if isinstance(raw, UUID):
        return str(raw)
    if type(raw) is str:
        if len(raw) == 36:
            return raw
        if len(raw) == 32:
            return (
                f"{raw[0:8]}-{raw[8:12]}-{raw[12:16]}-"
                f"{raw[16:20]}-{raw[20:32]}"
            )
    try:
        return str(UUID(raw))
    except (TypeError, ValueError):
        return raw


class RankingAccumulator:
    """Acumulador de vencidos por técnico sobre la proyección ``poblacion``.

    El nombre, el equipo y el estado activo del técnico ya vienen de la misma
    sentencia que el resto del snapshot; este acumulador no vuelve a consultar
    ``users``.
    """

    __slots__ = ("overdue_count", "delay_seconds", "sample")

    def __init__(self, sample: PopulationTicket) -> None:
        self.overdue_count = 0
        self.delay_seconds = 0.0
        self.sample = sample

    def add(self, ticket: PopulationTicket) -> None:
        self.overdue_count += 1
        self.delay_seconds += ticket.retraso_s or 0.0


def accumulate_overdue(
    groups: dict, ticket: PopulationTicket
) -> None:
    """Añade un ticket vencido a su grupo de atribución (una sola vez).

    La clave es el identificador tal y como lo devuelve la proyección: la
    normalización al formato canónico se hace después, una vez por técnico, no
    una vez por ticket.
    """

    key = ticket.atribuido_a
    accumulator = groups.get(key)
    if accumulator is None:
        accumulator = RankingAccumulator(ticket)
        groups[key] = accumulator
    accumulator.add(ticket)


def ranking_from_groups(
    groups: dict[str | None, RankingAccumulator],
) -> RankingBlock:
    """Ensambla el ranking ordenado a partir de los grupos de atribución."""

    # El motor devuelve el mismo formato para todos los identificadores, así que
    # agrupar por el valor crudo ya es correcto; esta fusión solo unifica por si
    # llegasen formas distintas del mismo UUID.
    merged: dict[str | None, RankingAccumulator] = {}
    for raw, accumulator in groups.items():
        key = _canonical_id(raw)
        existing = merged.get(key)
        if existing is None:
            merged[key] = accumulator
        else:
            existing.overdue_count += accumulator.overdue_count
            existing.delay_seconds += accumulator.delay_seconds

    technicians: list[RankingEntry] = []
    unassigned: RankingEntry | None = None

    for attributed_to, accumulator in merged.items():
        overdue_count = accumulator.overdue_count
        avg_delay = accumulator.delay_seconds / overdue_count
        sample = accumulator.sample

        if attributed_to is None:
            unassigned = RankingEntry(
                technician_id=None,
                technician_name=SIN_ASIGNAR,
                team=None,
                is_active=None,
                overdue_count=overdue_count,
                avg_delay_seconds=avg_delay,
            )
            continue

        technicians.append(
            RankingEntry(
                technician_id=attributed_to,
                technician_name=sample.technician_name,
                team=sample.team,
                is_active=sample.is_active,
                overdue_count=overdue_count,
                avg_delay_seconds=avg_delay,
            )
        )

    technicians.sort(
        key=lambda entry: (
            -entry.overdue_count,
            -entry.avg_delay_seconds,
            entry.technician_name.casefold(),
            (entry.team or "").casefold(),
            # Desempate final por identidad: dos usuarios distintos pueden
            # compartir nombre, equipo, volumen y retraso. Sin este criterio el
            # orden dependería del orden de filas de la proyección (HU07-RN-08).
            str(entry.technician_id or ""),
        )
    )

    overdue_total = sum(entry.overdue_count for entry in technicians)
    if unassigned is not None:
        overdue_total += unassigned.overdue_count

    return RankingBlock(
        technicians=technicians,
        unassigned=unassigned,
        overdue_total=overdue_total,
    )


def build_ranking(tickets: list[PopulationTicket]) -> RankingBlock:
    """Ranking de técnicos con tickets vencidos y fila «Sin asignar»."""

    groups: dict[str | None, RankingAccumulator] = {}
    for ticket in tickets:
        if ticket.vencido:
            accumulate_overdue(groups, ticket)
    return ranking_from_groups(groups)


# ---------------------------------------------------------------------------
# Ensamblado del snapshot
# ---------------------------------------------------------------------------
def build_sla_dashboard(
    session: Session,
    query: DashboardQuery,
    *,
    now: datetime | None = None,
) -> SlaDashboardResponse:
    """Construye la instantánea completa del dashboard en una sola pasada.

    Todos los bloques (resumen, matriz, totales y ranking) se acumulan sobre la
    misma proyección mientras se consume: no se materializa la lista completa
    de tickets, lo que mantiene el p95 por debajo del presupuesto con 10.000
    tickets.
    """

    filters, desde_utc, hasta_utc, ahora = parse_filters(query, now=now)

    summary_accumulator = MetricsAccumulator()
    matrix_groups: dict[tuple[str, str | None], GroupSample] = {}
    ranking_groups: dict[str | None, RankingAccumulator] = {}

    for ticket in iter_population(
        session, filters, desde_utc, hasta_utc, ahora
    ):
        summary_accumulator.add(ticket)
        accumulate_group(
            matrix_groups, (ticket.priority_id, ticket.category_id), ticket
        )
        if ticket.vencido:
            accumulate_overdue(ranking_groups, ticket)

    summary = summary_accumulator.metrics()
    priority_totals, category_totals = _totals_from_matrix(matrix_groups)
    ranking = ranking_from_groups(ranking_groups)

    if ranking.overdue_total != summary.overdue_count:
        # Invariante HU07-RF-024 / HU07-SC-014: nunca se publica un ranking
        # que no concilie con el resumen global.
        raise ApiError(
            500,
            "internal_error",
            "No se pudo calcular el dashboard.",
        )

    data = SlaDashboardData(
        summary=summary,
        matrix=_matrix_from_groups(matrix_groups),
        priority_totals=priority_totals,
        category_totals=category_totals,
        ranking=ranking,
    )
    meta = SlaDashboardMeta(
        generated_at=ahora,
        timezone="Europe/Madrid",
        thresholds=Thresholds(
            green_pct=SLA_GREEN_THRESHOLD_PCT,
            amber_pct=SLA_AMBER_THRESHOLD_PCT,
        ),
        filters=EffectiveFilters(
            desde=filters.desde,
            hasta=filters.hasta,
            categorias=filters.categorias,
            prioridades=filters.prioridades,
        ),
        has_tickets=summary.ticket_count > 0,
    )
    return SlaDashboardResponse(data=data, meta=meta)


def build_sla_dashboard_options(
    session: Session,
    query: DashboardQuery,
    *,
    now: datetime | None = None,
) -> SlaDashboardOptions:
    """Opciones de filtro presentes en el periodo (solo fechas)."""

    dates_only = DashboardQuery(
        desde=query.desde,
        hasta=query.hasta,
        categorias=None,
        prioridades=None,
    )
    filters, desde_utc, hasta_utc, _ = parse_filters(dates_only, now=now)

    category_rows = session.execute(
        select(Category.id, Category.name, Category.is_active)
        .join(Ticket, Ticket.category_id == Category.id)
        .where(Ticket.created_at >= desde_utc)
        .where(Ticket.created_at < hasta_utc)
        .distinct()
        .order_by(Category.name.asc(), Category.id.asc())
    ).all()

    categories = [
        FilterCategoryOption(id=row.id, name=row.name, is_active=row.is_active)
        for row in category_rows
    ]

    has_no_category = session.scalar(
        select(func.count())
        .select_from(Ticket)
        .where(Ticket.created_at >= desde_utc)
        .where(Ticket.created_at < hasta_utc)
        .where(Ticket.category_id.is_(None))
    )
    if has_no_category:
        categories.append(
            FilterCategoryOption(id=None, name=SIN_CATEGORIA, is_active=None)
        )

    priority_rows = session.execute(
        select(Priority.level, Priority.name, Priority.is_active)
        .join(Ticket, Ticket.priority_id == Priority.id)
        .where(Ticket.created_at >= desde_utc)
        .where(Ticket.created_at < hasta_utc)
        .distinct()
        .order_by(Priority.level.asc())
    ).all()

    priorities = [
        FilterPriorityOption(
            level=int(row.level), name=row.name, is_active=row.is_active
        )
        for row in priority_rows
    ]

    return SlaDashboardOptions(
        desde=filters.desde,
        hasta=filters.hasta,
        categories=categories,
        priorities=priorities,
    )
