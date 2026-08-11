from __future__ import annotations

from datetime import datetime, timezone

from fastapi.testclient import TestClient

from app.api.app import create_app
from app.telemetry.manager import TelemetryStatus
from app.telemetry.models import SensorReading, TelemetrySnapshot


CAPTURED_AT = datetime(2026, 8, 10, 14, 55, tzinfo=timezone.utc)


class StubTelemetryManager:
    def __init__(self, snapshot: TelemetrySnapshot | None) -> None:
        self.status = TelemetryStatus.RUNNING
        self.snapshot = snapshot
        self.start_calls = 0
        self.stop_calls = 0
        self.get_snapshot_calls = 0
        self.wait_for_snapshot_calls = 0

    def start(self) -> None:
        self.start_calls += 1

    def stop(self) -> None:
        self.stop_calls += 1

    def get_snapshot(self) -> TelemetrySnapshot | None:
        self.get_snapshot_calls += 1
        return self.snapshot

    def wait_for_snapshot(self) -> None:
        self.wait_for_snapshot_calls += 1


def sensor(
    hardware_type: str,
    hardware_identifier: str,
    sensor_type: str,
    sensor_identifier: str,
    sensor_name: str,
    value: float | None,
) -> SensorReading:
    return SensorReading(
        hardware_identifier=hardware_identifier,
        hardware_name=hardware_identifier,
        hardware_type=hardware_type,
        sensor_identifier=sensor_identifier,
        sensor_name=sensor_name,
        sensor_type=sensor_type,
        value=value,
        min_value=None,
        max_value=None,
    )


def test_metrics_returns_canonical_map_from_latest_raw_snapshot() -> None:
    raw_snapshot = TelemetrySnapshot(
        sequence=152,
        captured_at=CAPTURED_AT,
        sensors=(
            sensor(
                "Cpu", "/intelcpu/0", "Temperature",
                "/intelcpu/0/temperature/0", "CPU Package", 54.0,
            ),
            sensor(
                "Cpu", "/intelcpu/0", "Load",
                "/intelcpu/0/load/0", "CPU Total", 17.3,
            ),
            sensor(
                "GpuNvidia", "/nvidiagpu/0", "Temperature",
                "/nvidiagpu/0/temperature/0", "GPU Core", 42.0,
            ),
            sensor(
                "GpuNvidia", "/nvidiagpu/0", "Load",
                "/nvidiagpu/0/load/0", "GPU Core", None,
            ),
            sensor(
                "GpuNvidia", "/nvidiagpu/0", "SmallData",
                "/nvidiagpu/0/smalldata/1", "GPU Memory Used", 2048.0,
            ),
            sensor(
                "Memory", "/memory", "Load",
                "/memory/load/0", "Memory", 63.5,
            ),
            sensor(
                "Memory", "/memory", "Data",
                "/memory/data/0", "Memory Used", 20.0,
            ),
        ),
    )
    manager = StubTelemetryManager(raw_snapshot)
    application = create_app(manager)  # type: ignore[arg-type]

    with TestClient(application) as client:
        response = client.get("/api/v1/metrics")

    assert response.status_code == 200
    payload = response.json()
    assert payload["sequence"] == 152
    assert payload["captured_at"] == "2026-08-10T14:55:00Z"
    assert payload["hardware_models"] == {
        "cpu": "/intelcpu/0",
        "gpu": "/nvidiagpu/0",
    }
    assert payload["metrics"]["cpu.temperature"] == {
        "value": 54.0,
        "unit": "celsius",
        "source_sensor_identifier": "/intelcpu/0/temperature/0",
    }
    assert payload["metrics"]["gpu.memory.used"]["value"] == 2048.0
    assert payload["metrics"]["memory.used"]["value"] == 20480.0
    assert payload["metrics"]["cpu.clock"]["value"] is None
    assert payload["metrics"]["gpu.temperature.hotspot"]["value"] is None
    assert payload["metrics"]["memory.total"]["value"] is None
    assert manager.get_snapshot_calls == 1
    assert manager.wait_for_snapshot_calls == 0
    assert manager.start_calls == 1
    assert manager.stop_calls == 1


def test_metrics_returns_503_without_raw_snapshot() -> None:
    manager = StubTelemetryManager(None)
    application = create_app(manager)  # type: ignore[arg-type]

    with TestClient(application) as client:
        response = client.get("/api/v1/metrics")

    assert response.status_code == 503
    assert response.json() == {
        "detail": "Telemetry snapshot is not available yet",
    }
    assert manager.get_snapshot_calls == 1
    assert manager.wait_for_snapshot_calls == 0


def test_raw_telemetry_and_sensor_catalog_endpoints_remain_available() -> None:
    raw_snapshot = TelemetrySnapshot(
        sequence=1,
        captured_at=CAPTURED_AT,
        sensors=(
            sensor(
                "Cpu", "/cpu/0", "Load",
                "/cpu/0/load/0", "CPU Total", 25.0,
            ),
        ),
    )
    manager = StubTelemetryManager(raw_snapshot)
    application = create_app(manager)  # type: ignore[arg-type]

    with TestClient(application) as client:
        telemetry_response = client.get("/api/v1/telemetry")
        sensors_response = client.get("/api/v1/sensors")

    assert telemetry_response.status_code == 200
    assert telemetry_response.json()["sensors"][0]["hardware_type"] == "Cpu"
    assert sensors_response.status_code == 200
    assert sensors_response.json()["sensors"][0]["sensor_name"] == "CPU Total"
