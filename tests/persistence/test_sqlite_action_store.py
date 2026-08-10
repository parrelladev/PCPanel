from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from app.actions.models import ActionDefinition
from app.persistence import (
    CorruptStoredActionError,
    Database,
    SQLiteActionStore,
    StoredAction,
)


def make_store(tmp_path: Path) -> tuple[Database, SQLiteActionStore]:
    database = Database(tmp_path)
    database.initialize()
    return database, SQLiteActionStore(database)


def make_action(
    action_id: str = "editor",
    *,
    arguments: tuple[str, ...] = ("--profile", "value with spaces"),
    working_directory: Path | None = Path("workspace"),
    enabled: bool = True,
) -> StoredAction:
    return StoredAction(
        definition=ActionDefinition(
            id=action_id,
            label=f"Open {action_id}",
            executable=Path(f"bin/{action_id}.exe"),
            arguments=arguments,
            working_directory=working_directory,
        ),
        enabled=enabled,
    )


def test_action_round_trip_preserves_all_fields(tmp_path: Path) -> None:
    _, store = make_store(tmp_path)
    record = make_action()

    store.save_action(record)

    assert store.load_actions() == (record,)
    loaded = store.load_actions()[0]
    assert loaded.definition.id == record.definition.id
    assert loaded.definition.label == record.definition.label
    assert loaded.definition.executable == record.definition.executable
    assert loaded.definition.arguments == ("--profile", "value with spaces")
    assert len(loaded.definition.arguments) == 2
    assert loaded.definition.working_directory == Path("workspace")
    assert isinstance(loaded.definition.executable, Path)
    assert loaded.enabled is True


def test_empty_arguments_and_none_working_directory_round_trip(tmp_path: Path) -> None:
    _, store = make_store(tmp_path)
    record = make_action(arguments=(), working_directory=None)

    store.save_action(record)

    loaded = store.load_actions()[0]
    assert loaded.definition.arguments == ()
    assert loaded.definition.working_directory is None


@pytest.mark.parametrize("enabled", [True, False])
def test_enabled_state_round_trip(tmp_path: Path, enabled: bool) -> None:
    _, store = make_store(tmp_path)

    store.save_action(make_action(enabled=enabled))

    assert store.load_actions()[0].enabled is enabled


def test_arguments_are_stored_as_structured_json(tmp_path: Path) -> None:
    database, store = make_store(tmp_path)
    arguments = ("--foo", "--bar", "value with spaces")
    store.save_action(make_action(arguments=arguments))

    with database.connection() as connection:
        stored = connection.execute(
            "SELECT executable, arguments_json FROM actions"
        ).fetchone()

    assert json.loads(stored["arguments_json"]) == list(arguments)
    assert stored["arguments_json"] != " ".join(arguments)
    assert stored["executable"] == str(Path("bin/editor.exe"))
    assert "--foo" not in stored["executable"]


def test_two_actions_are_persisted_separately(tmp_path: Path) -> None:
    _, store = make_store(tmp_path)
    first = make_action("editor")
    second = make_action("terminal", enabled=False)

    store.save_action(first)
    store.save_action(second)

    assert store.load_actions() == (first, second)


@pytest.mark.parametrize(
    ("stored_json", "message"),
    [
        ("not-json", "invalid JSON"),
        ('{"argument": "--foo"}', "JSON list"),
        ('["--foo", 42]', "items must all be strings"),
    ],
)
def test_corrupt_arguments_fail_clearly(
    tmp_path: Path,
    stored_json: str,
    message: str,
) -> None:
    database, store = make_store(tmp_path)
    store.save_action(make_action())
    with database.connection() as connection:
        connection.execute(
            "UPDATE actions SET arguments_json = ? WHERE id = 'editor'",
            (stored_json,),
        )

    with pytest.raises(CorruptStoredActionError, match=message):
        store.load_actions()


def test_invalid_action_definition_from_storage_is_rejected(tmp_path: Path) -> None:
    database, store = make_store(tmp_path)
    store.save_action(make_action())
    with database.connection() as connection:
        connection.execute("UPDATE actions SET id = 'Invalid ID'")

    with pytest.raises(CorruptStoredActionError, match="action id must match"):
        store.load_actions()


def test_invalid_enabled_value_is_rejected(tmp_path: Path) -> None:
    database, store = make_store(tmp_path)
    store.save_action(make_action())
    with database.connection() as connection:
        connection.execute("PRAGMA ignore_check_constraints = ON")
        connection.execute("UPDATE actions SET enabled = 2")

    with pytest.raises(CorruptStoredActionError, match="0 or 1"):
        store.load_actions()


def test_concurrent_saves_do_not_corrupt_database(tmp_path: Path) -> None:
    _, store = make_store(tmp_path)
    records = [make_action(f"action-{index}") for index in range(12)]

    with ThreadPoolExecutor(max_workers=4) as executor:
        list(executor.map(store.save_action, records))

    loaded = store.load_actions()
    assert len(loaded) == len(records)
    assert {record.definition.id for record in loaded} == {
        record.definition.id for record in records
    }
