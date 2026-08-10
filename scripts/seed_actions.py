from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.actions import ActionDefinition
from app.persistence import ActionStore, Database, SQLiteActionStore, StoredAction


def seed_development_actions(
    store: ActionStore,
    *,
    windows_directory: Path | None = None,
) -> bool:
    """Add the development Notepad action only when its ID is not configured."""
    if any(record.definition.id == "notepad" for record in store.load_actions()):
        return False

    windows_root = windows_directory or Path(
        os.environ.get("SystemRoot", r"C:\Windows")
    )
    definition = ActionDefinition(
        id="notepad",
        label="Notepad",
        executable=windows_root / "System32" / "notepad.exe",
        arguments=(),
        working_directory=None,
    )
    store.save_action(StoredAction(definition=definition, enabled=True))
    return True


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Explicitly seed local development Actions.",
    )
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=Path("data"),
        help="PCPanel data directory (default: ./data)",
    )
    args = parser.parse_args()

    database = Database(args.data_dir)
    database.initialize()
    created = seed_development_actions(SQLiteActionStore(database))
    print("Seeded Notepad." if created else "Notepad is already configured; unchanged.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
