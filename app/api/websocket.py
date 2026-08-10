from __future__ import annotations

import asyncio
from typing import cast

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from ..telemetry.manager import TelemetryManager
from .schemas import TelemetryResponse


POLL_INTERVAL_SECONDS = 0.1

router = APIRouter()


@router.websocket("/ws/v1/telemetry")
async def telemetry_websocket(websocket: WebSocket) -> None:
    """Stream each newly observed telemetry snapshot to one client."""

    manager = cast(
        TelemetryManager,
        websocket.app.state.telemetry_manager,
    )
    last_sequence: int | None = None
    await websocket.accept()

    try:
        while True:
            snapshot = manager.get_snapshot()
            if snapshot is not None and snapshot.sequence != last_sequence:
                response = TelemetryResponse.from_snapshot(snapshot)
                await websocket.send_json(response.model_dump(mode="json"))
                last_sequence = snapshot.sequence

            await asyncio.sleep(POLL_INTERVAL_SECONDS)
    except WebSocketDisconnect:
        return
