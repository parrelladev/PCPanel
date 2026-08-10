from __future__ import annotations

from app.actions.executor import ActionExecutor
from app.actions.models import ActionDefinition, ActionExecution
from app.actions.registry import ActionRegistry


class ActionService:
    """Orchestrate action lookup and execution through domain contracts."""

    def __init__(
        self,
        registry: ActionRegistry,
        executor: ActionExecutor,
    ) -> None:
        self._registry = registry
        self._executor = executor

    def list_actions(self) -> tuple[ActionDefinition, ...]:
        """Return the actions explicitly allowed by the registry."""
        return self._registry.list()

    def execute(self, action_id: str) -> ActionExecution:
        """Execute the preexisting definition registered for an action ID."""
        action = self._registry.get(action_id)
        return self._executor.execute(action)
