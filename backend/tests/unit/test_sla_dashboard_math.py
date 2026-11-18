"""Fórmulas puras de agregación del dashboard de SLA (T018).

Cubren la derivación por ticket (``_derive_ticket``) y las agregaciones
(resumen, matriz y totales) sin base de datos: son funciones puras sobre la
proyección ``poblacion``.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from app.services.sla_dashboard import (
    POPULATION_COLUMNS,
    DashboardFilters,
    PopulationTicket,
    _derive_ticket,
    _derive_values,
    _population_statement,
    _totals_from_matrix,
    accumulate_group,
    aggregate_metrics,
    build_category_totals,
    build_matrix,
    build_priority_totals,
    build_ranking,
)
from app.utils.sla import compliance_band

UTC = timezone.utc
NOW = datetime(2026, 11, 15, 10, 0, tzinfo=UTC)

P1 = uuid.uuid5(uuid.NAMESPACE_DNS, "math-priority-1")
P2 = uuid.uuid5(uuid.NAMESPACE_DNS, "math-priority-2")
C_A = uuid.uuid5(uuid.NAMESPACE_DNS, "math-category-a")
C_B = uuid.uuid5(uuid.NAMESPACE_DNS, "math-category-b")
TECH = uuid.uuid5(uuid.NAMESPACE_DNS, "math-tech")


def make_ticket(
    *,
    priority_level: int = 1,
    priority_name: str = "Crítica",
    priority_is_active: bool = True,
    category_id: uuid.UUID | None = C_A,
    category_name: str = "Alfa",
    category_is_active: bool | None = True,
    con_sla: bool = True,
    atendido: bool = True,
    dentro_de_plazo: bool = True,
    vencido: bool = False,
    tiempo_respuesta_s: float | None = 3600.0,
    retraso_s: float | None = None,
    atribuido_a: uuid.UUID | None = TECH,
    technician_name: str = "Sin asignar",
    team: str | None = None,
    is_active: bool | None = None,
) -> PopulationTicket:
    return PopulationTicket(
        priority_id=P1 if priority_level == 1 else P2,
        priority_level=priority_level,
        priority_name=priority_name,
        priority_is_active=priority_is_active,
        category_id=category_id,
        category_name=category_name,
        category_is_active=category_is_active,
        con_sla=con_sla,
        atendido=atendido,
        atendido_con_sla=atendido and con_sla,
        dentro_de_plazo=dentro_de_plazo,
        vencido=vencido,
        tiempo_respuesta_s=tiempo_respuesta_s,
        retraso_s=retraso_s,
        atribuido_a=atribuido_a,
        technician_name=technician_name,
        team=team,
        is_active=is_active,
    )


def derive_row(
    *,
    created: datetime,
    deadline: datetime | None,
    finalized: datetime | None,
    assignee_id: uuid.UUID | None = TECH,
    first_author_id: uuid.UUID | None = None,
    category_id: uuid.UUID | None = C_A,
):
    return SimpleNamespace(
        priority_id=P1,
        priority_level=1,
        priority_name="Crítica",
        priority_is_active=True,
        category_id=category_id,
        category_name="Alfa" if category_id is not None else None,
        category_is_active=True if category_id is not None else None,
        created_at=created,
        sla_deadline=deadline,
        primera_finalizacion=finalized,
        assignee_id=assignee_id,
        first_author_id=first_author_id,
    )


class TestDerivacionPorTicket:
    def test_primera_finalizacion_igual_al_limite_cuenta_dentro_de_plazo(self):
        limite = NOW - timedelta(hours=1)
        ticket = _derive_ticket(
            derive_row(
                created=limite - timedelta(hours=4),
                deadline=limite,
                finalized=limite,
            ),
            NOW,
        )

        assert ticket.atendido is True
        assert ticket.atendido_con_sla is True
        assert ticket.dentro_de_plazo is True
        assert ticket.vencido is False
        assert ticket.tiempo_respuesta_s == 4 * 3600

    def test_primera_finalizacion_posterior_al_limite_cuenta_vencido(self):
        limite = NOW - timedelta(hours=2)
        ticket = _derive_ticket(
            derive_row(
                created=limite - timedelta(hours=4),
                deadline=limite,
                finalized=limite + timedelta(hours=1),
            ),
            NOW,
        )

        assert ticket.dentro_de_plazo is False
        assert ticket.vencido is True
        assert ticket.retraso_s == 3600

    def test_activo_pasado_el_limite_cuenta_vencido(self):
        ticket = _derive_ticket(
            derive_row(
                created=NOW - timedelta(days=2),
                deadline=NOW - timedelta(hours=1),
                finalized=None,
            ),
            NOW,
        )

        assert ticket.atendido is False
        assert ticket.vencido is True
        assert ticket.retraso_s == 3600
        assert ticket.tiempo_respuesta_s is None

    def test_activo_sin_vencer_queda_fuera_de_porcentaje_y_media(self):
        ticket = _derive_ticket(
            derive_row(
                created=NOW - timedelta(hours=1),
                deadline=NOW + timedelta(hours=1),
                finalized=None,
            ),
            NOW,
        )
        metrics = aggregate_metrics([ticket])

        assert ticket.vencido is False
        assert metrics.ticket_count == 1
        assert metrics.attended_with_sla == 0
        assert metrics.compliance_pct is None
        assert metrics.avg_response_seconds is None
        assert metrics.overdue_count == 0
        assert metrics.semaphore == "sin_datos"

    def test_sin_sla_incrementa_no_sla_y_nunca_vence(self):
        ticket = _derive_ticket(
            derive_row(
                created=NOW - timedelta(days=30),
                deadline=None,
                finalized=None,
            ),
            NOW,
        )
        metrics = aggregate_metrics([ticket])

        assert ticket.con_sla is False
        assert ticket.vencido is False
        assert metrics.no_sla_count == 1
        assert metrics.compliance_pct is None
        assert metrics.semaphore == "sin_datos"

    def test_atribucion_mixta_al_autor_de_la_primera_finalizacion(self):
        autor = uuid.uuid5(uuid.NAMESPACE_DNS, "math-author")
        limite = NOW - timedelta(hours=2)
        finalizado_tarde = _derive_ticket(
            derive_row(
                created=limite - timedelta(hours=4),
                deadline=limite,
                finalized=limite + timedelta(hours=1),
                assignee_id=TECH,
                first_author_id=autor,
            ),
            NOW,
        )
        activo_vencido = _derive_ticket(
            derive_row(
                created=NOW - timedelta(days=2),
                deadline=NOW - timedelta(hours=1),
                finalized=None,
                assignee_id=autor,
            ),
            NOW,
        )

        assert finalizado_tarde.atribuido_a == autor
        assert activo_vencido.atribuido_a == autor

    def test_heredado_sin_linea_temporal_se_atribuye_al_responsable(self):
        # Ticket legado: la primera finalización viene de `finalized_at` y no
        # hay autor de resolución, así que la atribución cae en `assignee_id`.
        row = derive_row(
            created=NOW - timedelta(days=3),
            deadline=NOW - timedelta(days=2),
            finalized=NOW - timedelta(days=1),
            assignee_id=TECH,
            first_author_id=None,
        )
        row.assignee_name = "Técnico A"
        row.assignee_team = "Soporte"
        row.assignee_is_active = True

        ticket = _derive_ticket(row, NOW)

        assert ticket.atendido is True
        assert ticket.vencido is True
        assert ticket.atribuido_a == TECH
        assert ticket.technician_name == "Técnico A"
        assert ticket.team == "Soporte"
        assert ticket.is_active is True

    def test_heredado_sin_responsable_cae_en_sin_asignar(self):
        row = derive_row(
            created=NOW - timedelta(days=3),
            deadline=NOW - timedelta(days=2),
            finalized=NOW - timedelta(days=1),
            assignee_id=None,
            first_author_id=None,
        )

        ticket = _derive_ticket(row, NOW)

        assert ticket.vencido is True
        assert ticket.atribuido_a is None
        assert ticket.technician_name == "Sin asignar"
        assert ticket.team is None
        assert ticket.is_active is None

    def test_reabierto_conserva_la_primera_finalizacion(self):
        # La proyección entrega la primera finalización de la línea temporal,
        # no el estado actual: el ticket se cuenta una sola vez como atendido.
        primera = NOW - timedelta(days=1)
        ticket = _derive_ticket(
            derive_row(
                created=NOW - timedelta(days=2),
                deadline=primera - timedelta(hours=1),
                finalized=primera,
            ),
            NOW,
        )
        metrics = aggregate_metrics([ticket])

        assert metrics.ticket_count == 1
        assert metrics.attended_with_sla == 1
        assert metrics.on_time == 0
        assert metrics.overdue_count == 1


class TestAgregaciones:
    def test_cumplimiento_redondea_a_un_decimal_con_half_up(self):
        # 1/16 = 6,25 % -> 6,3 % (HALF_UP, no el redondeo bancario de round()).
        tickets = [
            make_ticket(dentro_de_plazo=True, vencido=False),
            *[
                make_ticket(dentro_de_plazo=False, vencido=True)
                for _ in range(15)
            ],
        ]

        metrics = aggregate_metrics(tickets)

        assert metrics.compliance_pct == 6.3
        assert metrics.on_time == 1
        assert metrics.attended_with_sla == 16

    def test_porcentaje_de_cien_y_cero(self):
        todo_bien = aggregate_metrics([make_ticket()])
        todo_mal = aggregate_metrics(
            [make_ticket(dentro_de_plazo=False, vencido=True)]
        )

        assert todo_bien.compliance_pct == 100.0
        assert todo_bien.semaphore == "verde"
        assert todo_mal.compliance_pct == 0.0
        assert todo_mal.semaphore == "rojo"

    def test_media_de_respuesta_es_exacta(self):
        metrics = aggregate_metrics(
            [
                make_ticket(tiempo_respuesta_s=100.0),
                make_ticket(tiempo_respuesta_s=200.0),
                make_ticket(tiempo_respuesta_s=301.0),
            ]
        )

        assert metrics.avg_response_seconds == 200.33333333333334

    def test_media_nula_si_no_hay_atendidos_con_sla(self):
        metrics = aggregate_metrics(
            [
                make_ticket(
                    atendido=False,
                    dentro_de_plazo=False,
                    tiempo_respuesta_s=None,
                ),
                make_ticket(
                    con_sla=False,
                    atendido=False,
                    dentro_de_plazo=False,
                    tiempo_respuesta_s=None,
                ),
            ]
        )

        assert metrics.attended_with_sla == 0
        assert metrics.avg_response_seconds is None
        assert metrics.no_sla_count == 1

    def test_vencidos_cuentan_tickets_no_eventos(self):
        metrics = aggregate_metrics(
            [
                make_ticket(dentro_de_plazo=False, vencido=True),
                make_ticket(dentro_de_plazo=False, vencido=True),
                make_ticket(),
            ]
        )

        assert metrics.overdue_count == 2

    def test_totales_recalculados_desde_tickets_y_no_media_de_celdas(self):
        # Celda A: 1/1 dentro de plazo (100 %). Celda B: 0/9 (0 %).
        # El total es 1/10 = 10,0 %, nunca la media de 100 y 0.
        tickets = [
            make_ticket(
                priority_level=1,
                category_id=C_A,
                category_name="Alfa",
            ),
            *[
                make_ticket(
                    priority_level=2,
                    priority_name="Alta",
                    category_id=C_B,
                    category_name="Beta",
                    dentro_de_plazo=False,
                    vencido=True,
                )
                for _ in range(9)
            ],
        ]

        total = aggregate_metrics(tickets)
        matrix = build_matrix(tickets)

        assert total.compliance_pct == 10.0
        assert total.attended_with_sla == 10
        assert matrix[0].compliance_pct == 100.0
        assert matrix[1].compliance_pct == 0.0

    def test_orden_de_prioridades_y_categorias(self):
        tickets = [
            make_ticket(
                priority_level=2,
                priority_name="Alta",
                category_id=C_B,
                category_name="Beta",
            ),
            make_ticket(
                priority_level=1,
                category_id=C_A,
                category_name="Alfa",
            ),
            make_ticket(
                priority_level=1,
                category_id=None,
                category_name="Sin categoría",
                category_is_active=None,
            ),
        ]

        matrix = build_matrix(tickets)
        priority_totals = build_priority_totals(tickets)
        category_totals = build_category_totals(tickets)

        assert [row.priority_level for row in priority_totals] == [1, 2]
        assert [row.category_name for row in category_totals] == [
            "Alfa",
            "Beta",
            "Sin categoría",
        ]
        assert [row.priority_level for row in matrix] == [1, 1, 2]
        assert [row.category_name for row in matrix] == [
            "Alfa",
            "Sin categoría",
            "Beta",
        ]

    def test_matriz_omite_combinaciones_sin_tickets(self):
        tickets = [
            make_ticket(priority_level=1, category_id=C_A, category_name="Alfa"),
            make_ticket(
                priority_level=2,
                priority_name="Alta",
                category_id=C_B,
                category_name="Beta",
            ),
        ]

        matrix = build_matrix(tickets)

        assert len(matrix) == 2
        assert {
            (row.priority_level, row.category_id) for row in matrix
        } == {(1, C_A), (2, C_B)}

    def test_semaforo_sin_datos_con_denominador_cero(self):
        assert compliance_band(None) == "sin_datos"
        assert aggregate_metrics([]).semaphore == "sin_datos"


class TestProyeccionYRanking:
    def test_columnas_de_la_proyeccion_coinciden_con_el_desempaquetado(self):
        filters = DashboardFilters(desde=NOW.date(), hasta=NOW.date())
        statement = _population_statement(filters, NOW, NOW)

        assert tuple(statement.selected_columns.keys()) == POPULATION_COLUMNS

    def test_derivacion_posicional_equivale_a_la_derivacion_por_atributos(self):
        row = derive_row(
            created=NOW - timedelta(days=2),
            deadline=NOW - timedelta(hours=1),
            finalized=NOW - timedelta(minutes=30),
            assignee_id=TECH,
            first_author_id=uuid.uuid5(uuid.NAMESPACE_DNS, "posicional"),
            category_id=C_B,
        )
        positional = (
            row.first_author_id,
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
            None,
            None,
            None,
        )

        assert _derive_values(positional, NOW, NOW.replace(tzinfo=None)) == (
            _derive_ticket(row, NOW)
        )

    def test_ranking_usa_las_etiquetas_de_la_poblacion_sin_otra_consulta(self):
        ana = uuid.uuid5(uuid.NAMESPACE_DNS, "math-ana")
        luis = uuid.uuid5(uuid.NAMESPACE_DNS, "math-luis")
        tickets = [
            make_ticket(
                vencido=True,
                retraso_s=7200.0,
                atribuido_a=ana,
                technician_name="Ana Torres",
                team="Soporte",
                is_active=True,
            ),
            make_ticket(
                vencido=True,
                retraso_s=3600.0,
                atribuido_a=ana,
                technician_name="Ana Torres",
                team="Soporte",
                is_active=True,
            ),
            make_ticket(
                vencido=True,
                retraso_s=3600.0,
                atribuido_a=luis,
                technician_name="Luis Pérez",
                team="Redes",
                is_active=False,
            ),
            make_ticket(vencido=False, atribuido_a=None),
        ]

        ranking = build_ranking(tickets)

        assert ranking.overdue_total == 3
        assert [str(entry.technician_id) for entry in ranking.technicians] == [
            str(ana),
            str(luis),
        ]
        assert ranking.technicians[0].technician_name == "Ana Torres"
        assert ranking.technicians[0].team == "Soporte"
        assert ranking.technicians[0].overdue_count == 2
        assert ranking.technicians[0].avg_delay_seconds == 5400.0
        assert ranking.technicians[1].is_active is False
        assert ranking.unassigned is None

    def test_ranking_separa_sin_asignar_y_concilia_el_total(self):
        tickets = [
            make_ticket(vencido=True, retraso_s=1800.0, atribuido_a=None),
            make_ticket(
                vencido=True,
                retraso_s=3600.0,
                atribuido_a=TECH,
                technician_name="Ana Torres",
            ),
        ]

        ranking = build_ranking(tickets)

        assert ranking.overdue_total == 2
        assert ranking.unassigned is not None
        assert ranking.unassigned.technician_id is None
        assert ranking.unassigned.technician_name == "Sin asignar"
        assert ranking.unassigned.overdue_count == 1
        assert ranking.unassigned.avg_delay_seconds == 1800.0
        assert [entry.technician_name for entry in ranking.technicians] == [
            "Ana Torres"
        ]

    def test_ranking_empatado_usa_technician_id_como_desempate_final(self):
        ids = [
            uuid.uuid5(uuid.NAMESPACE_DNS, "math-twin-zzz"),
            uuid.uuid5(uuid.NAMESPACE_DNS, "math-twin-aaa"),
        ]

        def twins(order):
            return [
                make_ticket(
                    vencido=True,
                    retraso_s=3600.0,
                    atribuido_a=id_,
                    technician_name="Técnico Gemelo",
                    team="Soporte",
                    is_active=True,
                )
                for id_ in order
            ]

        first = build_ranking(twins(ids))
        second = build_ranking(twins(list(reversed(ids))))

        expected = [str(id_) for id_ in sorted(ids)]
        assert [str(entry.technician_id) for entry in first.technicians] == expected
        assert [str(entry.technician_id) for entry in second.technicians] == expected
        assert first.overdue_total == second.overdue_total == 2

    def test_totales_derivados_de_la_matriz_equivalen_al_recorrido_directo(self):
        tickets = [
            make_ticket(priority_level=1, priority_name="Crítica", category_id=C_A),
            make_ticket(
                priority_level=1,
                priority_name="Crítica",
                category_id=C_B,
                vencido=True,
                retraso_s=600.0,
            ),
            make_ticket(priority_level=2, priority_name="Alta", category_id=C_A),
            make_ticket(
                priority_level=2,
                priority_name="Alta",
                category_id=None,
                category_name="Sin categoría",
                category_is_active=None,
                con_sla=False,
                atendido=False,
                dentro_de_plazo=False,
                tiempo_respuesta_s=None,
            ),
        ]

        groups: dict[tuple[str, str | None], tuple] = {}
        for ticket in tickets:
            accumulate_group(groups, (ticket.priority_id, ticket.category_id), ticket)

        priority_totals, category_totals = _totals_from_matrix(groups)

        assert priority_totals == build_priority_totals(tickets)
        assert category_totals == build_category_totals(tickets)
        assert sum(row.ticket_count for row in category_totals) == len(tickets)
