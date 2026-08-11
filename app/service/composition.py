from __future__ import annotations

from ..config import AppSettings
from ..ipc.server import TelemetryPipeServer
from ..telemetry.manager import TelemetryManager
from ..telemetry.providers.librehardwaremonitor import LibreHardwareMonitorProvider
from .runtime import TelemetryServiceRuntime


def create_telemetry_service_runtime(
    settings: AppSettings | None = None,
) -> TelemetryServiceRuntime:
    """Compose the hardware-only service process without network or persistence."""

    resolved = settings or AppSettings.from_env()
    provider = LibreHardwareMonitorProvider(dll_path=resolved.lhm_dll_path)
    manager = TelemetryManager(provider, interval=resolved.telemetry_interval)
    runtime: TelemetryServiceRuntime
    server = TelemetryPipeServer(manager, lambda: runtime.status)
    runtime = TelemetryServiceRuntime(manager, server)
    return runtime
