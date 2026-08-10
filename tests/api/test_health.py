from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.api.app import create_app
from app.telemetry.manager import TelemetryStatus


class StubTelemetryManager:
    def __init__(self, status: TelemetryStatus) -> None:
        self.status = status
        self.start_calls = 0
        self.stop_calls = 0
        self.get_snapshot_calls = 0
        self.wait_for_snapshot_calls = 0

    def start(self) -> None:
        self.start_calls += 1

    def stop(self) -> None:
        self.stop_calls += 1

    def get_snapshot(self) -> None:
        self.get_snapshot_calls += 1

    def wait_for_snapshot(self) -> None:
        self.wait_for_snapshot_calls += 1


@pytest.mark.parametrize(
    ("telemetry_status", "expected_value"),
    [
        (TelemetryStatus.RUNNING, "running"),
        (TelemetryStatus.FAILED, "failed"),
    ],
)
def test_health_reports_api_and_telemetry_status(
    telemetry_status: TelemetryStatus,
    expected_value: str,
) -> None:
    manager = StubTelemetryManager(telemetry_status)
    application = create_app(manager)  # type: ignore[arg-type]

    with TestClient(application) as client:
        response = client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "telemetry_status": expected_value,
    }


def test_health_does_not_collect_or_wait_for_telemetry() -> None:
    manager = StubTelemetryManager(TelemetryStatus.RUNNING)
    application = create_app(manager)  # type: ignore[arg-type]

    with TestClient(application) as client:
        client.get("/api/v1/health")

    assert manager.get_snapshot_calls == 0
    assert manager.wait_for_snapshot_calls == 0
    assert manager.start_calls == 1
    assert manager.stop_calls == 1
