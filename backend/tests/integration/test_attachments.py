import asyncio
from io import BytesIO
from pathlib import Path

import pytest
from fastapi import UploadFile
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.models import Employee, Ticket
from app.services.attachments import stage_files
from app.services.tickets import create_ticket

PNG = b"\x89PNG\r\n\x1a\n" + b"contenido"


def test_failed_ticket_cleans_staged_attachment(
    db_session: Session, tmp_path: Path
) -> None:
    employee = db_session.scalar(select(Employee))
    assert employee is not None

    temp_dir = tmp_path / "tmp"
    staged = asyncio.run(
        stage_files([UploadFile(filename="foto.png", file=BytesIO(PNG))], temp_dir)
    )

    with pytest.raises(AppError) as error:
        create_ticket(
            db_session,
            employee,
            title="No funciona la VPN",
            description="No puedo conectar desde ayer por la tarde.",
            priority_id=9999,
            staged=staged,
            attachments_dir=tmp_path,
        )

    assert error.value.code == "invalid_priority"
    assert db_session.scalar(select(func.count(Ticket.id))) == 0
    assert list(temp_dir.glob("*")) == []
    assert not (tmp_path / "attachments").exists()
