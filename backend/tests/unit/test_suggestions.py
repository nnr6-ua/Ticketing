from sqlalchemy.orm import Session

from app.services.suggestions import suggest


def test_suggests_category_and_priority_by_keywords(db_session: Session) -> None:
    result = suggest(db_session, "No funciona la VPN urgente", "No puedo conectar desde ayer.")

    assert result.category.name == "Red y conectividad"
    assert result.priority.name == "Crítica"
    assert result.category_is_fallback is False
    assert result.priority_is_fallback is False


def test_uses_default_catalog_values_when_no_keyword_matches(db_session: Session) -> None:
    result = suggest(db_session, "zzz", "zzz")

    assert result.category.name == "Otros"
    assert result.priority.name == "Media"
    assert result.category_is_fallback is True
    assert result.priority_is_fallback is True


def test_multiword_keyword_has_more_weight(db_session: Session) -> None:
    result = suggest(db_session, "error grave en el portátil", "Necesito ayuda.")

    assert result.category.name == "Hardware"
    assert result.priority.name == "Alta"
