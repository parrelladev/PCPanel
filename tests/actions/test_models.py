from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from app.actions import ActionDefinition, ActionExecution


def action_definition(action_id: str, **kwargs: object) -> ActionDefinition:
    return ActionDefinition(
        id=action_id,
        label="Test action",
        executable=Path("program.exe"),
        **kwargs,
    )


@pytest.mark.parametrize(
    "action_id",
    [
        "steam",
        "my_app",
        "app-2",
        "a" * 64,
    ],
)
def test_accepts_valid_action_ids(action_id: str) -> None:
    assert action_definition(action_id).id == action_id


@pytest.mark.parametrize(
    "action_id",
    [
        "2app",
        "Steam",
        "../cmd",
        r"C:\Windows\cmd.exe",
        "my app",
        "",
        "a" * 65,
    ],
)
def test_rejects_invalid_action_ids(action_id: str) -> None:
    with pytest.raises(ValueError, match="action id must match"):
        action_definition(action_id)


def test_arguments_remain_a_tuple() -> None:
    arguments = ("--profile", "gaming")

    definition = action_definition("steam", arguments=arguments)

    assert definition.arguments == arguments
    assert definition.arguments is arguments
    assert isinstance(definition.arguments, tuple)

    with pytest.raises(TypeError):
        definition.arguments[0] = "changed"  # type: ignore[index]


def test_rejects_mutable_or_non_string_arguments() -> None:
    with pytest.raises(TypeError, match="tuple of strings"):
        action_definition("steam", arguments=["--silent"])  # type: ignore[arg-type]

    with pytest.raises(TypeError, match="tuple of strings"):
        action_definition("steam", arguments=(42,))  # type: ignore[arg-type]


def test_requires_structured_path_fields() -> None:
    with pytest.raises(TypeError, match="executable must be a Path"):
        ActionDefinition(
            id="steam",
            label="Steam",
            executable="steam.exe",  # type: ignore[arg-type]
        )

    with pytest.raises(TypeError, match="working_directory must be a Path or None"):
        action_definition(
            "steam",
            working_directory="C:/Games",  # type: ignore[arg-type]
        )


def test_action_definition_is_immutable() -> None:
    definition = action_definition("steam")

    with pytest.raises(FrozenInstanceError):
        definition.label = "Changed"  # type: ignore[misc]


def test_action_execution_is_immutable() -> None:
    execution = ActionExecution(action_id="steam", started=True, process_id=1234)

    with pytest.raises(FrozenInstanceError):
        execution.process_id = 5678  # type: ignore[misc]
