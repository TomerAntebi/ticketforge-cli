import pytest

from tests.conftest import FakeSession, error_response, make_response
from ticketforge.client.account_client import AccountClient
from ticketforge.exceptions.errors import UsernameTakenError

BASE_URL = "https://example.test"


def make_client(session: FakeSession) -> AccountClient:
    return AccountClient(BASE_URL + "/", session=session)  # type: ignore[arg-type]


# --- Positive ---------------------------------------------------------------
def test_register_posts_the_credentials() -> None:
    session = FakeSession(make_response(200, {"user": {"username": "tomer"}}))

    make_client(session).register_user("tomer", "secret")

    assert session.calls[0]["url"] == f"{BASE_URL}/api/tforge/user/register"
    assert session.calls[0]["json"] == {"username": "tomer", "password": "secret"}


# --- Negative ---------------------------------------------------------------
def test_existing_username_raises_username_taken() -> None:
    session = FakeSession(error_response("user_exists", "Username already exists"))

    with pytest.raises(UsernameTakenError):
        make_client(session).register_user("tomer", "secret")

