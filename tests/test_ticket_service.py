import pytest

from tests.conftest import FakeGateway, make_page, make_ticket
from ticketforge.exceptions.errors import TicketNotFoundError, TicketValidationError
from ticketforge.models.api_models import TicketStage
from ticketforge.services.ticket_service import TicketService


# --- Create: positive -------------------------------------------------------
def test_create_trims_whitespace_around_the_title() -> None:
    gateway = FakeGateway()

    TicketService(gateway).create_ticket("  Fix bug  ")

    assert gateway.created[0]["title"] == "Fix bug"


def test_create_passes_description_and_dependencies_through() -> None:
    gateway = FakeGateway()

    TicketService(gateway).create_ticket("Fix bug", "Details", ["TF-2"])

    assert gateway.created[0]["description"] == "Details"
    assert gateway.created[0]["depends_on"] == ["TF-2"]


# --- Create: negative -------------------------------------------------------
@pytest.mark.parametrize("blank_title", ["", "   "])
def test_create_rejects_a_blank_title_without_calling_the_api(blank_title: str) -> None:
    gateway = FakeGateway()

    with pytest.raises(TicketValidationError):
        TicketService(gateway).create_ticket(blank_title)

    assert gateway.created == []


# --- Show -------------------------------------------------------------------
@pytest.mark.parametrize("blank_ref", ["", "   "])
def test_get_ticket_rejects_a_blank_ref(blank_ref: str) -> None:
    with pytest.raises(TicketValidationError):
        TicketService(FakeGateway()).get_ticket(blank_ref)


# --- Update: positive -------------------------------------------------------
def test_update_changes_only_the_given_field() -> None:
    current = make_ticket(title="Old", description="Desc", stage=TicketStage.OPEN, depends_on=("TF-2",))
    gateway = FakeGateway(tickets=[current])

    TicketService(gateway).update_ticket("TF-1", title="New")

    sent = gateway.updated[0]
    assert sent["title"] == "New"
    assert sent["description"] == "Desc"
    assert sent["stage"] is TicketStage.OPEN
    assert sent["depends_on"] == ("TF-2",)


def test_update_with_empty_dependency_list_clears_dependencies() -> None:
    gateway = FakeGateway(tickets=[make_ticket(depends_on=("TF-2",))])

    TicketService(gateway).update_ticket("TF-1", depends_on=[])

    assert gateway.updated[0]["depends_on"] == []


# --- Update: negative -------------------------------------------------------
def test_update_with_no_fields_is_rejected_without_calling_the_api() -> None:
    gateway = FakeGateway(tickets=[make_ticket()])

    with pytest.raises(TicketValidationError, match="Nothing to update"):
        TicketService(gateway).update_ticket("TF-1")

    assert gateway.updated == []


def test_update_with_a_blank_title_is_rejected() -> None:
    gateway = FakeGateway(tickets=[make_ticket()])

    with pytest.raises(TicketValidationError):
        TicketService(gateway).update_ticket("TF-1", title="   ")

    assert gateway.updated == []


def test_update_of_an_unknown_ticket_fails_and_sends_no_update() -> None:
    gateway = FakeGateway()

    with pytest.raises(TicketNotFoundError):
        TicketService(gateway).update_ticket("TF-999", title="New")

    assert gateway.updated == []


# --- Listing and pagination -------------------------------------------------
def test_verify_credentials_asks_the_api_for_a_single_ticket() -> None:
    gateway = FakeGateway(pages=[make_page([make_ticket()])])

    TicketService(gateway).verify_credentials()

    assert gateway.list_calls == [{"limit": 1, "cursor": None}]


def test_pages_follow_the_cursor_until_the_last_page() -> None:
    gateway = FakeGateway(
        pages=[
            make_page([make_ticket("TF-1")], has_more=True, next_cursor="c1"),
            make_page([make_ticket("TF-2")], has_more=True, next_cursor="c2"),
            make_page([make_ticket("TF-3")], has_more=False),
        ]
    )

    pages = list(TicketService(gateway).iter_ticket_pages(limit=1))

    assert [page.tickets[0].ref for page in pages] == ["TF-1", "TF-2", "TF-3"]
    assert [call["cursor"] for call in gateway.list_calls] == [None, "c1", "c2"]


def test_pages_are_fetched_lazily() -> None:
    gateway = FakeGateway(
        pages=[
            make_page([make_ticket("TF-1")], has_more=True, next_cursor="c1"),
            make_page([make_ticket("TF-2")]),
        ]
    )

    first_page = next(TicketService(gateway).iter_ticket_pages())

    assert first_page.tickets[0].ref == "TF-1"
    assert len(gateway.list_calls) == 1


def test_paging_stops_when_more_is_promised_but_no_cursor_is_given() -> None:
    gateway = FakeGateway(pages=[make_page([make_ticket()], has_more=True, next_cursor=None)])

    pages = list(TicketService(gateway).iter_ticket_pages())

    assert len(pages) == 1

