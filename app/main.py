from __future__ import annotations

import uvicorn
from fastapi import FastAPI

from .api.app import create_app
from .config import AppSettings
from .telemetry.manager import TelemetryManager
from .telemetry.providers.librehardwaremonitor import (
    LibreHardwareMonitorProvider,
)


def build_app(settings: AppSettings | None = None) -> FastAPI:
    """Compose the application runtime without starting the HTTP server."""

    resolved_settings = settings or AppSettings.from_env()
    provider = LibreHardwareMonitorProvider(
        dll_path=resolved_settings.lhm_dll_path,
    )
    manager = TelemetryManager(
        provider,
        interval=resolved_settings.telemetry_interval,
    )
    return create_app(manager)


def main() -> None:
    """Start PCPanel's HTTP server using environment-backed settings."""

    settings = AppSettings.from_env()
    application = build_app(settings)
    uvicorn.run(application, host=settings.host, port=settings.port)


if __name__ == "__main__":
    main()
