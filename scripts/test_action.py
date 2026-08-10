from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.actions import (
    ActionDefinition,
    ActionError,
    ActionRegistry,
    ActionService,
    WindowsProcessExecutor,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Manually start an explicitly registered local action.",
    )
    parser.add_argument(
        "action_id",
        help="ID of an action registered in this script (currently: notepad).",
    )
    return parser.parse_args()


def create_service() -> ActionService:
    windows_directory = Path(os.environ.get("SystemRoot", r"C:\Windows"))
    registry = ActionRegistry(
        (
            ActionDefinition(
                id="notepad",
                label="Notepad",
                executable=windows_directory / "System32" / "notepad.exe",
            ),
        )
    )
    return ActionService(registry, WindowsProcessExecutor())


def main() -> int:
    args = parse_args()
    service = create_service()

    try:
        execution = service.execute(args.action_id)
    except ActionError as exc:
        print(f"Action failed: {exc}", file=sys.stderr)
        return 1

    print(f"Action started: {execution.action_id}")
    print(f"PID: {execution.process_id if execution.process_id is not None else 'unknown'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
