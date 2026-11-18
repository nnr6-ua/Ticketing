from app.services.ticket_numbers import max_ticket_number_value


def test_max_ticket_number_value_ignores_invalid_and_returns_one_when_empty() -> None:
    assert max_ticket_number_value([]) == 1
    assert max_ticket_number_value(["TK-000001", "TK-abc", ""]) == 1


def test_max_ticket_number_value_returns_highest_existing_suffix() -> None:
    numbers = ["TK-000001", "TK-000101", "TK-000099"]
    assert max_ticket_number_value(numbers) == 101
