import pytest

from tests.conftest import error_response, make_response
from ticketforge.client.transport.error_mapping import raise_for_api_error
from ticketforge.exceptions.errors import (
    AuthenticationError,
    RateLimitError,
    TicketForgeApiError,
    TicketNotFoundError,
    TicketValidationError,
    UsernameTakenError,
)


# --- Positive ---------------------------------------------------------------
def test_success_response_raises_nothing() -> None:
    raise_for_api_error(make_response(200, {"ok": True}))


# --- Negative: the API signals the failure type in the `err` code -----------
@pytest.mark.parametrize(
    ("error_code", "expected_error"),
    [
        ("not_found", TicketNotFoundError),
        ("user_exists", UsernameTakenError),
        ("invalid_input", TicketValidationError),
        ("missing_fields", TicketValidationError),
        ("invalid_cursor", TicketValidationError),
        ("unauthorized", AuthenticationError),
    ],
)
def test_error_code_is_mapped_to_a_domain_error(error_code: str, expected_error: type) -> None:
    with pytest.raises(expected_error):
        raise_for_api_error(error_response(error_code))


def test_error_message_comes_from_the_response_body() -> None:
    with pytest.raises(TicketNotFoundError, match="TF-99 does not exist"):
        raise_for_api_error(error_response("not_found", "TF-99 does not exist"))


def test_http_401_is_an_authentication_error() -> None:
    with pytest.raises(AuthenticationError):
        raise_for_api_error(make_response(401, text="nope"))


def test_rate_limit_reads_retry_after_and_reset_headers() -> None:
    response = make_response(
        429,
        {"err": "rate_limit_exceeded", "message": "Slow down"},
        headers={"retry-after": "7", "x-ratelimit-reset": "2026-01-01T10:00:00Z"},
    )

    with pytest.raises(RateLimitError) as caught:
        raise_for_api_error(response)

    assert caught.value.retry_after_seconds == 7
    assert caught.value.reset_at is not None


def test_rate_limit_without_headers_has_no_wait_hint() -> None:
    with pytest.raises(RateLimitError) as caught:
        raise_for_api_error(make_response(429, text="too many"))

    assert caught.value.retry_after_seconds is None
    assert caught.value.reset_at is None


def test_unknown_server_error_keeps_the_status_code() -> None:
    with pytest.raises(TicketForgeApiError) as caught:
        raise_for_api_error(make_response(500, {"err": "boom", "message": "Server down"}))

    assert caught.value.status_code == 500


def test_non_json_error_body_falls_back_to_raw_text() -> None:
    with pytest.raises(TicketForgeApiError, match="HTTP 502: Bad Gateway"):
        raise_for_api_error(make_response(502, text="Bad Gateway"))
