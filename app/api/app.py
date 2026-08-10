from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from ..telemetry.manager import TelemetryManager
from .routes import router
from .websocket import router as websocket_router


WEB_ROOT = Path(__file__).resolve().parents[2] / "web"


def create_app(manager: TelemetryManager) -> FastAPI:
    """Create the HTTP application around one shared telemetry manager."""

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
    app.include_router(router)
    app.include_router(websocket_router)
    app.mount("/css", StaticFiles(directory=WEB_ROOT / "css"), name="css")
    app.mount("/js", StaticFiles(directory=WEB_ROOT / "js"), name="js")

    @app.get("/", include_in_schema=False)
    def frontend() -> FileResponse:
        return FileResponse(WEB_ROOT / "index.html")

    return app
