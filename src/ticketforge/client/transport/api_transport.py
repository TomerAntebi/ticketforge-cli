from typing import Optional

import requests

from ticketforge.client.transport.error_mapping import raise_for_api_error
from ticketforge.client.transport.rate_limit import retry_on_rate_limit
from ticketforge.exceptions.errors import TicketForgeConnectionError

DEFAULT_TIMEOUT_SECONDS = 10.0


class ApiTransport:
    """What every TicketForge call needs, in one place: URL, timeout, error mapping, 429 retry.

    Clients decide *which* endpoint to call; this class decides *how* a request is sent.
    """

    def __init__(
        self,
        base_url: str,
        session: Optional[requests.Session] = None,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
        auth: Optional[tuple[str, str]] = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout_seconds = timeout_seconds
        # Session is injectable so tests can stub HTTP without a network.
        self._session = session or requests.Session()
        if auth is not None:
            self._session.auth = auth

    def request_with_retry(
        self,
        method: str,
        path: str,
        json_body: Optional[dict[str, object]] = None,
        query: Optional[dict[str, object]] = None,
    ) -> requests.Response:
        return retry_on_rate_limit(lambda: self._request(method, path, json_body, query))

    def _request(
        self,
        method: str,
        path: str,
        json_body: Optional[dict[str, object]],
        query: Optional[dict[str, object]],
    ) -> requests.Response:
        try:
            response = self._session.request(
                method,
                f"{self._base_url}{path}",
                json=json_body,
                params=query,
                timeout=self._timeout_seconds,
            )
        except requests.RequestException as error:
            raise TicketForgeConnectionError(str(error)) from error
        raise_for_api_error(response)
        return response
