from app.services.duplicates import compute_content_hash, normalize_text


def test_normalize_text_trims_and_applies_nfc() -> None:
    assert normalize_text("  Hola  ") == "Hola"
    assert normalize_text("Cafe\u0301") == "Café"


def test_hash_is_stable_for_outer_whitespace() -> None:
    first = compute_content_hash("  No funciona la VPN  ", "  Desde ayer por la tarde.  ")
    second = compute_content_hash("No funciona la VPN", "Desde ayer por la tarde.")
    assert first == second
    assert len(first) == 64


def test_hash_changes_with_content() -> None:
    first = compute_content_hash("No funciona la VPN", "Desde ayer por la tarde.")
    second = compute_content_hash("No funciona la VPN", "Desde esta mañana.")
    assert first != second
