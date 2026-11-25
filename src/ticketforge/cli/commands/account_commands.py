import argparse
from getpass import getpass

from ticketforge.cli.output import BOLD, DIM, GREEN, colorize
from ticketforge.client.account_client import AccountClient
from ticketforge.client.ticket_client import TicketClient
from ticketforge.config.settings import DEFAULT_BASE_URL, Settings, SettingsStore
from ticketforge.services.ticket_service import TicketService


def add_account_parsers(
    subcommands: "argparse._SubParsersAction[argparse.ArgumentParser]",
) -> None:
    register = subcommands.add_parser("register", help="create a TicketForge account")
    register.add_argument("--username")
    register.add_argument("--base-url", default=DEFAULT_BASE_URL)
    register.set_defaults(handler=handle_register)

    setup = subcommands.add_parser("setup", help="log in and save credentials")
    setup.add_argument("--username")
    setup.add_argument("--base-url", default=DEFAULT_BASE_URL)
    setup.set_defaults(handler=handle_setup)

    whoami = subcommands.add_parser("whoami", help="show the logged-in account")
    whoami.set_defaults(handler=handle_whoami)

    logout = subcommands.add_parser("logout", help="remove saved credentials")
    logout.set_defaults(handler=handle_logout)


def prompt_credentials(args: argparse.Namespace) -> tuple[str, str]:
    """Ask only for what was not passed as a flag; the password is never a flag."""
    username = args.username or input("Username: ").strip()
    return username, getpass("Password: ")


def handle_register(args: argparse.Namespace, store: SettingsStore) -> None:
    username, password = prompt_credentials(args)
    AccountClient(args.base_url).register_user(username, password)
    print(f"{colorize('Account created', GREEN)} for {username}. Run 'ticketforge setup' to log in.")


def handle_setup(args: argparse.Namespace, store: SettingsStore) -> None:
    username, password = prompt_credentials(args)
    TicketService(TicketClient(args.base_url, username, password)).verify_credentials()
    store.save(Settings(base_url=args.base_url, username=username, password=password))
    print(f"{colorize('Logged in', GREEN)} as {colorize(username, BOLD)}. Settings saved.")


def handle_whoami(args: argparse.Namespace, store: SettingsStore) -> None:
    # Reads the saved file only; the password is never printed.
    settings = store.load()
    print(f"{colorize(settings.username, BOLD)} {colorize('@ ' + settings.base_url, DIM)}")


def handle_logout(args: argparse.Namespace, store: SettingsStore) -> None:
    if store.clear():
        print(f"{colorize('Logged out', GREEN)}. Saved credentials removed.")
    else:
        print("You are not logged in.")
