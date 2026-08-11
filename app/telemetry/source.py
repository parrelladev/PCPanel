from __future__ import annotations

from typing import Protocol

from .models import TelemetrySnapshot


class TelemetrySnapshotSource(Protocol):
    """Read-only source of the latest raw telemetry snapshot."""

    def get_snapshot(self) -> TelemetrySnapshot | None:
        """Return the latest snapshot without triggering collection."""

        ...
