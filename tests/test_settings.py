import os
import stat
from pathlib import Path

import pytest

from ticketforge.config.settings import Settings, SettingsStore
from ticketforge.exceptions.errors import ConfigurationError

SETTINGS = Settings(base_url="https://example.test", username="tomer", password="secret")


@pytest.fixture
def store(tmp_path: Path) -> SettingsStore:
    # A temp path keeps tests away from the real ~/.ticketforge/config.json.
    return SettingsStore(tmp_path / "nested" / "config.json")


# --- Positive ---------------------------------------------------------------
def test_saved_settings_can_be_loaded_back(store: SettingsStore) -> None:
    store.save(SETTINGS)

    assert store.load() == SETTINGS


@pytest.mark.skipif(os.name == "nt", reason="POSIX file modes only")
def test_config_file_is_readable_by_the_owner_only(store: SettingsStore, tmp_path: Path) -> None:
    store.save(SETTINGS)

    mode = stat.S_IMODE((tmp_path / "nested" / "config.json").stat().st_mode)
    assert mode == 0o600


def test_delete_removes_the_file_and_reports_true(store: SettingsStore) -> None:
    store.save(SETTINGS)

    assert store.delete() is True
    with pytest.raises(ConfigurationError):
        store.load()


# --- Negative ---------------------------------------------------------------
def test_delete_with_nothing_saved_returns_false(store: SettingsStore) -> None:
    assert store.delete() is False


def test_load_before_setup_asks_the_user_to_run_setup(store: SettingsStore) -> None:
    with pytest.raises(ConfigurationError, match="ticketforge setup"):
        store.load()


def test_corrupt_json_is_reported_as_a_configuration_error(tmp_path: Path) -> None:
    config_path = tmp_path / "config.json"
    config_path.write_text("{not json", encoding="utf-8")

    with pytest.raises(ConfigurationError, match="invalid"):
        SettingsStore(config_path).load()

