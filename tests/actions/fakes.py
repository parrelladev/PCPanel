from __future__ import annotations

from app.actions import (
    ActionDefinition,
    ActionExecution,
    ActionExecutionError,
    ActionExecutor,
)


class FakeActionExecutor(ActionExecutor):
    """In-memory executor for service tests; it never starts a process."""

    def __init__(
        self,
        *,
        result: ActionExecution | None = None,
        error: ActionExecutionError | None = None,
    ) -> None:
        self.executed_actions: list[ActionDefinition] = []
        self.result = result
        self.error = error

    @property
    def execution_count(self) -> int:
        return len(self.executed_actions)

    def execute(self, action: ActionDefinition) -> ActionExecution:
        self.executed_actions.append(action)
        if self.error is not None:
            raise self.error
        if self.result is not None:
            return self.result
        return ActionExecution(
            action_id=action.id,
            started=True,
            process_id=None,
        )
