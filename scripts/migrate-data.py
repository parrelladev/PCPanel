from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.persistence.data_migration import migrate_database


def main() -> int:
    parser = argparse.ArgumentParser(description="Migrate an explicit PCPanel data directory")
    parser.add_argument("source", type=Path)
    parser.add_argument(
        "--destination",
        type=Path,
        default=Path(os.environ["LOCALAPPDATA"]) / "PCPanel",
    )
    args = parser.parse_args()
    print(migrate_database(args.source, args.destination))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
