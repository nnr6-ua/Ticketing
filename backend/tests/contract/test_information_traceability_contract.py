"""Trazabilidad del contrato de HU-03 (T046)."""

from tests.integration.test_information_cycle import (
    test_full_cycle_returns_ticket_to_queue_with_traceability as test_independent_entries_traceability,
    test_information_entries_are_immutable_and_have_no_edit_endpoints as test_entries_are_immutable,
    test_response_is_rejected_when_ticket_is_finalized as test_finalized_ticket_rejects_response,
)
from tests.integration.test_ticket_information import (
    test_timeline_exposes_reply_to_id_only_to_authorized_viewers as test_reply_to_id_contract,
)

__all__ = [
    test_entries_are_immutable.__name__,
    test_finalized_ticket_rejects_response.__name__,
    test_independent_entries_traceability.__name__,
    test_reply_to_id_contract.__name__,
]
