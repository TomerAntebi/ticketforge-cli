import argparse
import sys
from typing import Iterable

from ticketforge.cli.output import (
    DIM,
    GREEN,
    colorize,
    describe_ticket,
    format_ticket_details,
    format_ticket_table,
)
from ticketforge.client.ticket_client import TicketClient
from ticketforge.config.settings import SettingsStore
from ticketforge.models.api_models import TicketPage, TicketStage
from ticketforge.services.ticket_service import TicketService


# --- Service wiring -----------------------------------------------------------
def create_ticket_service(store: SettingsStore) -> TicketService:
    """Wire saved credentials into a service. Raises ConfigurationError before `setup`."""
    settings = store.load()
    client = TicketClient(settings.base_url, settings.username, settings.password)
    return TicketService(client)


# --- Argument parsers ---------------------------------------------------------
def add_ticket_parsers(
    subcommands: "argparse._SubParsersAction[argparse.ArgumentParser]",
) -> None:
    list_command = subcommands.add_parser("list", help="list your tickets")
    list_command.add_argument(
        "--limit", type=int, help="tickets per page, 1-5 (the API maximum is 5)"
    )
    list_command.add_argument("--all", action="store_true", help="list every ticket without paging")
    list_command.set_defaults(handler=handle_list)

    show = subcommands.add_parser("show", help="show the details of a ticket")
    show.add_argument("ref", help="ticket ref, for example TF-821")
    show.set_defaults(handler=handle_show)

    create = subcommands.add_parser("create", help="create a ticket")
    create.add_argument("title")
    create.add_argument("--description")
    create.add_argument("--depends-on", nargs="+", default=(), metavar="REF")
    create.set_defaults(handler=handle_create)

    update = subcommands.add_parser("update", help="update a ticket")
    update.add_argument("ref", help="ticket ref, for example TF-821")
    update.add_argument("--title")
    update.add_argument("--description")
    update.add_argument("--stage", choices=[stage.value for stage in TicketStage])
    update.add_argument(
        "--depends-on",
        nargs="*",
        default=None,
        metavar="REF",
        help="replace dependencies; pass no refs to clear them",
    )
    update.set_defaults(handler=handle_update)


# --- Command handlers ---------------------------------------------------------
def handle_list(args: argparse.Namespace, store: SettingsStore) -> None:
    pages = create_ticket_service(store).iter_ticket_pages(limit=args.limit)
    if args.all:
        print_all_tickets(pages)
    else:
        print_pages_one_at_a_time(pages)


def handle_show(args: argparse.Namespace, store: SettingsStore) -> None:
    print(format_ticket_details(create_ticket_service(store).get_ticket(args.ref)))


def print_all_tickets(pages: Iterable[TicketPage]) -> None:
    tickets = [ticket for page in pages for ticket in page.tickets]
    if not tickets:
        print("No tickets found.")
        return
    print(format_ticket_table(tickets))
    print(colorize(f"\nShowing {len(tickets)} ticket(s) in total.", DIM))


def print_pages_one_at_a_time(pages: Iterable[TicketPage]) -> None:
    for page in pages:
        if not page.tickets:
            print("No tickets found.")
            return
        print(format_ticket_table(page.tickets))
        print(colorize(f"\nShowing {len(page.tickets)} ticket(s).", DIM))
        if not page.has_more:
            return
        if not is_terminal_session():
            # Never block on a prompt when output is piped or redirected.
            print("More tickets available. Use --all to list everything.", file=sys.stderr)
            return
        if not ask_for_next_page():
            return
        print()


def is_terminal_session() -> bool:
    return sys.stdin.isatty() and sys.stdout.isatty()


def ask_for_next_page() -> bool:
    try:
        answer = input("More tickets available. Press Enter for the next page, or q to quit: ")
    except (EOFError, KeyboardInterrupt):
        print()
        return False
    return answer.strip().lower() not in ("q", "quit")


def handle_create(args: argparse.Namespace, store: SettingsStore) -> None:
    ticket = create_ticket_service(store).create_ticket(args.title, args.description, args.depends_on)
    print(f"{colorize('Created', GREEN)} {describe_ticket(ticket)}")


def handle_update(args: argparse.Namespace, store: SettingsStore) -> None:
    stage = TicketStage(args.stage) if args.stage else None
    ticket = create_ticket_service(store).update_ticket(
        args.ref,
        title=args.title,
        description=args.description,
        stage=stage,
        depends_on=args.depends_on,
    )
    print(f"{colorize('Updated', GREEN)} {describe_ticket(ticket)}")
