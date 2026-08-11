from __future__ import annotations

import os
import subprocess
from pathlib import Path

from ..ipc.win32 import current_user_sid


def harden_user_data_directory(path: Path) -> None:
    """Restrict installed Agent data to its Windows user and SYSTEM."""

    if os.name != "nt":
        return
    user_sid = current_user_sid()
    subprocess.run(
        [
            "icacls.exe",
            str(path),
            "/inheritance:r",
            "/grant:r",
            f"*{user_sid}:(OI)(CI)F",
            "*S-1-5-18:(OI)(CI)F",
        ],
        check=True,
        capture_output=True,
        creationflags=subprocess.CREATE_NO_WINDOW,
        shell=False,
    )
