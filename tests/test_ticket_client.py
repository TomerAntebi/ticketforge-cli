from functools import partial

import pytest
import requests

import ticketforge.client.transport.api_transport as transport_module
from tests.conftest import FakeSession, make_response, workitem_payload
from ticketforge.client.transport.rate_limit import retry_on_rate_limit
from ticketforge.client.ticket_client import TicketClient
from ticketforge.exceptions.errors import (
    AuthenticationError,
    TicketForgeConnectionError,
)
from ticketforge.models.api_models import TicketStage

BASE_URL = "https://example.test"


def make_client(session: FakeSession, base_url: str = BASE_URL) -> TicketClient:
    return TicketClient(base_url, "tomer", "secret", session=session)  # type: ignore[arg-type]


def workitem_response(**overrides: object) -> requests.Response:
    return make_response(200, {"workitem": workitem_payload(**overrides)})


def list_response(count: int = 2, has_more: bool = False, next_cursor: str = "") -> requests.Response:
    pagination: dict[str, object] = {"limit": 5, "hasMore": has_more}
    if next_cursor:
        pagination["nextCursor"] = next_cursor
    items = [workitem_payload(ref=f"TF-{number}") for number in range(1, count + 1)]
    return make_response(200, {"workitems": items, "pagination": pagination})


# --- Setup ------------------------------------------------------------------
def test_basic_auth_credentials_are_set_on_the_session() -> None:
    session = FakeSession()

    make_client(session)

    assert session.auth == ("tomer", "secret")


# --- Positive ---------------------------------------------------------------
def test_list_returns_a_parsed_page() -> None:
    session = FakeSession(list_response(count=2, has_more=True, next_cursor="abc:1"))

    page = make_client(session).fetch_ticket_page()

    assert [ticket.ref for ticket in page.tickets] == ["TF-1", "TF-2"]
    assert page.has_more is True
    assert page.next_cursor == "abc:1"


def test_list_sends_limit_and_cursor_only_when_given() -> None:
    session = FakeSession(list_response(), list_response())
    client = make_client(session)

    client.fetch_ticket_page()
    client.fetch_ticket_page(limit=3, cursor="abc:1")

    assert session.calls[0]["params"] == {}
    assert session.calls[1]["params"] == {"limit": 3, "cursor": "abc:1"}


def test_get_ticket_returns_dependencies() -> None:
    session = FakeSession(workitem_response(dependsOn=["TF-2"]))

    ticket = make_client(session).get_ticket("TF-1")

    assert ticket.depends_on == ("TF-2",)
    assert session.calls[0]["method"] == "GET"


def test_create_sends_only_the_title_when_nothing_else_is_given() -> None:
    session = FakeSession(workitem_response())

    make_client(session).create_ticket("New ticket")

    assert session.calls[0]["method"] == "POST"
    assert session.calls[0]["json"] == {"title": "New ticket"}


def test_create_sends_description_and_dependencies_when_given() -> None:
    session = FakeSession(workitem_response())

    make_client(session).create_ticket("New", description="Details", depends_on=["TF-2"])

    assert session.calls[0]["json"] == {
        "title": "New",
        "description": "Details",
        "dependsOn": ["TF-2"],
    }


def test_update_sends_the_full_body_with_the_stage_value() -> None:
    session = FakeSession(workitem_response(stage="review"))

    ticket = make_client(session).update_ticket(
        "TF-1", "Title", "Desc", TicketStage.REVIEW, depends_on=["TF-2"]
    )

    assert session.calls[0]["method"] == "PUT"
    assert session.calls[0]["json"] == {
        "title": "Title",
        "description": "Desc",
        "stage": "review",
        "dependsOn": ["TF-2"],
        "customFields": {},
    }
    assert ticket.stage is TicketStage.REVIEW


# --- Negative ---------------------------------------------------------------
@pytest.mark.parametrize("network_error", [requests.ConnectionError("down"), requests.Timeout("slow")])
def test_network_failure_becomes_a_connection_error(network_error: Exception) -> None:
    session = FakeSession(network_error)

    with pytest.raises(TicketForgeConnectionError):
        make_client(session).get_ticket("TF-1")


def test_wrong_credentials_raise_authentication_error() -> None:
    session = FakeSession(make_response(401, {"err": "unauthorized", "message": "Bad login"}))

    with pytest.raises(AuthenticationError):
        make_client(session).fetch_ticket_page()


def test_rate_limited_request_is_retried_and_then_succeeds(monkeypatch: pytest.MonkeyPatch) -> None:
    # Keep the real retry logic but skip the actual waiting.
    monkeypatch.setattr(
        transport_module,
        "retry_on_rate_limit",
        partial(retry_on_rate_limit, sleep=lambda seconds: None),
    )
    rate_limited = make_response(
        429, {"err": "rate_limit_exceeded", "message": "Slow"}, headers={"retry-after": "1"}
    )
    session = FakeSession(rate_limited, workitem_response())

    ticket = make_client(session).get_ticket("TF-1")

    assert ticket.ref == "TF-1"
    assert len(session.calls) == 2
