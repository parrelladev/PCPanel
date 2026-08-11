from __future__ import annotations

import logging
import threading

from ..ipc.client import TelemetryPipeClient
from ..ipc.protocol import IPCError
from ..telemetry.models import TelemetrySnapshot


logger = logging.getLogger(__name__)


class AgentTelemetrySource:
    """Recovering Agent adapter around the fail-fast named pipe client."""

    def __init__(self, client: TelemetryPipeClient) -> None:
        self._client = client
        self._state_lock = threading.Lock()
        self._offline = False

    def get_snapshot(self) -> TelemetrySnapshot | None:
        try:
            snapshot = self._client.get_snapshot()
        except IPCError as exc:
            self._mark_offline(exc)
            return None
        self._mark_online()
        return snapshot

    def get_status(self) -> str:
        try:
            status = self._client.get_status()
        except IPCError as exc:
            self._mark_offline(exc)
            return "unavailable"
        self._mark_online()
        if status in {"running", "telemetry_available"}:
            return "running"
        if status == "provider_unavailable":
            return "failed"
        return "unavailable"

    def _mark_offline(self, error: IPCError) -> None:
        with self._state_lock:
            if self._offline:
                return
            self._offline = True
        logger.warning("Telemetry Service is unavailable: %s", error)

    def _mark_online(self) -> None:
        with self._state_lock:
            if not self._offline:
                return
            self._offline = False
        logger.info("Telemetry Service connection recovered")
