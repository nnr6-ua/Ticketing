import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import ConfigurationVersion, User, UserRole
from scripts.seed_dev import SEED_SUMMARY_LINES, seed_configuration


def test_seed_summary_describes_baseline_configuration() -> None:
    summary = "\n".join(SEED_SUMMARY_LINES)

    assert "Administración: admin@example.com (rol admin)" in summary
    assert "versión 1 base" in summary
    assert "cero reglas SLA" in summary
    assert "sin histórico de configuración" in summary
    assert "tickets legacy sin sla_config_version_id" in summary
    assert "versión 2" not in summary
    assert "16 reglas" not in summary


def test_seed_configuration_baseline_has_no_author(db: Session) -> None:
    db.query(ConfigurationVersion).delete()
    db.commit()
    actor = User(
        id=uuid.uuid4(),
        name="Administración",
        email="seed-baseline@example.com",
        role=UserRole.admin,
        is_active=True,
    )
    db.add(actor)
    db.commit()

    seed_configuration(db, datetime.now(timezone.utc))
    db.flush()

    baseline = db.scalar(
        select(ConfigurationVersion).where(ConfigurationVersion.version == 1)
    )
    assert baseline is not None
    assert baseline.created_by_id is None
