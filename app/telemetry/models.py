from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(slots=True, frozen=True)
class HardwareInfo:
    """Basic information about a detected hardware device."""

    name: str
    hardware_type: str
    identifier: str | None = None


@dataclass(slots=True, frozen=True)
class SensorReading:
    """Normalized snapshot of a hardware sensor reading."""

    hardware_identifier: str
    hardware_name: str
    hardware_type: str
    sensor_identifier: str
    sensor_name: str
    sensor_type: str
    value: float | None
    min_value: float | None
    max_value: float | None


@dataclass(slots=True, frozen=True)
class TelemetrySnapshot:
    """Immutable telemetry collection captured at a timezone-aware instant."""

    sequence: int
    captured_at: datetime
    sensors: tuple[SensorReading, ...]
