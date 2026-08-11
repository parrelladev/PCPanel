from __future__ import annotations

from ..telemetry.models import TelemetrySnapshot
from .protocol import (
    Command,
    IPCProtocolError,
    PIPE_NAME,
    command_message,
    decode_message,
    encode_message,
    snapshot_from_message,
)
from .win32 import close_handle, open_client, read_frame, write_all


class TelemetryPipeClient:
    """Bounded, read-only client used as an Agent snapshot source."""

    def __init__(self, pipe_name: str = PIPE_NAME, timeout: float = 1.0) -> None:
        if timeout <= 0:
            raise ValueError("timeout must be greater than zero")
        self._pipe_name = pipe_name
        self._timeout = timeout

    def get_snapshot(self) -> TelemetrySnapshot | None:
        return snapshot_from_message(self._request(Command.GET_LATEST_SNAPSHOT))

    def get_status(self) -> str:
        response = self._request(Command.GET_STATUS)
        if response.get("type") != "SERVICE_STATUS" or not isinstance(response.get("status"), str):
            raise IPCProtocolError("Unexpected IPC status response")
        return response["status"]

    def _request(self, command: Command) -> dict[str, object]:
        handle = open_client(self._pipe_name, self._timeout)
        try:
            write_all(handle, encode_message(command_message(command)))
            return decode_message(read_frame(handle))
        finally:
            close_handle(handle)
