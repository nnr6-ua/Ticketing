from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_employee
from app.db.session import get_db
from app.models import Employee, Priority
from app.schemas.ticket import PriorityRead

router = APIRouter(prefix="/priorities", tags=["priorities"])


@router.get("", response_model=list[PriorityRead])
def list_priorities(
    db: Session = Depends(get_db),
    _: Employee = Depends(get_current_employee),
) -> list[Priority]:
    return list(
        db.scalars(
            select(Priority)
            .where(
                Priority.is_active.is_(True),
                Priority.is_system.is_(False),
            )
            .order_by(Priority.sort_order, Priority.id)
        ).all()
    )
