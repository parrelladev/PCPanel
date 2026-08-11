from __future__ import annotations

import logging
import threading
from typing import Protocol

from ..telemetry.manager import TelemetryManager, TelemetryStatus


logger = logging.getLogger(__name__)


class TelemetryIPCServer(Protocol):
    def serve_forever(self) -> None: ...
    def stop(self) -> None: ...


class TelemetryServiceRuntime:
    """Own only the telemetry manager and its local read-only IPC server."""

    def __init__(self, manager: TelemetryManager, ipc_server: TelemetryIPCServer) -> None:
        self._manager = manager
        self._ipc_server = ipc_server
        self._ipc_thread: threading.Thread | None = None

    @property
    def status(self) -> str:
        snapshot = self._manager.get_snapshot()
        if self._manager.status is TelemetryStatus.FAILED:
            return "provider_unavailable"
        if snapshot is not None:
            return "telemetry_available"
        return self._manager.status.value

    def start(self) -> None:
        if self._ipc_thread is not None and self._ipc_thread.is_alive():
            return
        logger.info("Starting PCPanel telemetry service runtime")
        self._manager.start()
        worker = threading.Thread(
            target=self._ipc_server.serve_forever,
            name="pcpanel-telemetry-ipc",
            daemon=False,
        )
        self._ipc_thread = worker
        try:
            worker.start()
        except Exception:
            self._ipc_thread = None
            self._manager.stop()
            raise

    def stop(self) -> None:
        logger.info("Stopping PCPanel telemetry service runtime")
        worker = self._ipc_thread
        if worker is not None:
            self._ipc_server.stop()
            worker.join()
            self._ipc_thread = None
        self._manager.stop()
