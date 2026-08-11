from __future__ import annotations

import os
import shutil
import sqlite3
from contextlib import closing
from pathlib import Path
from uuid import uuid4

from .database import Database
from .migrations import CURRENT_SCHEMA_VERSION
from .permissions import harden_user_data_directory


class DataMigrationError(RuntimeError):
    pass


def migrate_database(source_dir: Path, destination_dir: Path) -> Path:
    """Recoverably copy one explicitly selected PCPanel database."""

    source = source_dir / Database.filename
    destination = destination_dir / Database.filename
    if not source.is_file():
        raise FileNotFoundError(f"Source PCPanel database was not found: {source}")
    if destination.exists():
        raise FileExistsError(f"Destination PCPanel database already exists: {destination}")

    destination_dir.mkdir(parents=True, exist_ok=True)
    harden_user_data_directory(destination_dir)
    temporary = destination_dir / f".{Database.filename}.migrating-{uuid4().hex}"
    try:
        shutil.copy2(source, temporary)
        _validate_database(temporary)
        os.replace(temporary, destination)
        return destination
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise


def _validate_database(path: Path) -> None:
    try:
        with closing(sqlite3.connect(f"file:{path}?mode=ro", uri=True)) as connection:
            result = connection.execute("PRAGMA quick_check").fetchone()
            version = int(connection.execute("PRAGMA user_version").fetchone()[0])
            tables = {
                row[0]
                for row in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table'"
                )
            }
    except sqlite3.DatabaseError as exc:
        raise DataMigrationError("Source database is not a valid SQLite database") from exc
    if result is None or result[0] != "ok":
        raise DataMigrationError("Source database failed SQLite integrity validation")
    if version > CURRENT_SCHEMA_VERSION:
        raise DataMigrationError("Source database schema is newer than this PCPanel version")
    if not {"devices", "actions"}.issubset(tables):
        raise DataMigrationError("Source database does not contain the PCPanel schema")
