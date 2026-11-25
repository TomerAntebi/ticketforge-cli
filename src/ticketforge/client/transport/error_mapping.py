from datetime import datetime
from typing import Optional

import requests

from ticketforge.exceptions.errors import (
    AuthenticationError,
    RateLimitError,
    TicketForgeApiError,
    TicketNotFoundError,
    TicketValidationError,
    UsernameTakenError,
)
from ticketforge.models.api_models import parse_timestamp

# The API reports most failures as HTTP 400 and distinguishes them only by the
# `err` code in the JSON body, so status codes alone cannot be trusted.
VALIDATION_ERROR_CODES = frozenset({"invalid_input", "missing_fields", "invalid_cursor"})
NOT_FOUND_ERROR_CODE = "not_found"
USERNAME_TAKEN_ERROR_CODE = "user_exists"
UNAUTHORIZED_ERROR_CODE = "unauthorized"
RATE_LIMIT_ERROR_CODE = "rate_limit_exceeded"


def raise_for_api_error(response: requests.Response) -> None:
    """Translate HTTP failures into domain errors, shared by every API client."""
    if response.ok:
        return
    status = response.status_code
    error_code, message = _read_error_body(response)

    if status == 401 or error_code == UNAUTHORIZED_ERROR_CODE:
        raise AuthenticationError(message)
    if status == 429 or error_code == RATE_LIMIT_ERROR_CODE:
        raise RateLimitError(
            message,
            reset_at=_read_reset_time(response),
            retry_after_seconds=_read_retry_after(response),
        )
    if error_code == NOT_FOUND_ERROR_CODE:
        raise TicketNotFoundError(message)
    if error_code == USERNAME_TAKEN_ERROR_CODE:
        raise UsernameTakenError(message)
    if error_code in VALIDATION_ERROR_CODES:
        raise TicketValidationError(message)
    raise TicketForgeApiError(message, status)


def _read_error_body(response: requests.Response) -> tuple[Optional[str], str]:
    """Return (err code, human message); fall back to raw text for non-JSON bodies."""
    fallback_message = f"HTTP {response.status_code}: {response.text[:200]}"
    try:
        body = response.json()
    except ValueError:
        return None, fallback_message
    if not isinstance(body, dict):
        return None, fallback_message
    error_code = body.get("err")
    message = body.get("message")
    return (
        error_code if isinstance(error_code, str) else None,
        message if isinstance(message, str) else fallback_message,
    )


def _read_reset_time(response: requests.Response) -> Optional[datetime]:
    reset_header = response.headers.get("x-ratelimit-reset")
    return parse_timestamp(reset_header) if reset_header else None


def _read_retry_after(response: requests.Response) -> Optional[int]:
    retry_after_header = response.headers.get("retry-after")
    return int(retry_after_header) if retry_after_header and retry_after_header.isdigit() else None
