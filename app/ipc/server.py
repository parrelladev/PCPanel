from __future__ import annotations

import threading
import time
from collections.abc import Callable

from ..telemetry.source import TelemetrySnapshotSource
from .protocol import (
    Command,
    PIPE_NAME,
    PROTOCOL_VERSION,
    ResponseType,
    decode_message,
    encode_message,
    error_message,
    snapshot_message,
)
from .win32 import (
    close_handle,
    cancel_thread_io,
    connect_server,
    create_server_pipe,
    disconnect,
    flush_pipe,
    read_frame,
    write_all,
)


class TelemetryPipeServer:
    """Serve only raw telemetry and service status over a local named pipe."""

    def __init__(
        self,
        source: TelemetrySnapshotSource,
        status: Callable[[], str],
        pipe_name: str = PIPE_NAME,
    ) -> None:
        self._source = source
        self._status = status
        self._pipe_name = pipe_name
        self._stop_event = threading.Event()
        self._ready = threading.Event()
        self._thread_id: int | None = None

    def serve_forever(self) -> None:
        """Accept sequential Agent requests until ``stop`` cancels the listener."""

        self._stop_event.clear()
        self._thread_id = threading.get_native_id()
        self._ready.set()
        try:
            while not self._stop_event.is_set():
                try:
                    self.serve_once()
                except Exception:
                    if self._stop_event.is_set():
                        break
                    raise
        finally:
            self._thread_id = None
            self._ready.clear()

    def stop(self) -> None:
        self._stop_event.set()
        self._ready.wait(timeout=1.0)
        deadline = time.monotonic() + 1.0
        while self._thread_id is not None and time.monotonic() < deadline:
            cancel_thread_io(self._thread_id)
            time.sleep(0.001)

    def serve_once(self) -> None:
        handle = create_server_pipe(self._pipe_name)
        try:
            connect_server(handle)
            try:
                request = decode_message(read_frame(handle))
                command = request.get("command")
                if command == Command.GET_LATEST_SNAPSHOT.value:
                    response = snapshot_message(self._source.get_snapshot())
                elif command == Command.GET_STATUS.value:
                    response = {
                        "protocol_version": PROTOCOL_VERSION,
                        "type": ResponseType.SERVICE_STATUS.value,
                        "status": self._status(),
                    }
                else:
                    response = error_message("Unknown telemetry IPC command")
                write_all(handle, encode_message(response))
                flush_pipe(handle)
            finally:
                disconnect(handle)
        finally:
            close_handle(handle)
