from __future__ import annotations

from abc import ABC, abstractmethod

from app.actions.models import ActionDefinition, ActionExecution


class ActionExecutor(ABC):
    """Contract for attempting to start a resolved action."""

    @abstractmethod
    def execute(self, action: ActionDefinition) -> ActionExecution:
        """Attempt to start an action and return its initialization result."""
        raise NotImplementedError
