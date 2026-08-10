from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path


_ACTION_ID_PATTERN = re.compile(r"^[a-z][a-z0-9_-]{0,63}$")


@dataclass(slots=True, frozen=True)
class ActionDefinition:
    """Immutable definition of an action that may be executed."""

    id: str
    label: str
    executable: Path
    arguments: tuple[str, ...] = ()
    working_directory: Path | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.id, str) or _ACTION_ID_PATTERN.fullmatch(self.id) is None:
            raise ValueError(
                "action id must match ^[a-z][a-z0-9_-]{0,63}$"
            )
        if not isinstance(self.executable, Path):
            raise TypeError("action executable must be a Path")
        if not isinstance(self.arguments, tuple) or not all(
            isinstance(argument, str) for argument in self.arguments
        ):
            raise TypeError("action arguments must be a tuple of strings")
        if self.working_directory is not None and not isinstance(
            self.working_directory,
            Path,
        ):
            raise TypeError("action working_directory must be a Path or None")


@dataclass(slots=True, frozen=True)
class ActionExecution:
    """Result of an attempt to start an action."""

    action_id: str
    started: bool
    process_id: int | None
