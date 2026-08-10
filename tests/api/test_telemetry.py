from __future__ import annotations

from datetime import datetime, timezone

from fastapi.testclient import TestClient

from app.api.app import create_app
from app.telemetry.manager import TelemetryStatus
from app.telemetry.models import SensorReading, TelemetrySnapshot


class StubTelemetryManager:
    def __init__(self, snapshot: TelemetrySnapshot | None) -> None:
        self.status = TelemetryStatus.RUNNING
        self._snapshot = snapshot
        self.get_snapshot_calls = 0
        self.wait_for_snapshot_calls = 0

    def start(self) -> None:
        pass

    def stop(self) -> None:
        pass

    def get_snapshot(self) -> TelemetrySnapshot | None:
        self.get_snapshot_calls += 1
        return self._snapshot

    def wait_for_snapshot(self) -> None:
        self.wait_for_snapshot_calls += 1


def test_telemetry_returns_latest_snapshot_with_all_sensor_fields() -> None:
    snapshot = TelemetrySnapshot(
        sequence=42,
        captured_at=datetime(2026, 8, 10, 14, 20, 31, tzinfo=timezone.utc),
        sensors=(
            SensorReading(
                hardware_identifier="/intelcpu/0",
                hardware_name="11th Gen Intel Core i7-1165G7",
                hardware_type="Cpu",
                sensor_identifier="/intelcpu/0/temperature/0",
                sensor_name="Core Max",
                sensor_type="Temperature",
                value=None,
                min_value=None,
                max_value=None,
            ),
        ),
    )
    manager = StubTelemetryManager(snapshot)
    application = create_app(manager)  # type: ignore[arg-type]

    with TestClient(application) as client:
        response = client.get("/api/v1/telemetry")

    assert response.status_code == 200
    assert response.json() == {
        "sequence": 42,
        "captured_at": "2026-08-10T14:20:31Z",
        "sensors": [
            {
                "hardware_identifier": "/intelcpu/0",
                "hardware_name": "11th Gen Intel Core i7-1165G7",
                "hardware_type": "Cpu",
                "sensor_identifier": "/intelcpu/0/temperature/0",
                "sensor_name": "Core Max",
                "sensor_type": "Temperature",
                "value": None,
                "min_value": None,
                "max_value": None,
            }
        ],
    }
    assert manager.get_snapshot_calls == 1
    assert manager.wait_for_snapshot_calls == 0


def test_telemetry_returns_503_when_snapshot_is_not_available() -> None:
    manager = StubTelemetryManager(None)
    application = create_app(manager)  # type: ignore[arg-type]

    with TestClient(application) as client:
        response = client.get("/api/v1/telemetry")

    assert response.status_code == 503
    assert response.json() == {
        "detail": "Telemetry snapshot is not available yet",
    }
    assert manager.get_snapshot_calls == 1
    assert manager.wait_for_snapshot_calls == 0
