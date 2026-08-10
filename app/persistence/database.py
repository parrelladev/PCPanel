from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from app.persistence.migrations import migrate


class Database:
    """Manage short-lived connections to PCPanel's local SQLite database."""

    filename = "pcpanel.db"

    def __init__(self, data_dir: str | Path, *, timeout: float = 5.0) -> None:
        self._data_dir = Path(data_dir)
        self._path = self._data_dir / self.filename
        self._timeout = timeout

    @property
    def path(self) -> Path:
        """Return the SQLite file used by this database."""
        return self._path

    def initialize(self) -> None:
        """Create the database and migrate its schema to the current version."""
        with self.connection() as connection:
            migrate(connection)

    @contextmanager
    def connection(self) -> Iterator[sqlite3.Connection]:
        """Open one configured connection and always close it after the operation."""
        self._prepare_data_dir()
        connection = sqlite3.connect(self._path, timeout=self._timeout)
        try:
            connection.row_factory = sqlite3.Row
            connection.execute("PRAGMA foreign_keys = ON")
            yield connection
            if connection.in_transaction:
                connection.commit()
        except BaseException:
            if connection.in_transaction:
                connection.rollback()
            raise
        finally:
            connection.close()

    def _prepare_data_dir(self) -> None:
        if self._data_dir.exists() and not self._data_dir.is_dir():
            raise NotADirectoryError(
                f"PCPanel data directory is not a directory: {self._data_dir}"
            )
        self._data_dir.mkdir(parents=True, exist_ok=True)
