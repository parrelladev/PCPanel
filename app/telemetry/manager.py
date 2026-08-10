from __future__ import annotations

import logging
import threading
from datetime import datetime, timezone
from enum import Enum

from .models import TelemetrySnapshot
from .providers.base import TelemetryProvider


logger = logging.getLogger(__name__)


class TelemetryStatus(Enum):
    """Lifecycle state of a TelemetryManager."""

    STOPPED = "stopped"
    STARTING = "starting"
    RUNNING = "running"
    FAILED = "failed"


class TelemetryManager:
    """Collect and publish telemetry snapshots from one dedicated thread."""

    def __init__(
        self,
        provider: TelemetryProvider,
        interval: float = 0.5,
    ) -> None:
        if interval <= 0:
            raise ValueError("interval must be greater than zero")

        self._provider = provider
        self._interval = float(interval)
        self._stop_event = threading.Event()
        self._state_lock = threading.Lock()
        self._state_changed = threading.Condition(self._state_lock)
        self._thread: threading.Thread | None = None
        self._status = TelemetryStatus.STOPPED
        self._latest_snapshot: TelemetrySnapshot | None = None
        self._last_error: Exception | None = None
        self._sequence = 0

    @property
    def status(self) -> TelemetryStatus:
        with self._state_lock:
            return self._status

    @property
    def last_error(self) -> Exception | None:
        with self._state_lock:
            return self._last_error

    def start(self) -> None:
        """Start the telemetry worker unless it is already active."""

        with self._state_lock:
            if self._thread is not None and self._thread.is_alive():
                return

            self._stop_event.clear()
            self._status = TelemetryStatus.STARTING
            self._last_error = None
            worker = threading.Thread(
                target=self._run,
                name="pcpanel-telemetry",
                daemon=True,
            )
            self._thread = worker

            try:
                worker.start()
            except Exception as exc:
                self._thread = None
                self._status = TelemetryStatus.FAILED
                self._last_error = exc
                self._state_changed.notify_all()
                raise

    def stop(self) -> None:
        """Signal the telemetry worker and wait for its cleanup to finish."""

        with self._state_lock:
            worker = self._thread

        if worker is None:
            return

        self._stop_event.set()
        worker.join()

    def get_snapshot(self) -> TelemetrySnapshot | None:
        """Return the latest published snapshot without collecting telemetry."""

        with self._state_lock:
            return self._latest_snapshot

    def wait_for_snapshot(
        self,
        timeout: float | None = None,
    ) -> TelemetrySnapshot | None:
        """Wait for a snapshot, failure, stop, or timeout without collecting."""

        with self._state_changed:
            self._state_changed.wait_for(
                lambda: (
                    self._latest_snapshot is not None
                    or self._status in {
                        TelemetryStatus.FAILED,
                        TelemetryStatus.STOPPED,
                    }
                ),
                timeout=timeout,
            )
            return self._latest_snapshot

    def _run(self) -> None:
        provider_opened = False
        fatal_error: Exception | None = None

        try:
            self._provider.open()
            provider_opened = True

            with self._state_lock:
                self._status = TelemetryStatus.RUNNING

            while not self._stop_event.is_set():
                try:
                    self._provider.update()
                    sensors = self._provider.get_sensors()
                    captured_at = datetime.now(timezone.utc)

                    with self._state_lock:
                        self._sequence += 1
                        self._latest_snapshot = TelemetrySnapshot(
                            sequence=self._sequence,
                            captured_at=captured_at,
                            sensors=tuple(sensors),
                        )
                        self._last_error = None
                        self._state_changed.notify_all()
                except Exception as exc:
                    logger.exception("Telemetry collection failed; retrying")
                    with self._state_lock:
                        self._last_error = exc

                if self._stop_event.wait(self._interval):
                    break
        except Exception as exc:
            fatal_error = exc
            logger.exception("Telemetry worker failed")
        finally:
            if provider_opened:
                try:
                    self._provider.close()
                except Exception as exc:
                    logger.exception("Failed to close telemetry provider")
                    if fatal_error is None:
                        fatal_error = exc

            with self._state_lock:
                self._thread = None
                if fatal_error is None:
                    self._status = TelemetryStatus.STOPPED
                else:
                    self._status = TelemetryStatus.FAILED
                    self._last_error = fatal_error
                self._state_changed.notify_all()
