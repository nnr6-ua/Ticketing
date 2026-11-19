"""API administrativa de catálogos, matriz SLA e histórico (HU-08)."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import require_admin
from app.db.session import get_session
from app.models import ConfigAction, ConfigEntityType, User
from app.schemas.configuration import (
    CategoryAdmin,
    CategoryCreateRequest,
    CategoryUpdateRequest,
    ConfigHistoryResponse,
    DeleteRequest,
    DeleteResponse,
    PriorityAdmin,
    PriorityCreateRequest,
    PriorityUpdateRequest,
    SlaBatchRequest,
    SlaBatchResponse,
    SlaMatrixResponse,
    SlaRetireRequest,
)
from app.services import configuration

router = APIRouter(
    prefix="/admin",
    tags=["Configuración administrativa"],
    dependencies=[Depends(require_admin)],
)


@router.get("/categories", response_model=list[CategoryAdmin])
def list_categories(
    session: Session = Depends(get_session),
    _: User = Depends(require_admin),
) -> list[CategoryAdmin]:
    return configuration.list_categories(session)


@router.post("/categories", response_model=CategoryAdmin, status_code=201)
def create_category(
    payload: CategoryCreateRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(require_admin),
) -> CategoryAdmin:
    return configuration.create_category(session, current_user, payload)


@router.post("/categories/{category_id}/updates", response_model=CategoryAdmin)
def update_category(
    category_id: UUID,
    payload: CategoryUpdateRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(require_admin),
) -> CategoryAdmin:
    return configuration.update_category(
        session, current_user, category_id, payload
    )


@router.post(
    "/categories/{category_id}/deletion", response_model=DeleteResponse
)
def delete_category(
    category_id: UUID,
    payload: DeleteRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(require_admin),
) -> DeleteResponse:
    return configuration.delete_category(
        session, current_user, category_id, payload
    )


@router.get("/priorities", response_model=list[PriorityAdmin])
def list_priorities(
    session: Session = Depends(get_session),
    _: User = Depends(require_admin),
) -> list[PriorityAdmin]:
    return configuration.list_priorities(session)


@router.post("/priorities", response_model=PriorityAdmin, status_code=201)
def create_priority(
    payload: PriorityCreateRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(require_admin),
) -> PriorityAdmin:
    return configuration.create_priority(session, current_user, payload)


@router.post("/priorities/{priority_id}/updates", response_model=PriorityAdmin)
def update_priority(
    priority_id: UUID,
    payload: PriorityUpdateRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(require_admin),
) -> PriorityAdmin:
    return configuration.update_priority(
        session, current_user, priority_id, payload
    )


@router.post(
    "/priorities/{priority_id}/deletion", response_model=DeleteResponse
)
def delete_priority(
    priority_id: UUID,
    payload: DeleteRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(require_admin),
) -> DeleteResponse:
    return configuration.delete_priority(
        session, current_user, priority_id, payload
    )


@router.get("/sla-rules", response_model=SlaMatrixResponse)
def get_sla_rules(
    session: Session = Depends(get_session),
    _: User = Depends(require_admin),
) -> SlaMatrixResponse:
    return configuration.sla_matrix(session)


@router.post("/sla-rules/batch", response_model=SlaBatchResponse)
def apply_sla_batch(
    payload: SlaBatchRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(require_admin),
) -> SlaBatchResponse:
    return configuration.apply_sla_batch(session, current_user, payload)


@router.post(
    "/sla-rules/{rule_id}/retirement", response_model=SlaBatchResponse
)
def retire_sla_rule(
    rule_id: UUID,
    payload: SlaRetireRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(require_admin),
) -> SlaBatchResponse:
    return configuration.retire_sla_rule(
        session, current_user, rule_id, payload.expected_rule_id
    )


@router.get("/config-history", response_model=ConfigHistoryResponse)
def list_config_history(
    from_: Annotated[datetime | None, Query(alias="from")] = None,
    to: datetime | None = None,
    entity_type: ConfigEntityType | None = None,
    entity_id: UUID | None = None,
    action: ConfigAction | None = None,
    configuration_version_id: UUID | None = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 25,
    session: Session = Depends(get_session),
    _: User = Depends(require_admin),
) -> ConfigHistoryResponse:
    return configuration.list_config_history(
        session,
        from_date=from_,
        to_date=to,
        entity_type=entity_type,
        entity_id=entity_id,
        action=action,
        configuration_version_id=configuration_version_id,
        page=page,
        page_size=page_size,
    )
