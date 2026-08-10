from pathlib import Path

import pytest

from app.actions import (
    ActionDefinition,
    ActionExecution,
    ActionExecutionError,
    ActionNotFoundError,
    ActionRegistry,
    ActionService,
)
from tests.actions.fakes import FakeActionExecutor


def action(
    action_id: str,
    *,
    arguments: tuple[str, ...] = (),
) -> ActionDefinition:
    return ActionDefinition(
        id=action_id,
        label=action_id.title(),
        executable=Path(f"C:/Applications/{action_id}.exe"),
        arguments=arguments,
    )


def test_list_actions_returns_registry_snapshot() -> None:
    steam = action("steam")
    registry = ActionRegistry((steam,))
    service = ActionService(registry, FakeActionExecutor())

    listed = service.list_actions()
    registry.register(action("discord"))

    assert isinstance(listed, tuple)
    assert listed == (steam,)
    assert service.list_actions() == (steam, registry.get("discord"))


def test_execute_registered_action_returns_configured_result() -> None:
    steam = action("steam")
    expected = ActionExecution(action_id="steam", started=True, process_id=4567)
    executor = FakeActionExecutor(result=expected)
    service = ActionService(ActionRegistry((steam,)), executor)

    result = service.execute("steam")

    assert result is expected
    assert executor.execution_count == 1


def test_execute_missing_action_raises_domain_error_without_calling_executor() -> None:
    executor = FakeActionExecutor()
    service = ActionService(ActionRegistry(), executor)

    with pytest.raises(ActionNotFoundError):
        service.execute("missing")

    assert executor.execution_count == 0


def test_executor_receives_exact_registered_definition() -> None:
    registered = action("steam")
    executor = FakeActionExecutor()
    service = ActionService(ActionRegistry((registered,)), executor)

    service.execute("steam")

    assert executor.executed_actions == [registered]
    assert executor.executed_actions[0] is registered


def test_service_never_transforms_action_id_into_path() -> None:
    registered = action("cmd")
    executor = FakeActionExecutor()
    service = ActionService(ActionRegistry((registered,)), executor)

    with pytest.raises(ActionNotFoundError):
        service.execute(r"C:\Windows\System32\cmd.exe")

    assert executor.execution_count == 0


def test_action_arguments_are_preserved_for_executor() -> None:
    arguments = ("--profile", "Living room", "--fullscreen")
    registered = action("steam", arguments=arguments)
    executor = FakeActionExecutor()
    service = ActionService(ActionRegistry((registered,)), executor)

    service.execute("steam")

    received = executor.executed_actions[0]
    assert received.arguments is arguments
    assert received.arguments == arguments


def test_executor_domain_error_is_propagated_unchanged() -> None:
    execution_error = ActionExecutionError("steam")
    executor = FakeActionExecutor(error=execution_error)
    service = ActionService(ActionRegistry((action("steam"),)), executor)

    with pytest.raises(ActionExecutionError) as exc_info:
        service.execute("steam")

    assert exc_info.value is execution_error
    assert executor.execution_count == 1


def test_fake_executor_only_records_execution_in_memory() -> None:
    registered = action("steam")
    executor = FakeActionExecutor()

    result = executor.execute(registered)

    assert executor.executed_actions == [registered]
    assert executor.execution_count == 1
    assert result == ActionExecution(
        action_id="steam",
        started=True,
        process_id=None,
    )
