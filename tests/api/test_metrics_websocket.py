from __future__ import annotations

import time
from datetime import datetime, timezone
from threading import Lock

from fastapi.testclient import TestClient

from app.api.app import create_app
from app.telemetry.manager import TelemetryStatus
from app.telemetry.models import SensorReading, TelemetrySnapshot


CAPTURED_AT = datetime(2026, 8, 10, 15, 10, tzinfo=timezone.utc)


def sensor(
    sensor_type: str,
    sensor_identifier: str,
    sensor_name: str,
    value: float | None,
) -> SensorReading:
    return SensorReading(
        hardware_identifier="/cpu/0",
        hardware_name="CPU",
        hardware_type="Cpu",
        sensor_identifier=sensor_identifier,
        sensor_name=sensor_name,
        sensor_type=sensor_type,
        value=value,
        min_value=None,
        max_value=None,
    )


def snapshot(sequence: int, load: float = 25.0) -> TelemetrySnapshot:
    return TelemetrySnapshot(
        sequence=sequence,
        captured_at=CAPTURED_AT,
        sensors=(
            sensor(
                "Temperature",
                "/cpu/0/temperature/package",
                "CPU Package",
                54.0,
            ),
            sensor("Load", "/cpu/0/load/total", "CPU Total", load),
        ),
    )


class StubTelemetryManager:
    def __init__(self, initial_snapshot: TelemetrySnapshot) -> None:
        self.status = TelemetryStatus.RUNNING
        self._snapshot = initial_snapshot
        self._lock = Lock()
        self.get_snapshot_calls = 0
        self.wait_for_snapshot_calls = 0
        self.start_calls = 0
        self.stop_calls = 0

    def start(self) -> None:
        self.start_calls += 1

    def stop(self) -> None:
        self.stop_calls += 1

    def get_snapshot(self) -> TelemetrySnapshot:
        with self._lock:
            self.get_snapshot_calls += 1
            return self._snapshot

    def set_snapshot(self, next_snapshot: TelemetrySnapshot) -> None:
        with self._lock:
            self._snapshot = next_snapshot

    def wait_for_snapshot(self) -> None:
        self.wait_for_snapshot_calls += 1


def test_metrics_websocket_first_message_equals_rest_contract() -> None:
    manager = StubTelemetryManager(snapshot(153))
    application = create_app(manager)  # type: ignore[arg-type]

    with TestClient(application) as client:
        rest_message = client.get("/api/v1/metrics").json()
        with client.websocket_connect("/ws/v1/metrics") as websocket:
            websocket_message = websocket.receive_json()

    assert websocket_message == rest_message
    assert websocket_message["sequence"] == 153
    assert websocket_message["captured_at"] == "2026-08-10T15:10:00Z"
    assert websocket_message["metrics"]["cpu.temperature"] == {
        "value": 54.0,
        "unit": "celsius",
        "source_sensor_identifier": "/cpu/0/temperature/package",
    }
    assert manager.wait_for_snapshot_calls == 0


def test_metrics_websocket_sends_only_after_raw_sequence_changes() -> None:
    manager = StubTelemetryManager(snapshot(20, load=20.0))
    application = create_app(manager)  # type: ignore[arg-type]

    with TestClient(application) as client:
        with client.websocket_connect("/ws/v1/metrics") as websocket:
            first = websocket.receive_json()
            assert first["sequence"] == 20
            assert first["metrics"]["cpu.load"]["value"] == 20.0

            manager.set_snapshot(snapshot(20, load=99.0))
            time.sleep(0.2)
            manager.set_snapshot(snapshot(21, load=31.0))
            second = websocket.receive_json()

    assert second["sequence"] == 21
    assert second["metrics"]["cpu.load"]["value"] == 31.0
    assert manager.get_snapshot_calls >= 2
    assert manager.wait_for_snapshot_calls == 0


def test_metrics_websocket_disconnect_is_clean_and_manager_keeps_running() -> None:
    manager = StubTelemetryManager(snapshot(30))
    application = create_app(manager)  # type: ignore[arg-type]

    with TestClient(application) as client:
        with client.websocket_connect("/ws/v1/metrics") as first:
            assert first.receive_json()["sequence"] == 30

        manager.set_snapshot(snapshot(31))
        with client.websocket_connect("/ws/v1/metrics") as second:
            assert second.receive_json()["sequence"] == 31

        assert manager.status is TelemetryStatus.RUNNING
        assert manager.stop_calls == 0

    assert manager.stop_calls == 1
    assert manager.wait_for_snapshot_calls == 0


def test_metrics_websocket_supports_multiple_independent_clients() -> None:
    manager = StubTelemetryManager(snapshot(40))
    application = create_app(manager)  # type: ignore[arg-type]

    with TestClient(application) as client:
        with (
            client.websocket_connect("/ws/v1/metrics") as first,
            client.websocket_connect("/ws/v1/metrics") as second,
        ):
            assert first.receive_json()["sequence"] == 40
            assert second.receive_json()["sequence"] == 40

            manager.set_snapshot(snapshot(41))
            assert first.receive_json()["sequence"] == 41
            assert second.receive_json()["sequence"] == 41

    assert manager.wait_for_snapshot_calls == 0
