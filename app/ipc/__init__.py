"""Local, read-only telemetry IPC for the Windows service boundary."""

from .client import TelemetryPipeClient
from .server import TelemetryPipeServer

__all__ = ["TelemetryPipeClient", "TelemetryPipeServer"]
