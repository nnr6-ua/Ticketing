from fastapi import Depends, Header, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import Employee


def get_current_employee(
    db: Session = Depends(get_db),
    x_employee_id: str | None = Header(default=None, alias="X-Employee-Id"),
) -> Employee:
    if not x_employee_id:
        raise HTTPException(
            status_code=401,
            detail={
                "error": {
                    "code": "auth_required",
                    "message": "Falta la cabecera X-Employee-Id.",
                }
            },
        )

    try:
        employee_id = int(x_employee_id)
    except ValueError:
        raise HTTPException(
            status_code=401,
            detail={
                "error": {
                    "code": "auth_invalid",
                    "message": "La cabecera X-Employee-Id no es válida.",
                }
            },
        ) from None

    employee = db.scalar(
        select(Employee).where(
            Employee.id == employee_id,
            Employee.is_active.is_(True),
        )
    )
    if employee is None:
        raise HTTPException(
            status_code=401,
            detail={
                "error": {
                    "code": "auth_invalid",
                    "message": "El empleado no existe o no está activo.",
                }
            },
        )
    return employee
