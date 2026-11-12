from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, Response, UploadFile
from sqlalchemy.orm import Session

from app.api.deps import get_current_employee
from app.core.config import settings
from app.db.session import get_db
from app.models import Employee
from app.schemas.ticket import TicketCreateResponse
from app.services.attachments import cleanup_staged, stage_files
from app.services.tickets import create_ticket

router = APIRouter(prefix="/tickets", tags=["tickets"])


@router.post("", response_model=TicketCreateResponse, status_code=201)
async def create_ticket_endpoint(
    response: Response,
    title: Annotated[str, Form(min_length=5, max_length=120)],
    description: Annotated[str, Form(min_length=20, max_length=5000)],
    priority_id: Annotated[int | None, Form()] = None,
    attachments: Annotated[list[UploadFile] | None, File()] = None,
    db: Session = Depends(get_db),
    employee: Employee = Depends(get_current_employee),
) -> TicketCreateResponse:
    temp_dir = settings.attachments_dir / "tmp"
    staged = await stage_files(attachments or [], temp_dir)

    try:
        ticket, duplicate = create_ticket(
            db,
            employee,
            title=title,
            description=description,
            priority_id=priority_id,
            staged=staged,
            attachments_dir=settings.attachments_dir,
        )
    except Exception:
        cleanup_staged(staged)
        raise

    if duplicate:
        response.status_code = 200

    return TicketCreateResponse.model_validate(ticket).model_copy(
        update={"duplicate": duplicate}
    )
