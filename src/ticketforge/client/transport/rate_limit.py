import logging
import time
from typing import Callable

import requests

from ticketforge.exceptions.errors import RateLimitError

logger = logging.getLogger(__name__)

MAX_RATE_LIMIT_RETRIES = 2
MAX_WAIT_SECONDS = 60
DEFAULT_WAIT_SECONDS = 5  # used only when the server sends no Retry-After


def retry_on_rate_limit(
    send_request: Callable[[], requests.Response],
    sleep: Callable[[float], None] = time.sleep,
    max_retries: int = MAX_RATE_LIMIT_RETRIES,
) -> requests.Response:
    """Run `send_request`, waiting and retrying when the API answers 429.

    Only RateLimitError is retried: it means the request was rejected before
    processing, so repeating a POST cannot create duplicates. Timeouts and 5xx
    are deliberately not retried for the same reason.
    """
    attempt = 0
    while True:
        try:
            return send_request()
        except RateLimitError as error:
            wait_seconds = (
                DEFAULT_WAIT_SECONDS
                if error.retry_after_seconds is None
                else error.retry_after_seconds
            )
            if attempt >= max_retries or wait_seconds > MAX_WAIT_SECONDS:
                raise
            attempt += 1
            logger.warning(
                "Rate limit reached. Retrying in %d seconds (attempt %d of %d)...",
                wait_seconds,
                attempt,
                max_retries,
            )
            sleep(wait_seconds)
