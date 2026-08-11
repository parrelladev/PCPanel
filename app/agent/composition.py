from __future__ import annotations

from fastapi import FastAPI

from ..actions.composition import create_action_service
from ..api.app import create_app
from ..auth import DeviceRegistry, PairingService, TokenService
from ..config import AppSettings
from ..ipc.client import TelemetryPipeClient
from ..persistence import Database, SQLiteActionStore, SQLiteDeviceStore
from .telemetry import AgentTelemetrySource
from .pairing import WindowsPairingCodePresenter


def build_agent_app(settings: AppSettings | None = None) -> FastAPI:
    """Compose the non-elevated Agent without loading a hardware provider."""

    resolved = settings or AppSettings.from_env()
    source = AgentTelemetrySource(TelemetryPipeClient(timeout=0.2))
    database = Database(
        resolved.data_dir,
        restrict_permissions=resolved.packaged_runtime,
    )
    database.initialize()
    action_store = SQLiteActionStore(database)
    actions = tuple(
        record.definition
        for record in action_store.load_actions()
        if record.enabled
    )
    action_service = create_action_service(actions=actions)
    device_registry = DeviceRegistry(store=SQLiteDeviceStore(database))
    token_service = TokenService()
    pairing_service = PairingService(device_registry, token_service)
    return create_app(
        telemetry_source=source,
        telemetry_status=source.get_status,
        action_service=action_service,
        enable_actions_api=resolved.enable_actions_api,
        token_service=token_service,
        device_registry=device_registry,
        pairing_service=pairing_service,
        pairing_code_presenter=WindowsPairingCodePresenter(),
    )
