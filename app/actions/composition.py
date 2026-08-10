from __future__ import annotations

from pathlib import Path

from app.actions.executor import ActionExecutor
from app.actions.models import ActionDefinition
from app.actions.registry import ActionRegistry
from app.actions.service import ActionService
from app.actions.windows import WindowsProcessExecutor


NOTEPAD_ACTION = ActionDefinition(
    id="notepad",
    label="Notepad",
    executable=Path(r"C:\Windows\System32\notepad.exe"),
)


def create_action_service(
    *,
    executor: ActionExecutor | None = None,
) -> ActionService:
    """Compose the shared Actions runtime from server-owned definitions."""

    registry = ActionRegistry((NOTEPAD_ACTION,))
    process_executor = executor or WindowsProcessExecutor()
    return ActionService(registry, process_executor)
