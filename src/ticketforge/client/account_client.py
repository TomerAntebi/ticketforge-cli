from typing import Optional

import requests

from ticketforge.client.transport.api_transport import DEFAULT_TIMEOUT_SECONDS, ApiTransport


class AccountClient:
    """Unauthenticated calls: registration happens before credentials exist."""

    _REGISTER_PATH = "/api/tforge/user/register"

    def __init__(
        self,
        base_url: str,
        session: Optional[requests.Session] = None,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    ) -> None:
        self._transport = ApiTransport(base_url, session, timeout_seconds)

    def register_user(self, username: str, password: str) -> None:
        # The response is not needed: the caller already knows the username it sent.
        self._transport.request_with_retry(
            "POST", self._REGISTER_PATH, {"username": username, "password": password}
        )
