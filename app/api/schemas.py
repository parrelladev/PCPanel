from __future__ import annotations

import math
from datetime import datetime
from enum import Enum
from typing import Self

from pydantic import BaseModel

from ..telemetry.metrics import MetricReading, MetricSnapshot
from ..telemetry.models import SensorReading, TelemetrySnapshot


class ApiHealthStatus(str, Enum):
    """Public health states for the HTTP API itself."""

    OK = "ok"


class TelemetryHealthStatus(str, Enum):
    """Public representation of telemetry lifecycle states."""

    STOPPED = "stopped"
    STARTING = "starting"
    RUNNING = "running"
    FAILED = "failed"


class HealthResponse(BaseModel):
    """Small health contract for the API and telemetry runtime."""

    status: ApiHealthStatus
    telemetry_status: TelemetryHealthStatus


class SensorResponse(BaseModel):
    """JSON-safe representation of one raw sensor reading."""

    hardware_identifier: str
    hardware_name: str
    hardware_type: str
    sensor_identifier: str
    sensor_name: str
    sensor_type: str
    value: float | None
    min_value: float | None
    max_value: float | None

    @classmethod
    def from_reading(cls, reading: SensorReading) -> Self:
        return cls(
            hardware_identifier=reading.hardware_identifier,
            hardware_name=reading.hardware_name,
            hardware_type=reading.hardware_type,
            sensor_identifier=reading.sensor_identifier,
            sensor_name=reading.sensor_name,
            sensor_type=reading.sensor_type,
            value=_json_float(reading.value),
            min_value=_json_float(reading.min_value),
            max_value=_json_float(reading.max_value),
        )


class TelemetryResponse(BaseModel):
    """HTTP representation of the latest telemetry snapshot."""

    sequence: int
    captured_at: datetime
    sensors: list[SensorResponse]

    @classmethod
    def from_snapshot(cls, snapshot: TelemetrySnapshot) -> Self:
        return cls(
            sequence=snapshot.sequence,
            captured_at=snapshot.captured_at,
            sensors=[SensorResponse.from_reading(sensor) for sensor in snapshot.sensors],
        )


class MetricReadingResponse(BaseModel):
    """HTTP representation of one canonical metric reading."""

    value: float | None
    unit: str
    source_sensor_identifier: str | None

    @classmethod
    def from_reading(cls, reading: MetricReading) -> Self:
        return cls(
            value=_json_float(reading.value),
            unit=reading.unit,
            source_sensor_identifier=reading.source_sensor_identifier,
        )


class MetricsResponse(BaseModel):
    """Product-facing canonical metrics indexed by their stable keys."""

    sequence: int
    captured_at: datetime
    metrics: dict[str, MetricReadingResponse]

    @classmethod
    def from_snapshot(cls, snapshot: MetricSnapshot) -> Self:
        return cls(
            sequence=snapshot.sequence,
            captured_at=snapshot.captured_at,
            metrics={
                reading.key: MetricReadingResponse.from_reading(reading)
                for reading in snapshot.metrics
            },
        )


class SensorCatalogItem(BaseModel):
    """Stable metadata describing one available sensor."""

    hardware_identifier: str
    hardware_name: str
    hardware_type: str
    sensor_identifier: str
    sensor_name: str
    sensor_type: str


class SensorCatalogResponse(BaseModel):
    """Catalog derived from the sensors in the latest snapshot."""

    sensors: list[SensorCatalogItem]


class ErrorResponse(BaseModel):
    """Simple error contract shared by API failure responses."""

    detail: str


def _json_float(value: float | None) -> float | None:
    if value is None or not math.isfinite(value):
        return None
    return value
