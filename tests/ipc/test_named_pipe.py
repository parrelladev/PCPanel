from __future__ import annotations

import os
import threading
import time
import uuid
from datetime import datetime, timezone

import pytest

from app.ipc.client import TelemetryPipeClient
from app.ipc.protocol import IPCUnavailableError, IPCWin32Error
from app.ipc.server import TelemetryPipeServer
from app.ipc.win32 import (
    PIPE_REJECT_REMOTE_CLIENTS,
    PIPE_SDDL,
    close_handle,
    create_server_pipe,
    current_token_diagnostics,
    security_descriptor_sddl,
)
from app.telemetry.models import TelemetrySnapshot
from app.telemetry.source import TelemetrySnapshotSource


pytestmark = pytest.mark.skipif(os.name != "nt", reason="Windows named pipe integration")


class FakeSource:
    def __init__(self) -> None:
        self.snapshot = TelemetrySnapshot(
            sequence=9,
            captured_at=datetime(2026, 8, 10, tzinfo=timezone.utc),
            sensors=(),
        )

    def get_snapshot(self) -> TelemetrySnapshot:
        return self.snapshot


def unique_pipe() -> str:
    return rf"\\.\pipe\PCPanelTelemetry-{uuid.uuid4()}"


def serve(server: TelemetryPipeServer) -> threading.Thread:
    thread = threading.Thread(target=server.serve_once, daemon=True)
    thread.start()
    return thread


def require_representative_agent_token() -> None:
    diagnostics = current_token_diagnostics()
    restricting = {entry["sid"] for entry in diagnostics["restricted_sids"]}
    if diagnostics["is_restricted"] and "S-1-5-4" not in restricting:
        pytest.skip(
            "sandbox token restricts INTERACTIVE access; requires a normal interactive Agent token"
        )


def test_client_is_structurally_a_snapshot_source_and_connects() -> None:
    require_representative_agent_token()
    source = FakeSource()
    pipe_name = unique_pipe()
    thread = serve(TelemetryPipeServer(source, lambda: "running", pipe_name))
    client: TelemetrySnapshotSource = TelemetryPipeClient(pipe_name, timeout=1.0)

    assert client.get_snapshot() == source.snapshot
    thread.join(timeout=1.0)
    assert not thread.is_alive()


def test_client_reconnects_for_sequential_requests() -> None:
    require_representative_agent_token()
    source = FakeSource()
    pipe_name = unique_pipe()
    client = TelemetryPipeClient(pipe_name, timeout=1.0)

    first = serve(TelemetryPipeServer(source, lambda: "running", pipe_name))
    assert client.get_snapshot() == source.snapshot
    first.join(timeout=1.0)

    second = serve(TelemetryPipeServer(source, lambda: "running", pipe_name))
    assert client.get_status() == "running"
    second.join(timeout=1.0)


def test_service_unavailable_fails_within_timeout() -> None:
    client = TelemetryPipeClient(unique_pipe(), timeout=0.05)
    with pytest.raises(IPCUnavailableError):
        client.get_snapshot()


def test_security_policy_is_explicit_and_rejects_network_logons() -> None:
    assert "D:P" in PIPE_SDDL
    assert ";;;IU)" in PIPE_SDDL
    assert ";;;NU)" not in PIPE_SDDL
    assert ";;;WD)" not in PIPE_SDDL
    assert ";;;AN)" not in PIPE_SDDL
    assert PIPE_REJECT_REMOTE_CLIENTS == 0x8


def test_kernel_applies_the_explicit_secure_dacl() -> None:
    handle = create_server_pipe(unique_pipe())
    try:
        applied = security_descriptor_sddl(handle)
    finally:
        close_handle(handle)

    assert ";;;SY)" in applied
    assert ";;;BA)" in applied
    assert ";;;IU)" in applied
    assert ";;;WD)" not in applied
    assert ";;;AN)" not in applied


def test_restricted_sandbox_failure_identifies_create_file() -> None:
    diagnostics = current_token_diagnostics()
    restricting = {entry["sid"] for entry in diagnostics["restricted_sids"]}
    if not diagnostics["is_restricted"] or "S-1-5-4" in restricting:
        pytest.skip("diagnostic applies only to a token that restricts INTERACTIVE")

    source = FakeSource()
    pipe_name = unique_pipe()
    serve(TelemetryPipeServer(source, lambda: "running", pipe_name))

    with pytest.raises(IPCWin32Error) as caught:
        TelemetryPipeClient(pipe_name, timeout=1.0).get_status()

    assert caught.value.operation == "CreateFileW"
    assert caught.value.winerror == 5


def test_server_stop_cancels_blocking_listener_without_an_agent() -> None:
    server = TelemetryPipeServer(FakeSource(), lambda: "running", unique_pipe())
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    deadline = time.monotonic() + 1.0
    while not server._ready.is_set() and time.monotonic() < deadline:
        time.sleep(0.001)

    server.stop()
    thread.join(timeout=1.0)

    assert not thread.is_alive()
