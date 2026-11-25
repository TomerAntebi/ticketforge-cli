import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path

from ticketforge.exceptions.errors import ConfigurationError

DEFAULT_BASE_URL = "https://integrations-assignment-ticketforge.vercel.app"
DEFAULT_CONFIG_PATH = Path.home() / ".ticketforge" / "config.json"
OWNER_ONLY_FILE_MODE = 0o600
OWNER_ONLY_DIRECTORY_MODE = 0o700


@dataclass(frozen=True)
class Settings:
    base_url: str
    username: str
    password: str


class SettingsStore:
    """Persists connection settings. No HTTP: validating credentials is the setup flow's job."""

    def __init__(self, config_path: Path = DEFAULT_CONFIG_PATH) -> None:
        # Injectable so tests use a temp path instead of the real home directory.
        self._config_path = config_path

    def save(self, settings: Settings) -> None:
        self._config_path.parent.mkdir(
            parents=True, exist_ok=True, mode=OWNER_ONLY_DIRECTORY_MODE
        )
        # Open with the restrictive mode up front so the password is never
        # briefly readable by other users, as it would be with write-then-chmod.
        file_descriptor = os.open(
            self._config_path,
            os.O_WRONLY | os.O_CREAT | os.O_TRUNC,
            OWNER_ONLY_FILE_MODE,
        )
        with os.fdopen(file_descriptor, "w", encoding="utf-8") as config_file:
            json.dump(asdict(settings), config_file)

    def clear(self) -> bool:
        """Remove saved credentials. Returns False when nothing was saved."""
        try:
            self._config_path.unlink()
        except FileNotFoundError:
            return False
        return True

    def load(self) -> Settings:
        if not self._config_path.exists():
            raise ConfigurationError("Not configured yet. Run 'ticketforge setup' first.")
        try:
            raw_settings = json.loads(self._config_path.read_text(encoding="utf-8"))
            return Settings(
                base_url=raw_settings["base_url"],
                username=raw_settings["username"],
                password=raw_settings["password"],
            )
        except (json.JSONDecodeError, KeyError, TypeError) as error:
            raise ConfigurationError(
                f"Config file {self._config_path} is invalid. Run 'ticketforge setup' again."
            ) from error
