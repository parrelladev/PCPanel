from __future__ import annotations

import logging
import threading
import time
from collections.abc import Callable

import pytest

from app.telemetry.manager import TelemetryManager, TelemetryStatus
from app.telemetry.models import SensorReading, TelemetrySnapshot

from .fakes import FakeTelemetryProvider


EXPECTED_SENSOR = SensorReading(
    hardware_identifier="/cpu/0",
    hardware_name="CPU",
    hardware_type="Cpu",
    sensor_identifier="/cpu/0/load/0",
    sensor_name="CPU Total",
    sensor_type="Load",
    value=42.0,
    min_value=10.0,
    max_value=80.0,
)


def _wait_until(predicate: Callable[[], bool], timeout: float = 1.0) -> None:
    deadline = time.monotonic() + timeout
    while not predicate():
        if time.monotonic() >= deadline:
            raise AssertionError("condition was not reached before timeout")
        time.sleep(0.001)


def _wait_for_sequence(
    manager: TelemetryManager,
    minimum: int,
) -> TelemetrySnapshot:
    _wait_until(
        lambda: (
            (snapshot := manager.get_snapshot()) is not None
            and snapshot.sequence >= minimum
        )
    )
    snapshot = manager.get_snapshot()
    assert snapshot is not None
    return snapshot


def test_wait_for_snapshot_returns_first_snapshot() -> None:
    provider = FakeTelemetryProvider([EXPECTED_SENSOR])
    manager = TelemetryManager(provider, interval=0.01)

    manager.start()
    snapshot = manager.wait_for_snapshot(timeout=1.0)
    manager.stop()

    assert snapshot is not None
    assert snapshot.sequence == 1
    assert snapshot.sensors == (EXPECTED_SENSOR,)


def test_wait_for_snapshot_returns_none_on_initialization_failure() -> None:
    provider = FakeTelemetryProvider([EXPECTED_SENSOR], fail_open=True)
    manager = TelemetryManager(provider, interval=0.01)

    manager.start()
    snapshot = manager.wait_for_snapshot(timeout=1.0)
    manager.stop()

    assert snapshot is None
    assert manager.status is TelemetryStatus.FAILED


def test_lifecycle_snapshots_and_worker_thread_ownership() -> None:
    provider = FakeTelemetryProvider([EXPECTED_SENSOR])
    manager = TelemetryManager(provider, interval=0.005)
    main_thread = threading.get_ident()

    manager.start()
    manager.start()
    assert provider.opened.wait(timeout=1.0)

    first = _wait_for_sequence(manager, 1)
    second = _wait_for_sequence(manager, first.sequence + 1)

    manager.stop()
    manager.stop()

    assert provider.open_calls == 1
    assert provider.update_calls >= 2
    assert provider.get_sensors_calls >= 2
    assert provider.close_calls == 1
    assert provider.closed.is_set()
    assert manager.status is TelemetryStatus.STOPPED

    assert second.sequence > first.sequence
    assert second.captured_at.tzinfo is not None
    assert second.captured_at.utcoffset() is not None
    assert second.sensors == (EXPECTED_SENSOR,)

    all_thread_ids = {
        thread_id
        for calls in provider.method_threads.values()
        for thread_id in calls
    }
    assert len(all_thread_ids) == 1
    assert main_thread not in all_thread_ids


def test_snapshot_can_be_read_from_another_thread() -> None:
    provider = FakeTelemetryProvider([EXPECTED_SENSOR])
    manager = TelemetryManager(provider, interval=0.01)
    observed: list[TelemetrySnapshot | None] = []

    manager.start()
    expected = _wait_for_sequence(manager, 1)

    reader = threading.Thread(target=lambda: observed.append(manager.get_snapshot()))
    reader.start()
    reader.join(timeout=1.0)
    manager.stop()

    assert not reader.is_alive()
    assert observed == [expected]


def test_recoverable_read_failure_is_logged_and_collection_continues(
    caplog: pytest.LogCaptureFixture,
) -> None:
    provider = FakeTelemetryProvider([EXPECTED_SENSOR], update_failures=1)
    manager = TelemetryManager(provider, interval=0.005)

    with caplog.at_level(logging.ERROR, logger="app.telemetry.manager"):
        manager.start()
        snapshot = _wait_for_sequence(manager, 1)
        manager.stop()

    assert provider.update_calls >= 2
    assert provider.get_sensors_calls >= 1
    assert snapshot.sensors == (EXPECTED_SENSOR,)
    assert manager.status is TelemetryStatus.STOPPED
    assert "Telemetry collection failed; retrying" in caplog.text


def test_fatal_open_failure_is_observable() -> None:
    provider = FakeTelemetryProvider([EXPECTED_SENSOR], fail_open=True)
    manager = TelemetryManager(provider, interval=0.005)

    manager.start()
    _wait_until(lambda: manager.status is TelemetryStatus.FAILED)
    manager.stop()

    assert isinstance(manager.last_error, RuntimeError)
    assert manager.get_snapshot() is None
    assert provider.open_calls == 1
    assert provider.update_calls == 0
    assert provider.get_sensors_calls == 0
    assert provider.close_calls == 0


def test_interval_must_be_positive() -> None:
    provider = FakeTelemetryProvider([EXPECTED_SENSOR])

    with pytest.raises(ValueError, match="greater than zero"):
        TelemetryManager(provider, interval=0)
