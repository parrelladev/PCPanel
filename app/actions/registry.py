from __future__ import annotations

from collections.abc import Iterable

from app.actions.errors import ActionNotFoundError
from app.actions.models import ActionDefinition


class ActionRegistry:
    """Registry of explicitly allowed actions, listed in registration order."""

    def __init__(self, actions: Iterable[ActionDefinition] = ()) -> None:
        self._actions: dict[str, ActionDefinition] = {}
        for action in actions:
            self.register(action)

    def register(self, action: ActionDefinition) -> None:
        """Register an action without replacing an existing definition."""
        if not isinstance(action, ActionDefinition):
            raise TypeError("action must be an ActionDefinition")
        if action.id in self._actions:
            raise ValueError(f"action id is already registered: {action.id!r}")
        self._actions[action.id] = action

    def list(self) -> tuple[ActionDefinition, ...]:
        """Return an immutable snapshot in registration order."""
        return tuple(self._actions.values())

    def get(self, action_id: str) -> ActionDefinition:
        """Return the definition registered under an exact action ID."""
        try:
            return self._actions[action_id]
        except KeyError:
            raise ActionNotFoundError(action_id) from None

    def contains(self, action_id: str) -> bool:
        """Return whether the exact action ID is registered."""
        return action_id in self._actions
