from __future__ import annotations

import subprocess

from app.actions.errors import ActionExecutionError, ActionUnavailableError
from app.actions.executor import ActionExecutor
from app.actions.models import ActionDefinition, ActionExecution


class WindowsProcessExecutor(ActionExecutor):
    """Start explicitly defined actions without invoking a command shell."""

    def execute(self, action: ActionDefinition) -> ActionExecution:
        self._validate_availability(action)

        argv = [str(action.executable), *action.arguments]
        popen_kwargs: dict[str, object] = {"shell": False}
        if action.working_directory is not None:
            popen_kwargs["cwd"] = action.working_directory

        try:
            process = subprocess.Popen(argv, **popen_kwargs)
        except FileNotFoundError as exc:
            raise ActionUnavailableError(action.id) from exc
        except OSError as exc:
            raise ActionExecutionError(action.id) from exc

        return ActionExecution(
            action_id=action.id,
            started=True,
            process_id=getattr(process, "pid", None),
        )

    @staticmethod
    def _validate_availability(action: ActionDefinition) -> None:
        try:
            executable_is_file = action.executable.is_file()
        except OSError as exc:
            raise ActionUnavailableError(
                action.id,
                reason="executable is unavailable",
            ) from exc

        if not executable_is_file:
            raise ActionUnavailableError(
                action.id,
                reason="executable is unavailable",
            )

        if action.working_directory is None:
            return

        try:
            working_directory_is_directory = action.working_directory.is_dir()
        except OSError as exc:
            raise ActionUnavailableError(
                action.id,
                reason="working directory is unavailable",
            ) from exc

        if not working_directory_is_directory:
            raise ActionUnavailableError(
                action.id,
                reason="working directory is unavailable",
            )
