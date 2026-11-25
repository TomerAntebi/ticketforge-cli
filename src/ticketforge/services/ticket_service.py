from typing import Iterator, Optional, Sequence

from ticketforge.client.ticket_client import TicketClient
from ticketforge.exceptions.errors import TicketValidationError
from ticketforge.models.api_models import Ticket, TicketPage, TicketStage


class TicketService:
    """Ticket business rules. No HTTP, no printing, no argument parsing."""

    def __init__(self, ticket_client: TicketClient) -> None:
        self._ticket_client = ticket_client

    def verify_credentials(self) -> None:
        """Raise AuthenticationError if the credentials are rejected.

        The API has no login endpoint, so one cheap authenticated request is the check.
        """
        self._ticket_client.fetch_ticket_page(limit=1)

    def iter_ticket_pages(self, limit: Optional[int] = None) -> Iterator[TicketPage]:
        """Yield pages lazily, following the API cursor until the last page.

        Lazy on purpose: a page is requested only when the caller asks for the
        next one, so an interactive "press Enter for more" costs one request each.
        """
        cursor: Optional[str] = None
        while True:
            page = self._ticket_client.fetch_ticket_page(limit=limit, cursor=cursor)
            yield page
            if not page.has_more or page.next_cursor is None:
                return
            cursor = page.next_cursor

    def get_ticket(self, ref: str) -> Ticket:
        trimmed_ref = ref.strip()
        if not trimmed_ref:
            raise TicketValidationError("Ticket ref cannot be empty.")
        return self._ticket_client.get_ticket(trimmed_ref)

    def create_ticket(
        self,
        title: str,
        description: Optional[str] = None,
        depends_on: Sequence[str] = (),
    ) -> Ticket:
        trimmed_title = title.strip()
        if not trimmed_title:
            raise TicketValidationError("Title cannot be empty.")
        return self._ticket_client.create_ticket(trimmed_title, description, depends_on)

    def update_ticket(
        self,
        ref: str,
        title: Optional[str] = None,
        description: Optional[str] = None,
        stage: Optional[TicketStage] = None,
        depends_on: Optional[Sequence[str]] = None,
    ) -> Ticket:
        """Change only the given fields; None means "keep the current value".

        The API's PUT rejects partial bodies, so the current ticket is fetched
        first and its values fill every field the caller did not provide.
        """
        if all(value is None for value in (title, description, stage, depends_on)):
            raise TicketValidationError("Nothing to update: provide at least one field.")
        if title is not None and not title.strip():
            raise TicketValidationError("Title cannot be empty.")

        existing_ticket = self._ticket_client.get_ticket(ref)
        return self._ticket_client.update_ticket(
            ref,
            title=title.strip() if title is not None else existing_ticket.title,
            description=description if description is not None else existing_ticket.description,
            stage=stage if stage is not None else existing_ticket.stage,
            depends_on=depends_on if depends_on is not None else existing_ticket.depends_on,
        )
