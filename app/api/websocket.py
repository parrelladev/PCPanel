from __future__ import annotations

import asyncio
from collections.abc import Callable
from typing import cast

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

from ..telemetry.manager import TelemetryManager
from ..telemetry.models import TelemetrySnapshot
from .metric_contract import metrics_response_from_raw
from .schemas import TelemetryResponse


POLL_INTERVAL_SECONDS = 0.1

router = APIRouter()


@router.websocket("/ws/v1/telemetry")
async def telemetry_websocket(websocket: WebSocket) -> None:
    """Stream each newly observed telemetry snapshot to one client."""

    await _stream_snapshots(websocket, TelemetryResponse.from_snapshot)


@router.websocket("/ws/v1/metrics")
async def metrics_websocket(websocket: WebSocket) -> None:
    """Stream canonical metrics for each newly observed raw snapshot."""

    await _stream_snapshots(websocket, metrics_response_from_raw)


async def _stream_snapshots(
    websocket: WebSocket,
    serialize: Callable[[TelemetrySnapshot], BaseModel],
) -> None:
    """Send each sequence once using a client-local sequence cursor."""

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
                response = serialize(snapshot)
                try:
                    await websocket.send_json(response.model_dump(mode="json"))
                except (WebSocketDisconnect, ConnectionError, OSError, RuntimeError):
                    # The browser may disappear between the connection-state
                    # check and the actual socket write (refresh, rotation, or
                    # backend shutdown). Treat that race as a normal disconnect.
                    return
                last_sequence = snapshot.sequence

            await asyncio.sleep(POLL_INTERVAL_SECONDS)
    except WebSocketDisconnect:
        return
