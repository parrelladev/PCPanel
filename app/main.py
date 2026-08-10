from __future__ import annotations

import uvicorn
from fastapi import FastAPI

from .actions.composition import create_action_service
from .api.app import create_app
from .auth import DeviceRegistry, PairingService, TokenService
from .config import AppSettings
from .persistence import Database, SQLiteActionStore, SQLiteDeviceStore
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
    database = Database(resolved_settings.data_dir)
    database.initialize()
    action_store = SQLiteActionStore(database)
    enabled_actions = tuple(
        record.definition
        for record in action_store.load_actions()
        if record.enabled
    )
    action_service = create_action_service(actions=enabled_actions)
    device_store = SQLiteDeviceStore(database)
    device_registry = DeviceRegistry(store=device_store)
    token_service = TokenService()
    pairing_service = PairingService(device_registry, token_service)
    return create_app(
        manager,
        action_service=action_service,
        enable_actions_api=resolved_settings.enable_actions_api,
        token_service=token_service,
        device_registry=device_registry,
        pairing_service=pairing_service,
    )


def main() -> None:
    """Start PCPanel's HTTP server using environment-backed settings."""

    settings = AppSettings.from_env()
    application = build_app(settings)
    uvicorn.run(application, host=settings.host, port=settings.port)


if __name__ == "__main__":
    main()
