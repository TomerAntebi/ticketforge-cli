from datetime import datetime
from typing import Optional


class TicketForgeError(Exception):
    """Base class so callers can catch every TicketForge failure at once."""


class ConfigurationError(TicketForgeError):
    """Settings are missing or unreadable; the user must run `setup`."""


class TicketForgeConnectionError(TicketForgeError):
    """The request never reached the API (network down, timeout, DNS)."""


class AuthenticationError(TicketForgeError):
    """Credentials were rejected (HTTP 401)."""


class TicketNotFoundError(TicketForgeError):
    """The ticket ref does not exist. The API reports this as HTTP 400, not 404."""


class TicketValidationError(TicketForgeError):
    """The API rejected the request input (bad body, bad cursor, missing fields)."""


class UsernameTakenError(TicketForgeError):
    """Registration failed because the username already exists."""


class RateLimitError(TicketForgeError):
    """Too many requests (HTTP 429).

    `retry_after_seconds` comes from the Retry-After header and `reset_at` from
    x-ratelimit-reset, so callers can decide whether waiting is worthwhile.
    """

    def __init__(
        self,
        message: str,
        reset_at: Optional[datetime] = None,
        retry_after_seconds: Optional[int] = None,
    ) -> None:
        super().__init__(message)
        self.reset_at = reset_at
        self.retry_after_seconds = retry_after_seconds


class TicketForgeApiError(TicketForgeError):
    """Any other non-success response."""

    def __init__(self, message: str, status_code: int) -> None:
        super().__init__(message)
        self.status_code = status_code
