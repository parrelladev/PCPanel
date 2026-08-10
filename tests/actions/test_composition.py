from pathlib import Path

from app.actions import ActionDefinition, ActionService
from app.actions.composition import create_action_service

from .fakes import FakeActionExecutor


def test_composition_allows_empty_registry() -> None:
    executor = FakeActionExecutor()

    service = create_action_service(executor=executor)

    assert isinstance(service, ActionService)
    assert service.list_actions() == ()


def test_composition_registers_only_supplied_actions() -> None:
    executor = FakeActionExecutor()
    definition = ActionDefinition(
        id="notepad",
        label="Notepad",
        executable=Path(r"C:\Windows\System32\notepad.exe"),
        arguments=(),
        working_directory=None,
    )
    service = create_action_service(actions=(definition,), executor=executor)

    assert service.list_actions() == (definition,)


def test_composed_service_uses_injected_executor_without_starting_process() -> None:
    executor = FakeActionExecutor()
    definition = ActionDefinition(
        id="editor",
        label="Editor",
        executable=Path("editor.exe"),
    )
    service = create_action_service(actions=(definition,), executor=executor)

    result = service.execute("editor")

    assert result.started is True
    assert executor.executed_actions == [definition]
