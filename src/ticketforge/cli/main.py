import argparse
import logging
import sys
from typing import Optional, Sequence

from ticketforge.cli.commands.account_commands import add_account_parsers
from ticketforge.cli.commands.ticket_commands import add_ticket_parsers
from ticketforge.cli.output import RED, colorize
from ticketforge.config.settings import SettingsStore
from ticketforge.exceptions.errors import RateLimitError, TicketForgeError


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ticketforge",
        description="Manage TicketForge tickets from the terminal.",
    )
    subcommands = parser.add_subparsers(dest="command", required=True)
    add_account_parsers(subcommands)
    add_ticket_parsers(subcommands)
    return parser


def run(argv: Optional[Sequence[str]] = None) -> int:
    logging.basicConfig(level=logging.WARNING, format="%(message)s")
    args = build_parser().parse_args(argv)
    try:
        args.handler(args, SettingsStore())
    except TicketForgeError as error:
        print(colorize(f"Error: {error}{describe_retry_hint(error)}", RED, sys.stderr), file=sys.stderr)
        return 1
    return 0


def describe_retry_hint(error: TicketForgeError) -> str:
    """Only rate-limit errors can say how long to wait; everything else adds nothing."""
    if isinstance(error, RateLimitError) and error.retry_after_seconds is not None:
        return f" Try again in {error.retry_after_seconds} seconds."
    return ""
