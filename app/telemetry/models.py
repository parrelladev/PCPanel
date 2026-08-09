from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True, frozen=True)
class HardwareInfo:
    """Basic information about a detected hardware device."""

    name: str
    hardware_type: str
    identifier: str | None = None


@dataclass(slots=True, frozen=True)
class SensorReading:
    """Normalized snapshot of a hardware sensor reading."""

    hardware_name: str
    hardware_type: str
    sensor_name: str
    sensor_type: str
    value: float | None = None
    min_value: float | None = None
    max_value: float | None = None
