from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from ..actions.composition import create_action_service
from ..actions.service import ActionService
from ..auth import (
    ConsolePairingCodePresenter,
    DeviceRegistry,
    PairingCodePresenter,
    PairingService,
    TokenService,
)
from ..telemetry.manager import TelemetryManager
from .actions import router as actions_router
from .routes import router
from .websocket import router as websocket_router


WEB_ROOT = Path(__file__).resolve().parents[2] / "web"


def create_app(
    manager: TelemetryManager,
    *,
    action_service: ActionService | None = None,
    enable_actions_api: bool = False,
    token_service: TokenService | None = None,
    device_registry: DeviceRegistry | None = None,
    pairing_service: PairingService | None = None,
    pairing_code_presenter: PairingCodePresenter | None = None,
) -> FastAPI:
    """Create the application around shared Telemetry, Auth, and Actions services."""

    actions = action_service or create_action_service()
    tokens = token_service or TokenService()
    registry = device_registry or DeviceRegistry()
    pairing = pairing_service or PairingService(registry, tokens)
    presenter = pairing_code_presenter or ConsolePairingCodePresenter()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        app.state.telemetry_manager = manager
        manager.start()
        try:
            yield
        finally:
            manager.stop()

    app = FastAPI(title="PCPanel API", lifespan=lifespan)
    app.state.telemetry_manager = manager
    app.state.action_service = actions
    app.state.enable_actions_api = enable_actions_api
    app.state.token_service = tokens
    app.state.device_registry = registry
    app.state.pairing_service = pairing
    app.state.pairing_code_presenter = presenter
    app.include_router(router)
    app.include_router(websocket_router)
    if enable_actions_api:
        app.include_router(actions_router)
    app.mount("/css", StaticFiles(directory=WEB_ROOT / "css"), name="css")
    app.mount("/js", StaticFiles(directory=WEB_ROOT / "js"), name="js")
    app.mount("/assets", StaticFiles(directory=WEB_ROOT / "assets"), name="assets")

    @app.get("/", include_in_schema=False)
    def frontend() -> FileResponse:
        return FileResponse(WEB_ROOT / "index.html")

    @app.get("/manifest.webmanifest", include_in_schema=False)
    def web_manifest() -> FileResponse:
        return FileResponse(
            WEB_ROOT / "manifest.webmanifest",
            media_type="application/manifest+json",
        )

    return app
