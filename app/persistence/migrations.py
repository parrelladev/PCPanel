from __future__ import annotations

import sqlite3
from collections.abc import Callable


CURRENT_SCHEMA_VERSION = 1


class UnsupportedSchemaVersionError(RuntimeError):
    """Raised when a database was created by a newer PCPanel version."""

    def __init__(self, found: int, supported: int) -> None:
        self.found = found
        self.supported = supported
        super().__init__(
            "SQLite schema version "
            f"{found} is newer than the supported version {supported}"
        )


SCHEMA_V1 = (
    """
    CREATE TABLE devices (
        device_id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        status TEXT NOT NULL,
        created_at TEXT NOT NULL,
        authorized_at TEXT,
        revoked_at TEXT,
        token_hash TEXT
    )
    """,
    """
    CREATE TABLE actions (
        id TEXT PRIMARY KEY,
        label TEXT NOT NULL,
        executable TEXT NOT NULL,
        arguments_json TEXT NOT NULL DEFAULT '[]',
        working_directory TEXT,
        enabled INTEGER NOT NULL DEFAULT 1 CHECK (enabled IN (0, 1))
    )
    """,
)

Migration = Callable[[sqlite3.Connection], None]


def _migrate_0_to_1(connection: sqlite3.Connection) -> None:
    for statement in SCHEMA_V1:
        connection.execute(statement)


_MIGRATIONS: dict[int, Migration] = {
    0: _migrate_0_to_1,
}


def migrate(connection: sqlite3.Connection) -> None:
    """Atomically migrate a SQLite connection to the current schema version."""
    row = connection.execute("PRAGMA user_version").fetchone()
    version = int(row[0])

    if version > CURRENT_SCHEMA_VERSION:
        raise UnsupportedSchemaVersionError(version, CURRENT_SCHEMA_VERSION)
    if version == CURRENT_SCHEMA_VERSION:
        return

    connection.execute("BEGIN IMMEDIATE")
    try:
        while version < CURRENT_SCHEMA_VERSION:
            try:
                migration = _MIGRATIONS[version]
            except KeyError:
                raise RuntimeError(
                    f"no SQLite migration registered for schema version {version}"
                ) from None

            migration(connection)
            version += 1
            connection.execute(f"PRAGMA user_version = {version}")
        connection.commit()
    except BaseException:
        connection.rollback()
        raise
