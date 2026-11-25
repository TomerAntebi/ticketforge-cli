"""Small shared helpers so every test reads like a story, with no real network."""

import json
from datetime import datetime, timezone
from typing import Any, Optional, Sequence, Union

import pytest
import requests

from ticketforge.exceptions.errors import TicketForgeError, TicketNotFoundError
from ticketforge.models.api_models import Ticket, TicketPage, TicketStage


@pytest.fixture(autouse=True)
def plain_terminal_output(monkeypatch: pytest.MonkeyPatch) -> None:
    """No ANSI colors in any test, even when pytest runs with -s in a real terminal."""
    monkeypatch.setenv("NO_COLOR", "1")


def make_response(
    status_code: int = 200,
    json_body: Optional[Any] = None,
    headers: Optional[dict[str, str]] = None,
    text: Optional[str] = None,
) -> requests.Response:
    """Build a real requests.Response so .ok, .json() and .headers behave genuinely."""
    response = requests.Response()
    response.status_code = status_code
    if text is not None:
        response._content = text.encode("utf-8")
    elif json_body is not None:
        response._content = json.dumps(json_body).encode("utf-8")
    else:
        response._content = b""
    response.headers.update(headers or {})
    return response


def error_response(
    error_code: str, message: str = "Something went wrong", status_code: int = 400
) -> requests.Response:
    """The API reports most failures as HTTP 400 with an `err` code in the body."""
    return make_response(status_code, {"err": error_code, "message": message})


def workitem_payload(**overrides: Any) -> dict[str, Any]:
    """An API-shaped ticket; override any field per test."""
    payload: dict[str, Any] = {
        "ref": "TF-1",
        "title": "Fix login",
        "description": "Users cannot log in",
        "stage": "open",
        "created": "2026-01-01T10:00:00Z",
        "updated": "2026-01-02T10:00:00Z",
        "dependsOn": [],
    }
    payload.update(overrides)
    return payload


def make_ticket(
    ref: str = "TF-1",
    title: str = "Fix login",
    description: Optional[str] = "Users cannot log in",
    stage: TicketStage = TicketStage.OPEN,
    depends_on: tuple[str, ...] = (),
) -> Ticket:
    return Ticket(
        ref=ref,
        title=title,
        description=description,
        stage=stage,
        created=datetime(2026, 1, 1, tzinfo=timezone.utc),
        depends_on=depends_on,
    )


def make_page(
    tickets: Sequence[Ticket] = (),
    has_more: bool = False,
    next_cursor: Optional[str] = None,
) -> TicketPage:
    return TicketPage(
        tickets=tuple(tickets), limit=5, has_more=has_more, next_cursor=next_cursor
    )


class FakeSession:
    """Stands in for requests.Session: returns queued responses, records every call.

    Queue an Exception instead of a response to simulate a network failure.
    """

    def __init__(self, *queued: Union[requests.Response, Exception]) -> None:
        self._queue = list(queued)
        self.calls: list[dict[str, Any]] = []
        self.auth: Optional[tuple[str, str]] = None

    def request(self, method: str, url: str, **kwargs: Any) -> requests.Response:
        self.calls.append({"method": method, "url": url, **kwargs})
        return self._next()

    def post(self, url: str, **kwargs: Any) -> requests.Response:
        return self.request("POST", url, **kwargs)

    def _next(self) -> requests.Response:
        item = self._queue.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


class FakeGateway:
    """In-memory stand-in for TicketClient: lets service tests run without HTTP."""

    def __init__(
        self,
        tickets: Sequence[Ticket] = (),
        pages: Sequence[TicketPage] = (),
    ) -> None:
        self.tickets = {ticket.ref: ticket for ticket in tickets}
        self._pages = list(pages)
        self.list_calls: list[dict[str, Any]] = []
        self.created: list[dict[str, Any]] = []
        self.updated: list[dict[str, Any]] = []

    def fetch_ticket_page(
        self, limit: Optional[int] = None, cursor: Optional[str] = None
    ) -> TicketPage:
        self.list_calls.append({"limit": limit, "cursor": cursor})
        return self._pages.pop(0)

    def get_ticket(self, ref: str) -> Ticket:
        # Same failure the real client raises for an unknown ref.
        if ref not in self.tickets:
            raise TicketNotFoundError(f"{ref} not found")
        return self.tickets[ref]

    def create_ticket(
        self,
        title: str,
        description: Optional[str] = None,
        depends_on: Sequence[str] = (),
    ) -> Ticket:
        self.created.append(
            {"title": title, "description": description, "depends_on": depends_on}
        )
        return make_ticket(title=title, description=description)

    def update_ticket(
        self,
        ref: str,
        title: str,
        description: Optional[str],
        stage: TicketStage,
        depends_on: Sequence[str] = (),
    ) -> Ticket:
        self.updated.append(
            {
                "ref": ref,
                "title": title,
                "description": description,
                "stage": stage,
                "depends_on": depends_on,
            }
        )
        return make_ticket(ref=ref, title=title, description=description, stage=stage)


class FailingGateway:
    """A gateway whose page requests always fail with the given error."""

    def __init__(self, error: TicketForgeError) -> None:
        self._error = error

    def fetch_ticket_page(
        self, limit: Optional[int] = None, cursor: Optional[str] = None
    ) -> TicketPage:
        raise self._error
