from pathlib import Path

import pytest

from app.actions import ActionDefinition, ActionExecution, ActionExecutor


class FakeActionExecutor(ActionExecutor):
    def execute(self, action: ActionDefinition) -> ActionExecution:
        return ActionExecution(
            action_id=action.id,
            started=True,
            process_id=1234,
        )


def test_action_executor_requires_execute_implementation() -> None:
    with pytest.raises(TypeError):
        ActionExecutor()


def test_concrete_executor_returns_domain_execution_result() -> None:
    action = ActionDefinition(
        id="steam",
        label="Steam",
        executable=Path("steam.exe"),
    )

    result = FakeActionExecutor().execute(action)

    assert result == ActionExecution(
        action_id="steam",
        started=True,
        process_id=1234,
    )
