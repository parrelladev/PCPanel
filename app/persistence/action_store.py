from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from app.actions.models import ActionDefinition


@dataclass(slots=True, frozen=True)
class StoredAction:
    """Persistence record combining a validated action with its enabled state."""

    definition: ActionDefinition
    enabled: bool = True

    def __post_init__(self) -> None:
        if not isinstance(self.definition, ActionDefinition):
            raise TypeError("definition must be an ActionDefinition")
        if not isinstance(self.enabled, bool):
            raise TypeError("enabled must be a bool")


class ActionStore(Protocol):
    """Storage boundary for durable action configuration."""

    def load_actions(self) -> tuple[StoredAction, ...]: ...

    def save_action(self, record: StoredAction) -> None: ...

    def delete_action(self, action_id: str) -> None: ...
