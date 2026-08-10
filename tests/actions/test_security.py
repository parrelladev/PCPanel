import inspect
import re
from pathlib import Path

from app.actions import ActionExecution, ActionService


ACTIONS_PACKAGE = Path(__file__).parents[2] / "app" / "actions"
FORBIDDEN_EXECUTION_PATTERNS = {
    "shell execution": re.compile(r"shell\s*=\s*True", re.IGNORECASE),
    "os.system call": re.compile(r"os\.system\s*\(", re.IGNORECASE),
    "cmd shell command": re.compile(r"cmd\.exe\s+/c", re.IGNORECASE),
    "PowerShell command execution": re.compile(
        r"powershell(?:\.exe)?\s+(?:[^\r\n]*\s)?-Command\b",
        re.IGNORECASE,
    ),
}


def test_actions_package_contains_no_forbidden_shell_execution_patterns() -> None:
    source_by_file = {
        path.name: path.read_text(encoding="utf-8")
        for path in ACTIONS_PACKAGE.glob("*.py")
    }

    violations = [
        f"{filename}: {description}"
        for filename, source in source_by_file.items()
        for description, pattern in FORBIDDEN_EXECUTION_PATTERNS.items()
        if pattern.search(source)
    ]

    assert violations == []


def test_service_execute_public_contract_accepts_only_action_id() -> None:
    signature = inspect.signature(ActionService.execute)

    assert list(signature.parameters) == ["self", "action_id"]
    assert signature.parameters["action_id"].annotation in (str, "str")
    assert signature.return_annotation in (ActionExecution, "ActionExecution")
