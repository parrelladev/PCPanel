from app.actions import (
    ActionError,
    ActionExecutionError,
    ActionNotFoundError,
    ActionUnavailableError,
)


def test_not_found_error_identifies_unregistered_action() -> None:
    error = ActionNotFoundError("missing")

    assert isinstance(error, ActionError)
    assert error.action_id == "missing"
    assert str(error) == "action 'missing' is not registered"


def test_unavailable_error_identifies_action_and_safe_reason() -> None:
    error = ActionUnavailableError(
        "steam",
        reason="executable is unavailable",
    )

    assert isinstance(error, ActionError)
    assert error.action_id == "steam"
    assert str(error) == "action 'steam' is unavailable: executable is unavailable"


def test_execution_error_identifies_action_and_safe_reason() -> None:
    error = ActionExecutionError(
        "steam",
        reason="process creation failed",
    )

    assert isinstance(error, ActionError)
    assert error.action_id == "steam"
    assert str(error) == "action 'steam' could not be started: process creation failed"
