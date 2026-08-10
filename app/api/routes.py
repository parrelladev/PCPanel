from __future__ import annotations

from typing import cast

from fastapi import APIRouter, HTTPException, Request, status

from ..telemetry.manager import TelemetryManager
from ..telemetry.models import SensorReading, TelemetrySnapshot
from .schemas import (
    ApiHealthStatus,
    ErrorResponse,
    HealthResponse,
    SensorCatalogItem,
    SensorCatalogResponse,
    TelemetryHealthStatus,
    TelemetryResponse,
)


router = APIRouter(prefix="/api/v1")


@router.get("/health", response_model=HealthResponse)
def get_health(request: Request) -> HealthResponse:
    """Report API health using only the manager's in-memory lifecycle state."""

    manager = cast(
        TelemetryManager,
        request.app.state.telemetry_manager,
    )
    return HealthResponse(
        status=ApiHealthStatus.OK,
        telemetry_status=TelemetryHealthStatus(manager.status.value),
    )


@router.get(
    "/telemetry",
    response_model=TelemetryResponse,
    responses={status.HTTP_503_SERVICE_UNAVAILABLE: {"model": ErrorResponse}},
)
def get_telemetry(request: Request) -> TelemetryResponse:
    """Return the latest completed snapshot without triggering collection."""

    snapshot = _get_snapshot_or_503(request)

    return TelemetryResponse.from_snapshot(snapshot)


@router.get(
    "/sensors",
    response_model=SensorCatalogResponse,
    responses={status.HTTP_503_SERVICE_UNAVAILABLE: {"model": ErrorResponse}},
)
def get_sensors(request: Request) -> SensorCatalogResponse:
    """Derive sensor metadata from the latest completed snapshot."""

    snapshot = _get_snapshot_or_503(request)
    return SensorCatalogResponse(
        sensors=[_serialize_catalog_item(sensor) for sensor in snapshot.sensors],
    )


def _get_snapshot_or_503(request: Request) -> TelemetrySnapshot:
    manager = cast(
        TelemetryManager,
        request.app.state.telemetry_manager,
    )
    snapshot = manager.get_snapshot()
    if snapshot is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Telemetry snapshot is not available yet",
        )
    return snapshot


def _serialize_catalog_item(sensor: SensorReading) -> SensorCatalogItem:
    return SensorCatalogItem(
        hardware_identifier=sensor.hardware_identifier,
        hardware_name=sensor.hardware_name,
        hardware_type=sensor.hardware_type,
        sensor_identifier=sensor.sensor_identifier,
        sensor_name=sensor.sensor_name,
        sensor_type=sensor.sensor_type,
    )
