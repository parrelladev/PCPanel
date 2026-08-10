from __future__ import annotations

from pathlib import Path
from unittest.mock import Mock

import pytest

from app.actions import ActionDefinition
from app.persistence import Database, SQLiteActionStore, StoredAction
from scripts import seed_actions


def store_for(data_dir: Path) -> SQLiteActionStore:
    database = Database(data_dir)
    database.initialize()
    return SQLiteActionStore(database)


def test_fresh_database_has_no_automatic_actions(tmp_path: Path) -> None:
    store = store_for(tmp_path)

    assert store.load_actions() == ()


def test_development_seed_runs_only_when_explicitly_called(tmp_path: Path) -> None:
    store = store_for(tmp_path)
    assert store.load_actions() == ()

    created = seed_actions.seed_development_actions(
        store,
        windows_directory=Path("C:/Windows"),
    )

    assert created is True
    records = store.load_actions()
    assert len(records) == 1
    assert records[0].definition.id == "notepad"
    assert records[0].definition.arguments == ()
    assert records[0].enabled is True


def test_repeated_seed_does_not_duplicate_action(tmp_path: Path) -> None:
    first_store = store_for(tmp_path)
    assert seed_actions.seed_development_actions(first_store) is True

    restarted_store = store_for(tmp_path)
    assert seed_actions.seed_development_actions(restarted_store) is False

    assert len(restarted_store.load_actions()) == 1


def test_removed_seed_does_not_reappear_on_restart(tmp_path: Path) -> None:
    store = store_for(tmp_path)
    seed_actions.seed_development_actions(store)
    store.delete_action("notepad")

    restarted_store = store_for(tmp_path)

    assert restarted_store.load_actions() == ()


def test_seed_never_overwrites_existing_user_configuration(tmp_path: Path) -> None:
    store = store_for(tmp_path)
    configured = StoredAction(
        ActionDefinition(
            id="notepad",
            label="My custom editor",
            executable=Path("custom/notepad.exe"),
            arguments=("--custom", "value with spaces"),
            working_directory=Path("custom"),
        ),
        enabled=False,
    )
    store.save_action(configured)

    created = seed_actions.seed_development_actions(store)

    assert created is False
    assert store.load_actions() == (configured,)


def test_seed_constructs_action_through_domain_model(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = store_for(tmp_path)
    constructor = Mock(wraps=ActionDefinition)
    monkeypatch.setattr(seed_actions, "ActionDefinition", constructor)

    seed_actions.seed_development_actions(
        store,
        windows_directory=Path(r"C:\Windows"),
    )

    constructor.assert_called_once_with(
        id="notepad",
        label="Notepad",
        executable=Path(r"C:\Windows") / "System32" / "notepad.exe",
        arguments=(),
        working_directory=None,
    )
