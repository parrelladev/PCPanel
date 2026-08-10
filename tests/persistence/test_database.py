from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from app.persistence import Database


def test_initialize_creates_sqlite_file(tmp_path: Path) -> None:
    database = Database(tmp_path)

    database.initialize()

    assert database.path == tmp_path / "pcpanel.db"
    assert database.path.is_file()


def test_initialize_creates_data_directory(tmp_path: Path) -> None:
    data_dir = tmp_path / "nested" / "data"

    Database(data_dir).initialize()

    assert data_dir.is_dir()
    assert (data_dir / "pcpanel.db").is_file()


def test_connection_can_be_opened_and_is_configured(tmp_path: Path) -> None:
    database = Database(tmp_path)

    with database.connection() as connection:
        result = connection.execute("SELECT 1 AS value").fetchone()
        foreign_keys = connection.execute("PRAGMA foreign_keys").fetchone()

        assert result is not None
        assert result["value"] == 1
        assert foreign_keys is not None
        assert foreign_keys[0] == 1


def test_connection_is_closed_after_use(tmp_path: Path) -> None:
    database = Database(tmp_path)

    with database.connection() as connection:
        connection.execute("SELECT 1")

    with pytest.raises(sqlite3.ProgrammingError, match="closed database"):
        connection.execute("SELECT 1")


def test_two_consecutive_operations_work(tmp_path: Path) -> None:
    database = Database(tmp_path)

    with database.connection() as connection:
        connection.execute("CREATE TABLE values_table (value INTEGER NOT NULL)")
        connection.execute("INSERT INTO values_table VALUES (42)")

    with database.connection() as connection:
        result = connection.execute("SELECT value FROM values_table").fetchone()

    assert result is not None
    assert result["value"] == 42


def test_connections_are_independent(tmp_path: Path) -> None:
    database = Database(tmp_path)

    with database.connection() as first:
        with database.connection() as second:
            assert first is not second
            assert first.execute("SELECT 1").fetchone()[0] == 1
            assert second.execute("SELECT 2").fetchone()[0] == 2

        assert first.execute("SELECT 3").fetchone()[0] == 3

    with pytest.raises(sqlite3.ProgrammingError, match="closed database"):
        second.execute("SELECT 1")


def test_invalid_data_directory_fails_clearly(tmp_path: Path) -> None:
    invalid_data_dir = tmp_path / "not-a-directory"
    invalid_data_dir.write_text("occupied", encoding="utf-8")
    database = Database(invalid_data_dir)

    with pytest.raises(NotADirectoryError, match="not a directory"):
        database.initialize()

    assert not database.path.exists()


def test_database_is_confined_to_explicit_data_directory(tmp_path: Path) -> None:
    isolated_data_dir = tmp_path / "isolated"
    database = Database(isolated_data_dir)

    database.initialize()

    assert database.path.parent == isolated_data_dir
    assert list(tmp_path.glob("pcpanel.db")) == []
