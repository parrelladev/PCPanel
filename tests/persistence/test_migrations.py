from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from app.persistence import (
    CURRENT_SCHEMA_VERSION,
    Database,
    UnsupportedSchemaVersionError,
)
from app.persistence import migrations


def user_version(database: Database) -> int:
    with database.connection() as connection:
        return int(connection.execute("PRAGMA user_version").fetchone()[0])


def table_names(database: Database) -> set[str]:
    with database.connection() as connection:
        rows = connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        ).fetchall()
    return {str(row["name"]) for row in rows}


def column_names(database: Database, table: str) -> set[str]:
    with database.connection() as connection:
        rows = connection.execute(f"PRAGMA table_info({table})").fetchall()
    return {str(row["name"]) for row in rows}


def test_fresh_database_creates_current_schema(tmp_path: Path) -> None:
    database = Database(tmp_path)

    database.initialize()

    assert database.path.is_file()
    assert user_version(database) == CURRENT_SCHEMA_VERSION == 1
    assert table_names(database) == {"actions", "devices"}


def test_initial_schema_has_expected_columns(tmp_path: Path) -> None:
    database = Database(tmp_path)
    database.initialize()

    assert column_names(database, "devices") == {
        "authorized_at",
        "created_at",
        "device_id",
        "name",
        "revoked_at",
        "status",
        "token_hash",
    }
    assert column_names(database, "actions") == {
        "arguments_json",
        "enabled",
        "executable",
        "id",
        "label",
        "working_directory",
    }


def test_repeated_initialization_is_idempotent(tmp_path: Path) -> None:
    database = Database(tmp_path)
    database.initialize()

    with database.connection() as connection:
        connection.execute(
            "INSERT INTO actions (id, label, executable) VALUES (?, ?, ?)",
            ("terminal", "Terminal", "terminal.exe"),
        )

    database.initialize()

    with database.connection() as connection:
        count = connection.execute("SELECT COUNT(*) FROM actions").fetchone()[0]
    assert count == 1
    assert user_version(database) == CURRENT_SCHEMA_VERSION


def test_database_at_current_version_initializes_normally(tmp_path: Path) -> None:
    database = Database(tmp_path)
    database.initialize()

    database.initialize()

    assert table_names(database) == {"actions", "devices"}


def test_future_schema_version_fails_clearly(tmp_path: Path) -> None:
    database = Database(tmp_path)
    with database.connection() as connection:
        connection.execute(f"PRAGMA user_version = {CURRENT_SCHEMA_VERSION + 1}")

    with pytest.raises(UnsupportedSchemaVersionError) as exc_info:
        database.initialize()

    assert exc_info.value.found == 2
    assert exc_info.value.supported == 1
    assert user_version(database) == 2


def test_failed_migration_is_rolled_back(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    database = Database(tmp_path)

    def failing_migration(connection: sqlite3.Connection) -> None:
        connection.execute("CREATE TABLE partial_state (id INTEGER)")
        raise RuntimeError("migration failed")

    monkeypatch.setitem(migrations._MIGRATIONS, 0, failing_migration)

    with pytest.raises(RuntimeError, match="migration failed"):
        database.initialize()

    assert user_version(database) == 0
    assert "partial_state" not in table_names(database)


def test_schema_never_stores_plaintext_tokens(tmp_path: Path) -> None:
    database = Database(tmp_path)
    database.initialize()

    all_columns = column_names(database, "devices") | column_names(database, "actions")

    assert "token" not in all_columns
    assert "token_plaintext" not in all_columns
    assert "token_hash" in all_columns


def test_schema_does_not_persist_pairing_sessions(tmp_path: Path) -> None:
    database = Database(tmp_path)
    database.initialize()

    normalized_names = {name.lower() for name in table_names(database)}

    assert "pairingsession" not in normalized_names
    assert "pairing_session" not in normalized_names
    assert normalized_names == {"actions", "devices"}
