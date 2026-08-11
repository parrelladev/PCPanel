from __future__ import annotations

from unittest.mock import Mock

from app.service.runtime import TelemetryServiceRuntime
from app.telemetry.manager import TelemetryManager, TelemetryStatus


def manager_mock(status: TelemetryStatus = TelemetryStatus.RUNNING) -> Mock:
    manager = Mock(spec=TelemetryManager)
    manager.status = status
    manager.get_snapshot.return_value = None
    return manager


def test_runtime_starts_manager_and_ipc_source() -> None:
    manager = manager_mock()
    server = Mock()
    runtime = TelemetryServiceRuntime(manager, server)

    runtime.start()
    runtime.stop()

    manager.start.assert_called_once_with()
    server.serve_forever.assert_called_once_with()
    server.stop.assert_called_once_with()
    manager.stop.assert_called_once_with()


def test_runtime_can_restart_logically() -> None:
    manager = manager_mock()
    server = Mock()
    runtime = TelemetryServiceRuntime(manager, server)

    runtime.start()
    runtime.stop()
    runtime.start()
    runtime.stop()

    assert manager.start.call_count == 2
    assert manager.stop.call_count == 2
    assert server.serve_forever.call_count == 2
    assert server.stop.call_count == 2


def test_provider_failure_has_controlled_status() -> None:
    manager = manager_mock(TelemetryStatus.FAILED)
    server = Mock()

    assert TelemetryServiceRuntime(manager, server).status == "provider_unavailable"
