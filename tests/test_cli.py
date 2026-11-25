"""CLI tests: real argument parsing and real printing, fake API and fake config path."""

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional, Sequence

import pytest

import ticketforge.cli.main as main_module
import ticketforge.cli.commands.account_commands as account_module
import ticketforge.cli.commands.ticket_commands as ticket_module
from tests.conftest import FailingGateway, FakeGateway, make_page, make_ticket
from ticketforge.cli.main import build_parser, run
from ticketforge.config.settings import DEFAULT_BASE_URL, Settings, SettingsStore
from ticketforge.exceptions.errors import (
    AuthenticationError,
    RateLimitError,
    TicketForgeError,
    UsernameTakenError,
)
from ticketforge.models.api_models import TicketStage, User
from ticketforge.services.ticket_service import TicketService


@pytest.fixture
def store(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> SettingsStore:
    """Point the CLI at a temp config file instead of ~/.ticketforge."""
    temp_store = SettingsStore(tmp_path / "config.json")
    monkeypatch.setattr(main_module, "SettingsStore", lambda: temp_store)
    return temp_store


def use_gateway(monkeypatch: pytest.MonkeyPatch, gateway: Any) -> None:
    """Make ticket commands talk to a fake gateway instead of saved credentials."""
    monkeypatch.setattr(ticket_module, "create_ticket_service", lambda store: TicketService(gateway))


def set_interactive(monkeypatch: pytest.MonkeyPatch, answers: Sequence[str]) -> None:
    monkeypatch.setattr(ticket_module, "is_terminal_session", lambda: True)
    queue = list(answers)

    def fake_input(prompt: str = "") -> str:
        if not queue:
            raise EOFError
        return queue.pop(0)

    monkeypatch.setattr("builtins.input", fake_input)


# --- Argument parsing -------------------------------------------------------
def test_update_rejects_an_unknown_stage() -> None:
    with pytest.raises(SystemExit):
        build_parser().parse_args(["update", "TF-1", "--stage", "archived"])


def test_update_depends_on_distinguishes_omitted_from_empty() -> None:
    parser = build_parser()

    omitted = parser.parse_args(["update", "TF-1", "--title", "x"])
    cleared = parser.parse_args(["update", "TF-1", "--depends-on"])
    replaced = parser.parse_args(["update", "TF-1", "--depends-on", "TF-2", "TF-3"])

    assert omitted.depends_on is None
    assert cleared.depends_on == []
    assert replaced.depends_on == ["TF-2", "TF-3"]


# --- Exit codes and error output --------------------------------------------
def test_domain_error_returns_one_and_prints_to_stderr(
    store: SettingsStore, capsys: pytest.CaptureFixture[str]
) -> None:
    # Nothing saved yet, so whoami raises ConfigurationError.
    exit_code = run(["whoami"])

    captured = capsys.readouterr()
    assert exit_code == 1
    assert "Error:" in captured.err
    assert "ticketforge setup" in captured.err
    assert captured.out == ""


def test_rate_limit_error_tells_the_user_how_long_to_wait(
    store: SettingsStore, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    use_gateway(monkeypatch, FailingGateway(RateLimitError("Slow down", retry_after_seconds=30)))

    exit_code = run(["list"])

    assert exit_code == 1
    assert "Try again in 30 seconds" in capsys.readouterr().err


# --- list -------------------------------------------------------------------
def test_list_with_no_tickets_says_so(
    store: SettingsStore, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    use_gateway(monkeypatch, FakeGateway(pages=[make_page([])]))

    run(["list"])

    assert "No tickets found." in capsys.readouterr().out


def test_list_all_prints_every_page_and_the_total(
    store: SettingsStore, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    gateway = FakeGateway(
        pages=[
            make_page([make_ticket("TF-1"), make_ticket("TF-2")], has_more=True, next_cursor="c1"),
            make_page([make_ticket("TF-3")]),
        ]
    )
    use_gateway(monkeypatch, gateway)

    run(["list", "--all"])

    output = capsys.readouterr().out
    assert all(ref in output for ref in ("TF-1", "TF-2", "TF-3"))
    assert "Showing 3 ticket(s) in total." in output


def test_list_all_with_no_tickets_says_so(
    store: SettingsStore, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    use_gateway(monkeypatch, FakeGateway(pages=[make_page([])]))

    run(["list", "--all"])

    assert "No tickets found." in capsys.readouterr().out


def test_list_passes_the_limit_to_the_api(
    store: SettingsStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    gateway = FakeGateway(pages=[make_page([make_ticket()])])
    use_gateway(monkeypatch, gateway)

    run(["list", "--limit", "2"])

    assert gateway.list_calls == [{"limit": 2, "cursor": None}]


def test_piped_list_shows_one_page_and_a_hint_instead_of_prompting(
    store: SettingsStore, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    gateway = FakeGateway(
        pages=[make_page([make_ticket("TF-1")], has_more=True, next_cursor="c1")]
    )
    use_gateway(monkeypatch, gateway)
    monkeypatch.setattr(ticket_module, "is_terminal_session", lambda: False)

    run(["list"])

    captured = capsys.readouterr()
    assert "TF-1" in captured.out
    assert "Use --all" in captured.err
    assert len(gateway.list_calls) == 1


def test_interactive_list_shows_the_next_page_on_enter(
    store: SettingsStore, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    gateway = FakeGateway(
        pages=[
            make_page([make_ticket("TF-1")], has_more=True, next_cursor="c1"),
            make_page([make_ticket("TF-2")]),
        ]
    )
    use_gateway(monkeypatch, gateway)
    set_interactive(monkeypatch, [""])

    run(["list"])

    output = capsys.readouterr().out
    assert "TF-1" in output and "TF-2" in output


@pytest.mark.parametrize("answers", [["q"], []])
def test_interactive_list_stops_on_quit_or_end_of_input(
    store: SettingsStore, monkeypatch: pytest.MonkeyPatch, answers: list[str]
) -> None:
    gateway = FakeGateway(
        pages=[make_page([make_ticket("TF-1")], has_more=True, next_cursor="c1")]
    )
    use_gateway(monkeypatch, gateway)
    set_interactive(monkeypatch, answers)

    assert run(["list"]) == 0
    assert len(gateway.list_calls) == 1


# --- show -------------------------------------------------------------------
def test_show_prints_every_detail_of_the_ticket(
    store: SettingsStore, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    ticket = make_ticket("TF-7", title="Fix login", stage=TicketStage.REVIEW, depends_on=("TF-2", "TF-3"))
    use_gateway(monkeypatch, FakeGateway(tickets=[ticket]))

    exit_code = run(["show", "TF-7"])

    output = capsys.readouterr().out
    assert exit_code == 0
    assert "TF-7" in output and "Fix login" in output
    assert "review" in output
    assert "TF-2, TF-3" in output
    assert "Users cannot log in" in output
    assert "2026-01-01 00:00 UTC" in output


def test_show_prints_a_dash_for_missing_optional_values(
    store: SettingsStore, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    ticket = make_ticket("TF-8", description=None)
    use_gateway(monkeypatch, FakeGateway(tickets=[ticket]))

    run(["show", "TF-8"])

    lines = {line.split()[0]: line for line in capsys.readouterr().out.splitlines()}
    assert lines["Updated"].split()[-1] == "-"
    assert lines["Description"].split()[-1] == "-"
    assert lines["Depends"].split()[-1] == "-"


def test_show_of_an_unknown_ticket_fails(
    store: SettingsStore, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    use_gateway(monkeypatch, FakeGateway())

    assert run(["show", "TF-999"]) == 1
    assert "not found" in capsys.readouterr().err


# --- create -----------------------------------------------------------------
def test_create_prints_the_new_ticket(
    store: SettingsStore, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    gateway = FakeGateway()
    use_gateway(monkeypatch, gateway)

    exit_code = run(["create", "New thing", "--description", "Details", "--depends-on", "TF-2"])

    assert exit_code == 0
    assert "Created" in capsys.readouterr().out
    assert gateway.created[0] == {
        "title": "New thing",
        "description": "Details",
        "depends_on": ["TF-2"],
    }


# --- update -----------------------------------------------------------------
def test_update_prints_the_updated_ticket(
    store: SettingsStore, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    use_gateway(monkeypatch, FakeGateway(tickets=[make_ticket()]))

    exit_code = run(["update", "TF-1", "--stage", "closed"])

    assert exit_code == 0
    assert "Updated TF-1 [closed]" in capsys.readouterr().out


# --- register ---------------------------------------------------------------
def make_user(username: str) -> User:
    return User(id="u1", username=username, created=datetime(2026, 1, 1, tzinfo=timezone.utc))


class FakeAccountClient:
    def __init__(self, error: Optional[TicketForgeError] = None) -> None:
        self._error = error

    def register_user(self, username: str, password: str) -> User:
        if self._error:
            raise self._error
        return make_user(username)


def test_register_reports_the_created_account(
    store: SettingsStore, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(account_module, "getpass", lambda prompt: "secret")
    monkeypatch.setattr(account_module, "AccountClient", lambda base_url: FakeAccountClient())

    assert run(["register", "--username", "tomer"]) == 0
    assert "Account created for tomer" in capsys.readouterr().out


def test_register_with_a_taken_username_fails(
    store: SettingsStore, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(account_module, "getpass", lambda prompt: "secret")
    monkeypatch.setattr(
        account_module,
        "AccountClient",
        lambda base_url: FakeAccountClient(UsernameTakenError("Username already exists")),
    )

    assert run(["register", "--username", "tomer"]) == 1
    assert "already exists" in capsys.readouterr().err


# --- setup / whoami / logout ------------------------------------------------
def test_setup_saves_credentials_after_a_successful_login(
    store: SettingsStore, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(account_module, "getpass", lambda prompt: "secret")
    gateway = FakeGateway(pages=[make_page([])])
    monkeypatch.setattr(account_module, "TicketClient", lambda *args: gateway)

    assert run(["setup", "--username", "tomer"]) == 0

    assert store.load() == Settings(DEFAULT_BASE_URL, "tomer", "secret")
    assert gateway.list_calls == [{"limit": 1, "cursor": None}]
    assert "Logged in" in capsys.readouterr().out


def test_setup_does_not_save_credentials_when_login_fails(
    store: SettingsStore, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(account_module, "getpass", lambda prompt: "wrong")
    monkeypatch.setattr(
        account_module, "TicketClient", lambda *args: FailingGateway(AuthenticationError("Bad login"))
    )

    assert run(["setup", "--username", "tomer"]) == 1

    assert store.clear() is False  # nothing was written
    assert "Bad login" in capsys.readouterr().err


def test_whoami_shows_the_user_but_never_the_password(
    store: SettingsStore, capsys: pytest.CaptureFixture[str]
) -> None:
    store.save(Settings("https://example.test", "tomer", "super-secret"))

    assert run(["whoami"]) == 0

    output = capsys.readouterr().out
    assert "tomer" in output and "https://example.test" in output
    assert "super-secret" not in output


def test_logout_removes_credentials_and_then_reports_not_logged_in(
    store: SettingsStore, capsys: pytest.CaptureFixture[str]
) -> None:
    store.save(Settings("https://example.test", "tomer", "secret"))

    assert run(["logout"]) == 0
    assert "Logged out" in capsys.readouterr().out

    assert run(["logout"]) == 0
    assert "You are not logged in." in capsys.readouterr().out

