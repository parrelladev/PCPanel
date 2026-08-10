from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import Mock

from fastapi.testclient import TestClient

from app.api.app import create_app
from app.telemetry.manager import TelemetryManager, TelemetryStatus
from app.telemetry.models import SensorReading, TelemetrySnapshot


def _sensor(identifier: str, hardware_identifier: str) -> SensorReading:
    return SensorReading(
        hardware_identifier=hardware_identifier,
        hardware_name="Intel Iris Xe Graphics",
        hardware_type="GpuIntel",
        sensor_identifier=identifier,
        sensor_name="D3D Copy",
        sensor_type="Load",
        value=12.5,
        min_value=0.0,
        max_value=50.0,
    )


def _manager(snapshot: TelemetrySnapshot | None) -> Mock:
    manager = Mock(spec=TelemetryManager)
    manager.status = TelemetryStatus.RUNNING
    manager.get_snapshot.return_value = snapshot
    return manager


def test_sensors_returns_metadata_catalog_without_deduplicating_names() -> None:
    snapshot = TelemetrySnapshot(
        sequence=7,
        captured_at=datetime(2026, 8, 10, tzinfo=timezone.utc),
        sensors=(
            _sensor("/gpu-intel/0/load/1", "/gpu-intel/0"),
            _sensor("/gpu-intel/0/load/2", "/gpu-intel/0"),
        ),
    )
    manager = _manager(snapshot)
    application = create_app(manager)

    with TestClient(application) as client:
        response = client.get("/api/v1/sensors")

    assert response.status_code == 200
    assert response.json() == {
        "sensors": [
            {
                "hardware_identifier": "/gpu-intel/0",
                "hardware_name": "Intel Iris Xe Graphics",
                "hardware_type": "GpuIntel",
                "sensor_identifier": "/gpu-intel/0/load/1",
                "sensor_name": "D3D Copy",
                "sensor_type": "Load",
            },
            {
                "hardware_identifier": "/gpu-intel/0",
                "hardware_name": "Intel Iris Xe Graphics",
                "hardware_type": "GpuIntel",
                "sensor_identifier": "/gpu-intel/0/load/2",
                "sensor_name": "D3D Copy",
                "sensor_type": "Load",
            },
        ]
    }
    manager.get_snapshot.assert_called_once_with()
    manager.wait_for_snapshot.assert_not_called()


def test_sensors_returns_503_when_snapshot_is_not_available() -> None:
    manager = _manager(None)
    application = create_app(manager)

    with TestClient(application) as client:
        response = client.get("/api/v1/sensors")

    assert response.status_code == 503
    assert response.json() == {
        "detail": "Telemetry snapshot is not available yet",
    }
    manager.get_snapshot.assert_called_once_with()
    manager.wait_for_snapshot.assert_not_called()
