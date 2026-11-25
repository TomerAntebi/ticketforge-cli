from typing import Callable, Union

import pytest
import requests

from tests.conftest import make_response
from ticketforge.client.transport.rate_limit import (
    DEFAULT_WAIT_SECONDS,
    MAX_RATE_LIMIT_RETRIES,
    MAX_WAIT_SECONDS,
    retry_on_rate_limit,
)
from ticketforge.exceptions.errors import RateLimitError, TicketNotFoundError


def sender_that_returns(*outcomes: Union[requests.Response, Exception]) -> Callable[[], requests.Response]:
    """A send_request stub that plays back outcomes in order and counts calls."""
    queue = list(outcomes)

    def send_request() -> requests.Response:
        send_request.calls += 1  # type: ignore[attr-defined]
        outcome = queue.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    send_request.calls = 0  # type: ignore[attr-defined]
    return send_request


# --- Positive ---------------------------------------------------------------
def test_success_on_first_try_never_sleeps() -> None:
    sleeps: list[float] = []
    ok = make_response(200)

    result = retry_on_rate_limit(sender_that_returns(ok), sleep=sleeps.append)

    assert result is ok
    assert sleeps == []


def test_retries_after_a_rate_limit_and_waits_retry_after_seconds() -> None:
    sleeps: list[float] = []
    ok = make_response(200)
    send = sender_that_returns(RateLimitError("slow", retry_after_seconds=3), ok)

    result = retry_on_rate_limit(send, sleep=sleeps.append)

    assert result is ok
    assert sleeps == [3]


def test_uses_default_wait_when_server_sends_no_retry_after() -> None:
    sleeps: list[float] = []
    send = sender_that_returns(RateLimitError("slow"), make_response(200))

    retry_on_rate_limit(send, sleep=sleeps.append)

    assert sleeps == [DEFAULT_WAIT_SECONDS]


def test_retry_after_of_zero_is_respected_not_treated_as_missing() -> None:
    sleeps: list[float] = []
    send = sender_that_returns(RateLimitError("slow", retry_after_seconds=0), make_response(200))

    retry_on_rate_limit(send, sleep=sleeps.append)

    assert sleeps == [0]


# --- Negative ---------------------------------------------------------------
def test_gives_up_after_the_maximum_number_of_retries() -> None:
    sleeps: list[float] = []
    send = sender_that_returns(*[RateLimitError("slow", retry_after_seconds=1)] * (MAX_RATE_LIMIT_RETRIES + 1))

    with pytest.raises(RateLimitError):
        retry_on_rate_limit(send, sleep=sleeps.append)

    assert send.calls == MAX_RATE_LIMIT_RETRIES + 1  # type: ignore[attr-defined]
    assert len(sleeps) == MAX_RATE_LIMIT_RETRIES


def test_refuses_to_wait_longer_than_the_maximum() -> None:
    sleeps: list[float] = []
    send = sender_that_returns(RateLimitError("slow", retry_after_seconds=MAX_WAIT_SECONDS + 1))

    with pytest.raises(RateLimitError):
        retry_on_rate_limit(send, sleep=sleeps.append)

    assert sleeps == []
    assert send.calls == 1  # type: ignore[attr-defined]


def test_other_errors_are_not_retried() -> None:
    sleeps: list[float] = []
    send = sender_that_returns(TicketNotFoundError("missing"))

    with pytest.raises(TicketNotFoundError):
        retry_on_rate_limit(send, sleep=sleeps.append)

    assert send.calls == 1  # type: ignore[attr-defined]
    assert sleeps == []
