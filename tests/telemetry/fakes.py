from __future__ import annotations

import threading
from collections.abc import Sequence

from app.telemetry.models import SensorReading
from app.telemetry.providers.base import TelemetryProvider


class FakeTelemetryProvider(TelemetryProvider):
    """Observable, deterministic provider for TelemetryManager tests."""

    def __init__(
        self,
        sensors: Sequence[SensorReading],
        *,
        fail_open: bool = False,
        update_failures: int = 0,
    ) -> None:
        self.sensors = tuple(sensors)
        self.fail_open = fail_open
        self.update_failures = update_failures

        self.open_calls = 0
        self.close_calls = 0
        self.update_calls = 0
        self.get_sensors_calls = 0
        self.method_threads: dict[str, list[int]] = {
            "open": [],
            "close": [],
            "update": [],
            "get_sensors": [],
        }
        self.opened = threading.Event()
        self.closed = threading.Event()
        self._calls_changed = threading.Condition()

    def wait_for_calls(
        self,
        method: str,
        minimum: int,
        timeout: float = 1.0,
    ) -> bool:
        attribute = f"{method}_calls"
        with self._calls_changed:
            return self._calls_changed.wait_for(
                lambda: getattr(self, attribute) >= minimum,
                timeout=timeout,
            )

    def _record(self, method: str) -> None:
        attribute = f"{method}_calls"
        with self._calls_changed:
            setattr(self, attribute, getattr(self, attribute) + 1)
            self.method_threads[method].append(threading.get_ident())
            self._calls_changed.notify_all()

    def open(self) -> None:
        self._record("open")
        if self.fail_open:
            raise RuntimeError("simulated open failure")
        self.opened.set()

    def close(self) -> None:
        self._record("close")
        self.closed.set()

    def update(self) -> None:
        self._record("update")
        if self.update_failures:
            self.update_failures -= 1
            raise RuntimeError("simulated read failure")

    def get_sensors(self) -> list[SensorReading]:
        self._record("get_sensors")
        return list(self.sensors)
