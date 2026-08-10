from __future__ import annotations

from typing import Annotated, cast

from fastapi import APIRouter, Depends, HTTPException, Request, status

from ..auth import (
    PairingAlreadyConsumedError,
    PairingAttemptsExceededError,
    PairingCapacityError,
    PairingCodePresenter,
    PairingExpiredError,
    PairingInvalidCodeError,
    PairingNotFoundError,
    PairingService,
    AuthorizedDevice,
)
from ..telemetry.manager import TelemetryManager
from ..telemetry.models import SensorReading, TelemetrySnapshot
from .metric_contract import metrics_response_from_raw
from .dependencies import require_authorized_device
from .schemas import (
    ApiHealthStatus,
    AuthenticatedDeviceResponse,
    AuthStatusResponse,
    ErrorResponse,
    HealthResponse,
    MetricsResponse,
    PairingCompleteRequest,
    PairingCompleteResponse,
    PairingStartRequest,
    PairingStartResponse,
    SensorCatalogItem,
    SensorCatalogResponse,
    TelemetryHealthStatus,
    TelemetryResponse,
)


router = APIRouter(prefix="/api/v1")


@router.get(
    "/auth/status",
    response_model=AuthStatusResponse,
    responses={status.HTTP_401_UNAUTHORIZED: {"model": ErrorResponse}},
)
def get_auth_status(
    device: Annotated[AuthorizedDevice, Depends(require_authorized_device)],
) -> AuthStatusResponse:
    return AuthStatusResponse(
        authenticated=True,
        device=AuthenticatedDeviceResponse(id=device.id, name=device.name),
    )


@router.post(
    "/pairing/start",
    response_model=PairingStartResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        status.HTTP_422_UNPROCESSABLE_CONTENT: {"model": ErrorResponse},
        status.HTTP_429_TOO_MANY_REQUESTS: {"model": ErrorResponse},
    },
)
def start_pairing(
    payload: PairingStartRequest,
    request: Request,
) -> PairingStartResponse:
    pairing = cast(PairingService, request.app.state.pairing_service)
    presenter = cast(
        PairingCodePresenter,
        request.app.state.pairing_code_presenter,
    )
    try:
        challenge = pairing.start_pairing(payload.device_name)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Invalid device name",
        ) from exc
    except PairingCapacityError as exc:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Pairing capacity has been reached",
        ) from exc

    presenter.present(challenge)
    return PairingStartResponse(
        pairing_id=challenge.pairing_id,
        expires_at=challenge.expires_at,
    )


@router.post(
    "/pairing/complete",
    response_model=PairingCompleteResponse,
    responses={
        status.HTTP_401_UNAUTHORIZED: {"model": ErrorResponse},
        status.HTTP_404_NOT_FOUND: {"model": ErrorResponse},
        status.HTTP_409_CONFLICT: {"model": ErrorResponse},
        status.HTTP_410_GONE: {"model": ErrorResponse},
        status.HTTP_429_TOO_MANY_REQUESTS: {"model": ErrorResponse},
    },
)
def complete_pairing(
    payload: PairingCompleteRequest,
    request: Request,
) -> PairingCompleteResponse:
    pairing = cast(PairingService, request.app.state.pairing_service)
    try:
        issued = pairing.complete_pairing(payload.pairing_id, payload.code)
    except PairingNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Pairing was not found",
        ) from exc
    except PairingExpiredError as exc:
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail="Pairing has expired",
        ) from exc
    except PairingInvalidCodeError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Pairing code is invalid",
        ) from exc
    except PairingAttemptsExceededError as exc:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Pairing attempts have been exhausted",
        ) from exc
    except PairingAlreadyConsumedError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Pairing was already consumed",
        ) from exc

    return PairingCompleteResponse(
        device_id=issued.device_id,
        token=issued.token,
    )


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
    "/metrics",
    response_model=MetricsResponse,
    responses={status.HTTP_503_SERVICE_UNAVAILABLE: {"model": ErrorResponse}},
)
def get_metrics(request: Request) -> MetricsResponse:
    """Resolve the latest in-memory raw snapshot into canonical metrics."""

    return metrics_response_from_raw(_get_snapshot_or_503(request))


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
