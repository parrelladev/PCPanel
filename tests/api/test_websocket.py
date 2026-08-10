from __future__ import annotations

import time
from datetime import datetime, timezone
from threading import Lock

from fastapi.testclient import TestClient

from app.api.app import create_app
from app.telemetry.manager import TelemetryStatus
from app.telemetry.models import SensorReading, TelemetrySnapshot


SENSOR = SensorReading(
    hardware_identifier="/intelcpu/0",
    hardware_name="Intel CPU",
    hardware_type="Cpu",
    sensor_identifier="/intelcpu/0/load/0",
    sensor_name="CPU Total",
    sensor_type="Load",
    value=25.5,
    min_value=None,
    max_value=80.0,
)


def _snapshot(sequence: int) -> TelemetrySnapshot:
    return TelemetrySnapshot(
        sequence=sequence,
        captured_at=datetime(2026, 8, 10, 14, 20, 31, tzinfo=timezone.utc),
        sensors=(SENSOR,),
    )


class StubTelemetryManager:
    def __init__(self, snapshot: TelemetrySnapshot | None) -> None:
        self.status = TelemetryStatus.RUNNING
        self._snapshot = snapshot
        self._lock = Lock()
        self.get_snapshot_calls = 0
        self.wait_for_snapshot_calls = 0

    def start(self) -> None:
        pass

    def stop(self) -> None:
        pass

    def get_snapshot(self) -> TelemetrySnapshot | None:
        with self._lock:
            self.get_snapshot_calls += 1
            return self._snapshot

    def set_snapshot(self, snapshot: TelemetrySnapshot) -> None:
        with self._lock:
            self._snapshot = snapshot

    def wait_for_snapshot(self) -> None:
        self.wait_for_snapshot_calls += 1


def test_websocket_accepts_connection_and_sends_first_snapshot() -> None:
    manager = StubTelemetryManager(_snapshot(1))
    application = create_app(manager)  # type: ignore[arg-type]

    with TestClient(application) as client:
        with client.websocket_connect("/ws/v1/telemetry") as websocket:
            message = websocket.receive_json()

    assert message == {
        "sequence": 1,
        "captured_at": "2026-08-10T14:20:31Z",
        "sensors": [
            {
                "hardware_identifier": "/intelcpu/0",
                "hardware_name": "Intel CPU",
                "hardware_type": "Cpu",
                "sensor_identifier": "/intelcpu/0/load/0",
                "sensor_name": "CPU Total",
                "sensor_type": "Load",
                "value": 25.5,
                "min_value": None,
                "max_value": 80.0,
            }
        ],
    }
    assert manager.wait_for_snapshot_calls == 0


def test_websocket_sends_only_when_sequence_changes() -> None:
    manager = StubTelemetryManager(_snapshot(10))
    application = create_app(manager)  # type: ignore[arg-type]

    with TestClient(application) as client:
        with client.websocket_connect("/ws/v1/telemetry") as websocket:
            assert websocket.receive_json()["sequence"] == 10
            manager.set_snapshot(_snapshot(10))
            time.sleep(0.2)
            manager.set_snapshot(_snapshot(11))
            assert websocket.receive_json()["sequence"] == 11

    assert manager.get_snapshot_calls >= 2
    assert manager.wait_for_snapshot_calls == 0


def test_websocket_disconnect_does_not_stop_manager_or_break_new_clients() -> None:
    manager = StubTelemetryManager(_snapshot(20))
    application = create_app(manager)  # type: ignore[arg-type]

    with TestClient(application) as client:
        with client.websocket_connect("/ws/v1/telemetry") as first:
            assert first.receive_json()["sequence"] == 20

        manager.set_snapshot(_snapshot(21))
        with client.websocket_connect("/ws/v1/telemetry") as second:
            assert second.receive_json()["sequence"] == 21

    assert manager.status is TelemetryStatus.RUNNING
    assert manager.wait_for_snapshot_calls == 0


def test_websocket_supports_multiple_clients_independently() -> None:
    manager = StubTelemetryManager(_snapshot(30))
    application = create_app(manager)  # type: ignore[arg-type]

    with TestClient(application) as client:
        with (
            client.websocket_connect("/ws/v1/telemetry") as first,
            client.websocket_connect("/ws/v1/telemetry") as second,
        ):
            assert first.receive_json()["sequence"] == 30
            assert second.receive_json()["sequence"] == 30

            manager.set_snapshot(_snapshot(31))
            assert first.receive_json()["sequence"] == 31
            assert second.receive_json()["sequence"] == 31

    assert manager.wait_for_snapshot_calls == 0
