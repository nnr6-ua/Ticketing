"""Trazabilidad de la visibilidad pública de HU-03 (T045)."""

from tests.integration.test_information_cycle import (
    test_creator_cannot_see_internal_comments_but_sees_information as test_creator_sees_public_information_without_internal_comments,
    test_full_cycle_returns_ticket_to_queue_with_traceability as test_creator_and_technician_see_same_public_entries,
)

__all__ = [
    "test_creator_and_technician_see_same_public_entries",
    "test_creator_sees_public_information_without_internal_comments",
]
