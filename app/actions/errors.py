"""Domain errors raised while resolving and executing actions."""


class ActionError(Exception):
    """Base error for the Actions domain."""

    def __init__(self, action_id: str, message: str) -> None:
        self.action_id = action_id
        super().__init__(message)


class ActionNotFoundError(ActionError):
    """Raised when an action is not registered."""

    def __init__(self, action_id: str) -> None:
        super().__init__(action_id, f"action {action_id!r} is not registered")


class ActionUnavailableError(ActionError):
    """Raised when a registered action is unavailable on the system."""

    def __init__(self, action_id: str, *, reason: str | None = None) -> None:
        message = f"action {action_id!r} is unavailable"
        if reason is not None:
            message = f"{message}: {reason}"
        super().__init__(action_id, message)


class ActionExecutionError(ActionError):
    """Raised when an action cannot be started or executed."""

    def __init__(self, action_id: str, *, reason: str | None = None) -> None:
        message = f"action {action_id!r} could not be started"
        if reason is not None:
            message = f"{message}: {reason}"
        super().__init__(action_id, message)
