from datetime import datetime, timezone

import pytest

from tests.conftest import workitem_payload
from ticketforge.models.api_models import Ticket, TicketStage, User, parse_timestamp


# --- Positive ---------------------------------------------------------------
def test_ticket_is_built_from_a_full_payload() -> None:
    ticket = Ticket.from_payload(workitem_payload(dependsOn=["TF-2"]))

    assert ticket.ref == "TF-1"
    assert ticket.title == "Fix login"
    assert ticket.stage is TicketStage.OPEN
    assert ticket.owner is not None and ticket.owner.username == "tomer"
    assert ticket.depends_on == ("TF-2",)
    assert ticket.updated is not None


def test_ticket_optional_fields_default_when_missing() -> None:
    payload = workitem_payload()
    for optional_key in ("owner", "updated", "dependsOn"):
        del payload[optional_key]

    ticket = Ticket.from_payload(payload)

    assert ticket.owner is None
    assert ticket.updated is None
    assert ticket.depends_on == ()


def test_timestamp_with_trailing_z_is_parsed_as_utc() -> None:
    parsed = parse_timestamp("2026-01-01T10:00:00Z")

    assert parsed == datetime(2026, 1, 1, 10, 0, tzinfo=timezone.utc)


def test_user_is_built_from_a_payload() -> None:
    user = User.from_payload({"id": "u1", "username": "tomer", "created": "2026-01-01T10:00:00Z"})

    assert user.username == "tomer"
    assert user.created.year == 2026


# --- Negative ---------------------------------------------------------------
def test_unknown_stage_is_rejected() -> None:
    with pytest.raises(ValueError):
        Ticket.from_payload(workitem_payload(stage="archived"))

