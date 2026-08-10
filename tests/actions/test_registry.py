from pathlib import Path

import pytest

from app.actions import ActionDefinition, ActionNotFoundError, ActionRegistry


def action(action_id: str) -> ActionDefinition:
    return ActionDefinition(
        id=action_id,
        label=action_id.title(),
        executable=Path(f"{action_id}.exe"),
    )


def test_empty_registry() -> None:
    registry = ActionRegistry()

    assert registry.list() == ()


def test_registers_valid_action() -> None:
    definition = action("steam")
    registry = ActionRegistry()

    registry.register(definition)

    assert registry.list() == (definition,)


def test_register_rejects_unstructured_input() -> None:
    registry = ActionRegistry()

    with pytest.raises(TypeError, match="must be an ActionDefinition"):
        registry.register("steam")  # type: ignore[arg-type]

    assert registry.list() == ()


def test_registers_multiple_actions() -> None:
    definitions = (action("steam"), action("discord"), action("obs"))

    registry = ActionRegistry(definitions)

    assert registry.list() == definitions


def test_get_finds_registered_action() -> None:
    definition = action("steam")
    registry = ActionRegistry((definition,))

    assert registry.get("steam") is definition


def test_get_missing_action_raises_domain_error() -> None:
    registry = ActionRegistry()

    with pytest.raises(ActionNotFoundError) as exc_info:
        registry.get("missing")

    assert exc_info.value.action_id == "missing"
    assert str(exc_info.value) == "action 'missing' is not registered"


def test_contains_registered_action() -> None:
    registry = ActionRegistry((action("steam"),))

    assert registry.contains("steam") is True


def test_does_not_contain_missing_action() -> None:
    registry = ActionRegistry()

    assert registry.contains("steam") is False


def test_duplicate_id_is_rejected_without_overwriting() -> None:
    original = action("steam")
    duplicate = ActionDefinition(
        id="steam",
        label="Different Steam",
        executable=Path("different.exe"),
    )
    registry = ActionRegistry((original,))

    with pytest.raises(ValueError, match="already registered"):
        registry.register(duplicate)

    assert registry.get("steam") is original
    assert registry.list() == (original,)


def test_list_does_not_expose_mutable_internal_structure() -> None:
    definition = action("steam")
    registry = ActionRegistry((definition,))

    listed = registry.list()
    registry.register(action("discord"))

    assert isinstance(listed, tuple)
    assert listed == (definition,)
    assert registry.list() != listed


def test_list_preserves_registration_order() -> None:
    definitions = (action("spotify"), action("discord"), action("chrome"))
    registry = ActionRegistry()

    for definition in definitions:
        registry.register(definition)

    assert registry.list() == definitions
    assert registry.list() == definitions


def test_action_id_is_never_resolved_as_an_executable_path() -> None:
    executable = Path(r"C:\Windows\System32\cmd.exe")
    registry = ActionRegistry(
        (
            ActionDefinition(
                id="cmd",
                label="Command Prompt",
                executable=executable,
            ),
        )
    )

    with pytest.raises(ActionNotFoundError):
        registry.get(str(executable))

    assert registry.contains(str(executable)) is False
    assert registry.get("cmd").executable == executable
