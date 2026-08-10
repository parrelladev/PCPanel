from __future__ import annotations

import inspect
from pathlib import Path
from typing import get_type_hints

import pytest

from app.actions.models import ActionDefinition
from app.persistence.action_store import ActionStore, StoredAction


def action_definition() -> ActionDefinition:
    return ActionDefinition(
        id="editor",
        label="Open editor",
        executable=Path("editor.exe"),
        arguments=("--profile", "PC Panel"),
        working_directory=Path("workspace"),
    )


def test_stored_action_keeps_enabled_outside_domain_definition() -> None:
    definition = action_definition()

    record = StoredAction(definition=definition, enabled=False)

    assert record.definition is definition
    assert record.enabled is False
    assert not hasattr(definition, "enabled")


def test_stored_action_requires_validated_domain_definition() -> None:
    with pytest.raises(TypeError, match="must be an ActionDefinition"):
        StoredAction(definition={"id": "editor"})  # type: ignore[arg-type]


def test_stored_action_requires_boolean_enabled_state() -> None:
    with pytest.raises(TypeError, match="enabled must be a bool"):
        StoredAction(action_definition(), enabled=1)  # type: ignore[arg-type]


def test_arguments_remain_structured_tuple() -> None:
    record = StoredAction(action_definition())

    assert record.definition.arguments == ("--profile", "PC Panel")
    assert isinstance(record.definition.arguments, tuple)
    assert not hasattr(record, "command_line")
    assert not hasattr(record.definition, "command_line")


def test_contract_uses_only_python_and_domain_friendly_types() -> None:
    assert get_type_hints(ActionStore.load_actions)["return"] == tuple[
        StoredAction, ...
    ]
    assert get_type_hints(ActionStore.save_action) == {
        "record": StoredAction,
        "return": type(None),
    }
    assert get_type_hints(ActionStore.delete_action) == {
        "action_id": str,
        "return": type(None),
    }


def test_contract_exposes_no_sqlite_or_command_line_details() -> None:
    source = Path(inspect.getfile(ActionStore)).read_text(encoding="utf-8")
    signatures = " ".join(
        str(inspect.signature(method))
        for method in (
            ActionStore.load_actions,
            ActionStore.save_action,
            ActionStore.delete_action,
        )
    )

    assert "sqlite3" not in source
    assert "Connection" not in signatures
    assert "Cursor" not in signatures
    assert "Row" not in signatures
    assert "command_line" not in source


def test_plain_python_store_can_satisfy_protocol_shape() -> None:
    class MemoryActionStore:
        def __init__(self) -> None:
            self.records: dict[str, StoredAction] = {}

        def load_actions(self) -> tuple[StoredAction, ...]:
            return tuple(self.records.values())

        def save_action(self, record: StoredAction) -> None:
            self.records[record.definition.id] = record

        def delete_action(self, action_id: str) -> None:
            self.records.pop(action_id, None)

    store: ActionStore = MemoryActionStore()
    record = StoredAction(action_definition(), enabled=True)

    store.save_action(record)

    assert store.load_actions() == (record,)
    store.delete_action(record.definition.id)
    assert store.load_actions() == ()
