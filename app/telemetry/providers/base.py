from __future__ import annotations

from abc import ABC, abstractmethod
from types import TracebackType
from typing import Self

from ..models import SensorReading


class TelemetryProvider(ABC):
    """Abstract contract for hardware telemetry providers."""

    @abstractmethod
    def open(self) -> None:
        """Initialize the provider and acquire any required resources."""

    @abstractmethod
    def close(self) -> None:
        """Release resources held by the provider."""

    @abstractmethod
    def update(self) -> None:
        """Refresh the provider's internal telemetry state."""

    @abstractmethod
    def get_sensors(self) -> list[SensorReading]:
        """Return the sensor readings from the provider's current state."""

    def __enter__(self) -> Self:
        self.open()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.close()
