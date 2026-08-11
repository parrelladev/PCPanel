from __future__ import annotations

from datetime import datetime, timezone

from app.agent.telemetry import AgentTelemetrySource
from app.ipc.protocol import IPCUnavailableError
from app.telemetry.models import TelemetrySnapshot


class RecoveringClient:
    def __init__(self, snapshot: TelemetrySnapshot) -> None:
        self.snapshot = snapshot
        self.snapshot_calls = 0
        self.status_calls = 0

    def get_snapshot(self) -> TelemetrySnapshot:
        self.snapshot_calls += 1
        if self.snapshot_calls == 1:
            raise IPCUnavailableError("service starting")
        return self.snapshot

    def get_status(self) -> str:
        self.status_calls += 1
        if self.status_calls == 1:
            raise IPCUnavailableError("service starting")
        return "telemetry_available"


def test_agent_source_survives_absence_and_recovers_on_next_read() -> None:
    snapshot = TelemetrySnapshot(
        sequence=4,
        captured_at=datetime(2026, 8, 10, tzinfo=timezone.utc),
        sensors=(),
    )
    source = AgentTelemetrySource(RecoveringClient(snapshot))  # type: ignore[arg-type]

    assert source.get_status() == "unavailable"
    assert source.get_snapshot() is None
    assert source.get_status() == "running"
    assert source.get_snapshot() == snapshot
