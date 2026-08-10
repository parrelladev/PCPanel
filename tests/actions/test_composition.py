from pathlib import Path

from app.actions import ActionDefinition, ActionService
from app.actions.composition import NOTEPAD_ACTION, create_action_service

from .fakes import FakeActionExecutor


def test_composition_registers_only_server_defined_notepad() -> None:
    executor = FakeActionExecutor()

    service = create_action_service(executor=executor)

    assert isinstance(service, ActionService)
    assert service.list_actions() == (NOTEPAD_ACTION,)
    assert NOTEPAD_ACTION == ActionDefinition(
        id="notepad",
        label="Notepad",
        executable=Path(r"C:\Windows\System32\notepad.exe"),
        arguments=(),
        working_directory=None,
    )


def test_composed_service_uses_injected_executor_without_starting_process() -> None:
    executor = FakeActionExecutor()
    service = create_action_service(executor=executor)

    result = service.execute("notepad")

    assert result.started is True
    assert executor.executed_actions == [NOTEPAD_ACTION]
