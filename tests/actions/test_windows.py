from pathlib import Path
from types import SimpleNamespace

import pytest

from app.actions import (
    ActionDefinition,
    ActionExecutionError,
    ActionUnavailableError,
    WindowsProcessExecutor,
)


EXECUTABLE = Path(r"C:\Program Files\Test App\program.exe")
WORKING_DIRECTORY = Path(r"C:\Program Files\Test App")


def definition(
    *,
    arguments: tuple[str, ...] = (),
    working_directory: Path | None = None,
) -> ActionDefinition:
    return ActionDefinition(
        id="test_app",
        label="Test application",
        executable=EXECUTABLE,
        arguments=arguments,
        working_directory=working_directory,
    )


def make_paths_available(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(Path, "is_file", lambda path: True)
    monkeypatch.setattr(Path, "is_dir", lambda path: True)


def test_builds_structured_argv_and_returns_process_id(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    make_paths_available(monkeypatch)
    popen_calls: list[tuple[list[str], dict[str, object]]] = []

    def fake_popen(argv: list[str], **kwargs: object) -> SimpleNamespace:
        popen_calls.append((argv, kwargs))
        return SimpleNamespace(pid=4321)

    monkeypatch.setattr("app.actions.windows.subprocess.Popen", fake_popen)
    action = definition(
        arguments=("--profile", "Living room", "--fullscreen"),
    )

    result = WindowsProcessExecutor().execute(action)

    assert popen_calls == [
        (
            [str(EXECUTABLE), "--profile", "Living room", "--fullscreen"],
            {"shell": False},
        )
    ]
    assert popen_calls[0][0][0] == str(EXECUTABLE)
    assert popen_calls[0][0][2] == "Living room"
    assert "cwd" not in popen_calls[0][1]
    assert result.action_id == action.id
    assert result.started is True
    assert result.process_id == 4321


def test_passes_configured_working_directory_as_cwd(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    make_paths_available(monkeypatch)
    received_kwargs: dict[str, object] = {}

    def fake_popen(argv: list[str], **kwargs: object) -> SimpleNamespace:
        received_kwargs.update(kwargs)
        return SimpleNamespace(pid=10)

    monkeypatch.setattr("app.actions.windows.subprocess.Popen", fake_popen)

    WindowsProcessExecutor().execute(
        definition(working_directory=WORKING_DIRECTORY)
    )

    assert received_kwargs == {"shell": False, "cwd": WORKING_DIRECTORY}


def test_unavailable_executable_raises_domain_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(Path, "is_file", lambda path: False)
    popen_called = False

    def fake_popen(argv: list[str], **kwargs: object) -> SimpleNamespace:
        nonlocal popen_called
        popen_called = True
        return SimpleNamespace(pid=10)

    monkeypatch.setattr("app.actions.windows.subprocess.Popen", fake_popen)

    with pytest.raises(ActionUnavailableError):
        WindowsProcessExecutor().execute(definition())

    assert popen_called is False


def test_invalid_working_directory_raises_domain_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(Path, "is_file", lambda path: True)
    monkeypatch.setattr(Path, "is_dir", lambda path: False)
    popen_called = False

    def fake_popen(argv: list[str], **kwargs: object) -> SimpleNamespace:
        nonlocal popen_called
        popen_called = True
        return SimpleNamespace(pid=10)

    monkeypatch.setattr("app.actions.windows.subprocess.Popen", fake_popen)

    with pytest.raises(ActionUnavailableError):
        WindowsProcessExecutor().execute(
            definition(working_directory=WORKING_DIRECTORY)
        )

    assert popen_called is False


def test_popen_os_error_becomes_execution_error_with_chained_cause(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    make_paths_available(monkeypatch)
    infrastructure_error = OSError("operating system failure")

    def fake_popen(argv: list[str], **kwargs: object) -> SimpleNamespace:
        raise infrastructure_error

    monkeypatch.setattr("app.actions.windows.subprocess.Popen", fake_popen)

    with pytest.raises(ActionExecutionError) as exc_info:
        WindowsProcessExecutor().execute(definition())

    assert exc_info.value.__cause__ is infrastructure_error


def test_popen_file_not_found_becomes_unavailable_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    make_paths_available(monkeypatch)
    infrastructure_error = FileNotFoundError("disappeared before launch")

    def fake_popen(argv: list[str], **kwargs: object) -> SimpleNamespace:
        raise infrastructure_error

    monkeypatch.setattr("app.actions.windows.subprocess.Popen", fake_popen)

    with pytest.raises(ActionUnavailableError) as exc_info:
        WindowsProcessExecutor().execute(definition())

    assert exc_info.value.__cause__ is infrastructure_error
