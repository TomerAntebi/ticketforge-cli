"""Everything that describes TicketForge data, in three clearly separated sections:

1. Shared building blocks (stage enum, timestamp parsing)
2. Wire types: the raw JSON shapes the API sends (the API calls tickets "workitems")
3. Domain objects: what the rest of the app works with
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import NotRequired, Optional, TypedDict


# --- 1. Shared building blocks ------------------------------------------------
class TicketStage(str, Enum):
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    REVIEW = "review"
    CLOSED = "closed"


def parse_timestamp(value: str) -> datetime:
    # The API returns a trailing "Z", which fromisoformat rejects before Python 3.11.
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


# --- 2. Wire types (API JSON, never used outside parsing) ---------------------
class OwnerPayload(TypedDict):
    id: str
    username: str


class WorkItemPayload(TypedDict):
    ref: str
    title: str
    description: Optional[str]
    stage: str
    created: str
    updated: NotRequired[str]
    owner: NotRequired[OwnerPayload]
    dependsOn: NotRequired[list[str]]


class WorkItemEnvelopePayload(TypedDict):
    workitem: WorkItemPayload


class PaginationPayload(TypedDict):
    limit: int
    hasMore: bool
    nextCursor: NotRequired[str]


class WorkItemListPayload(TypedDict):
    workitems: list[WorkItemPayload]
    pagination: PaginationPayload


class UserPayload(TypedDict):
    id: str
    username: str
    created: str


class UserEnvelopePayload(TypedDict):
    user: UserPayload


# --- 3. Domain objects (what the app uses) ------------------------------------
@dataclass(frozen=True)
class Owner:
    id: str
    username: str


@dataclass(frozen=True)
class Ticket:
    ref: str
    title: str
    description: Optional[str]
    stage: TicketStage
    created: datetime
    updated: Optional[datetime] = None
    owner: Optional[Owner] = None
    depends_on: tuple[str, ...] = field(default_factory=tuple)

    @classmethod
    def from_payload(cls, payload: WorkItemPayload) -> Ticket:
        owner_payload = payload.get("owner")
        updated_value = payload.get("updated")
        return cls(
            ref=payload["ref"],
            title=payload["title"],
            description=payload["description"],
            stage=TicketStage(payload["stage"]),
            created=parse_timestamp(payload["created"]),
            updated=parse_timestamp(updated_value) if updated_value else None,
            owner=Owner(**owner_payload) if owner_payload else None,
            depends_on=tuple(payload.get("dependsOn", [])),
        )


@dataclass(frozen=True)
class TicketPage:
    tickets: tuple[Ticket, ...]
    limit: int
    has_more: bool
    next_cursor: Optional[str] = None


@dataclass(frozen=True)
class User:
    id: str
    username: str
    created: datetime

    @classmethod
    def from_payload(cls, payload: UserPayload) -> User:
        return cls(
            id=payload["id"],
            username=payload["username"],
            created=parse_timestamp(payload["created"]),
        )
