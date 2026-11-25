from typing import Optional, Sequence, cast

import requests

from ticketforge.client.transport.api_transport import DEFAULT_TIMEOUT_SECONDS, ApiTransport
from ticketforge.models.api_models import (
    Ticket,
    TicketPage,
    TicketStage,
    WorkItemEnvelopePayload,
    WorkItemListPayload,
)


class TicketClient:
    """Ticket endpoints of TicketForge. Knows paths and payloads; transport handles HTTP."""

    _LIST_MINE_PATH = "/api/tforge/workitems/mine"
    _PUBLISH_PATH = "/api/tforge/workitem/publish"
    _WORKITEM_PATH = "/api/tforge/workitem/{ref}"

    def __init__(
        self,
        base_url: str,
        username: str,
        password: str,
        session: Optional[requests.Session] = None,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    ) -> None:
        self._transport = ApiTransport(
            base_url, session, timeout_seconds, auth=(username, password)
        )

    def fetch_ticket_page(
        self,
        limit: Optional[int] = None,
        cursor: Optional[str] = None,
    ) -> TicketPage:
        # The API paginates with an opaque "timestamp:id" cursor returned as
        # pagination.nextCursor; offset/page parameters are silently ignored.
        query: dict[str, object] = {}
        if limit is not None:
            query["limit"] = limit
        if cursor is not None:
            query["cursor"] = cursor
        response = self._transport.request_with_retry("GET", self._LIST_MINE_PATH, query=query)
        payload = cast(WorkItemListPayload, response.json())
        pagination = payload["pagination"]
        return TicketPage(
            tickets=tuple(Ticket.from_payload(item) for item in payload["workitems"]),
            limit=pagination["limit"],
            has_more=pagination["hasMore"],
            next_cursor=pagination.get("nextCursor"),
        )

    def get_ticket(self, ref: str) -> Ticket:
        # Only this endpoint returns dependsOn; the list endpoint omits it.
        response = self._transport.request_with_retry("GET", self._WORKITEM_PATH.format(ref=ref))
        return self._parse_ticket(response)

    def create_ticket(
        self,
        title: str,
        description: Optional[str] = None,
        depends_on: Sequence[str] = (),
    ) -> Ticket:
        body: dict[str, object] = {"title": title}
        if description is not None:
            body["description"] = description
        if depends_on:
            body["dependsOn"] = list(depends_on)
        response = self._transport.request_with_retry("POST", self._PUBLISH_PATH, body)
        return self._parse_ticket(response)

    def update_ticket(
        self,
        ref: str,
        title: str,
        description: Optional[str],
        stage: TicketStage,
        depends_on: Sequence[str] = (),
    ) -> Ticket:
        # PUT needs the full body: the API rejects partial updates (title and a
        # valid stage are always required), so callers must send current values.
        # Custom fields are not modeled by this CLI, so an empty object is sent.
        body: dict[str, object] = {
            "title": title,
            "description": description,
            "stage": stage.value,
            "dependsOn": list(depends_on),
            "customFields": {},
        }
        response = self._transport.request_with_retry(
            "PUT", self._WORKITEM_PATH.format(ref=ref), body
        )
        return self._parse_ticket(response)

    @staticmethod
    def _parse_ticket(response: requests.Response) -> Ticket:
        payload = cast(WorkItemEnvelopePayload, response.json())
        return Ticket.from_payload(payload["workitem"])
