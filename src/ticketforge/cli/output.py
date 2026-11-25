import os
import sys
from typing import Sequence, TextIO

from ticketforge.models.api_models import Ticket, TicketStage

RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"
RED = "\033[31m"
GREEN = "\033[32m"
STAGE_COLORS = {
    TicketStage.OPEN: "\033[36m",
    TicketStage.IN_PROGRESS: "\033[33m",
    TicketStage.REVIEW: "\033[35m",
    TicketStage.CLOSED: GREEN,
}
TABLE_HEADER = ("REF", "STAGE", "TITLE")
DATE_FORMAT = "%Y-%m-%d %H:%M UTC"  # the API sends timestamps in UTC
EMPTY_VALUE = "-"


def colorize(text: str, style: str, stream: TextIO = sys.stdout) -> str:
    """Wrap text in an ANSI style, but only for real terminals.

    Piped output and NO_COLOR (https://no-color.org) stay plain, so scripts
    and log files never receive escape codes.
    """
    if not stream.isatty() or "NO_COLOR" in os.environ:
        return text
    return f"{style}{text}{RESET}"


def describe_ticket(ticket: Ticket) -> str:
    stage = colorize(ticket.stage.value, STAGE_COLORS[ticket.stage])
    return f"{colorize(ticket.ref, BOLD)} [{stage}] {ticket.title}"


def format_ticket_table(tickets: Sequence[Ticket]) -> str:
    # Pad first, color second: escape codes would otherwise break the alignment.
    ref_width = max([len(ticket.ref) for ticket in tickets] + [len(TABLE_HEADER[0])])
    stage_width = max([len(stage.value) for stage in TicketStage] + [len(TABLE_HEADER[1])])

    header = "  ".join(
        [
            TABLE_HEADER[0].ljust(ref_width),
            TABLE_HEADER[1].ljust(stage_width),
            TABLE_HEADER[2],
        ]
    )
    lines = [colorize(header, BOLD)]
    for ticket in tickets:
        stage = colorize(ticket.stage.value.ljust(stage_width), STAGE_COLORS[ticket.stage])
        lines.append(f"{colorize(ticket.ref.ljust(ref_width), BOLD)}  {stage}  {ticket.title}")
    return "\n".join(lines)


def format_ticket_details(ticket: Ticket) -> str:
    rows = [
        ("Ref", colorize(ticket.ref, BOLD)),
        ("Title", ticket.title),
        ("Stage", colorize(ticket.stage.value, STAGE_COLORS[ticket.stage])),
        ("Created", ticket.created.strftime(DATE_FORMAT)),
        ("Updated", ticket.updated.strftime(DATE_FORMAT) if ticket.updated else EMPTY_VALUE),
        ("Depends on", ", ".join(ticket.depends_on) or EMPTY_VALUE),
        ("Description", ticket.description or EMPTY_VALUE),
    ]
    label_width = max(len(label) for label, _ in rows)
    return "\n".join(f"{label.ljust(label_width)}  {value}" for label, value in rows)
