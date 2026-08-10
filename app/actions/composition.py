from __future__ import annotations

from collections.abc import Iterable

from app.actions.executor import ActionExecutor
from app.actions.models import ActionDefinition
from app.actions.registry import ActionRegistry
from app.actions.service import ActionService
from app.actions.windows import WindowsProcessExecutor

def create_action_service(
    *,
    actions: Iterable[ActionDefinition] = (),
    executor: ActionExecutor | None = None,
) -> ActionService:
    """Compose the Actions runtime from explicitly supplied definitions."""

    registry = ActionRegistry(actions)
    process_executor = executor or WindowsProcessExecutor()
    return ActionService(registry, process_executor)
