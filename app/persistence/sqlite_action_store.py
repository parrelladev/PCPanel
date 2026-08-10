from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from app.actions.models import ActionDefinition
from app.persistence.action_store import StoredAction
from app.persistence.database import Database


class ActionPersistenceError(RuntimeError):
    """Base error for durable action configuration."""


class CorruptStoredActionError(ActionPersistenceError):
    """Raised when a stored row cannot reconstruct a valid action."""


class SQLiteActionStore:
    """Persist structured action configuration in SQLite."""

    def __init__(self, database: Database) -> None:
        self._database = database

    def load_actions(self) -> tuple[StoredAction, ...]:
        with self._database.connection() as connection:
            rows = connection.execute(
                """
                SELECT id, label, executable, arguments_json,
                       working_directory, enabled
                FROM actions
                ORDER BY id
                """
            ).fetchall()
        return tuple(self._decode_row(row) for row in rows)

    def save_action(self, record: StoredAction) -> None:
        definition = record.definition
        arguments_json = json.dumps(
            list(definition.arguments),
            ensure_ascii=False,
            separators=(",", ":"),
        )
        with self._database.connection() as connection:
            connection.execute(
                """
                INSERT INTO actions (
                    id, label, executable, arguments_json,
                    working_directory, enabled
                ) VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    label = excluded.label,
                    executable = excluded.executable,
                    arguments_json = excluded.arguments_json,
                    working_directory = excluded.working_directory,
                    enabled = excluded.enabled
                """,
                (
                    definition.id,
                    definition.label,
                    str(definition.executable),
                    arguments_json,
                    (
                        str(definition.working_directory)
                        if definition.working_directory is not None
                        else None
                    ),
                    int(record.enabled),
                ),
            )

    def delete_action(self, action_id: str) -> None:
        with self._database.connection() as connection:
            connection.execute("DELETE FROM actions WHERE id = ?", (action_id,))

    @classmethod
    def _decode_row(cls, row: sqlite3.Row) -> StoredAction:
        action_id = row["id"]
        try:
            cls._require_string(action_id, "id")
            label = cls._require_string(row["label"], "label")
            executable = cls._require_string(row["executable"], "executable")
            working_directory_value = row["working_directory"]
            if working_directory_value is not None:
                cls._require_string(working_directory_value, "working_directory")
            arguments = cls._decode_arguments(row["arguments_json"])
            enabled = cls._decode_enabled(row["enabled"])
            definition = ActionDefinition(
                id=action_id,
                label=label,
                executable=Path(executable),
                arguments=arguments,
                working_directory=(
                    Path(working_directory_value)
                    if working_directory_value is not None
                    else None
                ),
            )
            return StoredAction(definition=definition, enabled=enabled)
        except (TypeError, ValueError) as exc:
            raise CorruptStoredActionError(
                f"persisted action {action_id!r} contains invalid data: {exc}"
            ) from exc

    @staticmethod
    def _decode_arguments(value: object) -> tuple[str, ...]:
        if not isinstance(value, str):
            raise ValueError("arguments_json is not a JSON string")
        try:
            decoded = json.loads(value)
        except json.JSONDecodeError as exc:
            raise ValueError("arguments_json contains invalid JSON") from exc
        if not isinstance(decoded, list):
            raise ValueError("arguments_json must contain a JSON list")
        if not all(isinstance(item, str) for item in decoded):
            raise ValueError("arguments_json items must all be strings")
        return tuple(decoded)

    @staticmethod
    def _decode_enabled(value: object) -> bool:
        if type(value) is not int or value not in (0, 1):
            raise ValueError("enabled must be the SQLite integer 0 or 1")
        return bool(value)

    @staticmethod
    def _require_string(value: object, field: str) -> str:
        if not isinstance(value, str):
            raise ValueError(f"{field} must be a string")
        return value
