from __future__ import annotations

import json
import struct
from datetime import datetime
from enum import Enum
from typing import Any

from ..telemetry.models import SensorReading, TelemetrySnapshot


PROTOCOL_VERSION = 1
PIPE_NAME = r"\\.\pipe\PCPanelTelemetry"
MAX_MESSAGE_BYTES = 4 * 1024 * 1024


class Command(str, Enum):
    GET_LATEST_SNAPSHOT = "GET_LATEST_SNAPSHOT"
    GET_STATUS = "GET_STATUS"


class ResponseType(str, Enum):
    SNAPSHOT = "SNAPSHOT"
    SERVICE_STATUS = "SERVICE_STATUS"
    ERROR = "ERROR"


class IPCError(RuntimeError):
    """Base error raised at the telemetry IPC boundary."""


class IPCUnavailableError(IPCError):
    pass


class IPCTimeoutError(IPCError):
    pass


class IPCProtocolError(IPCError):
    pass


class IPCWin32Error(IPCUnavailableError):
    """A named Win32 operation failed with a native error code."""

    def __init__(self, operation: str, winerror: int) -> None:
        self.operation = operation
        self.winerror = winerror
        super().__init__(f"{operation} failed with Win32 error {winerror}")


def encode_message(message: dict[str, Any]) -> bytes:
    body = json.dumps(message, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    if len(body) > MAX_MESSAGE_BYTES:
        raise IPCProtocolError("IPC message exceeds maximum size")
    return struct.pack("<I", len(body)) + body


def decode_message(frame: bytes) -> dict[str, Any]:
    if len(frame) < 4:
        raise IPCProtocolError("IPC frame is truncated")
    (size,) = struct.unpack("<I", frame[:4])
    body = frame[4:]
    if size > MAX_MESSAGE_BYTES or size != len(body):
        raise IPCProtocolError("IPC frame length is invalid")
    try:
        value = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise IPCProtocolError("IPC payload is not valid JSON") from exc
    if not isinstance(value, dict):
        raise IPCProtocolError("IPC payload must be an object")
    if value.get("protocol_version") != PROTOCOL_VERSION:
        raise IPCProtocolError("IPC protocol version is incompatible")
    return value


def command_message(command: Command) -> dict[str, Any]:
    return {"protocol_version": PROTOCOL_VERSION, "command": command.value}


def snapshot_message(snapshot: TelemetrySnapshot | None) -> dict[str, Any]:
    return {
        "protocol_version": PROTOCOL_VERSION,
        "type": ResponseType.SNAPSHOT.value,
        "snapshot": None if snapshot is None else {
            "sequence": snapshot.sequence,
            "captured_at": snapshot.captured_at.isoformat(),
            "sensors": [
                {
                    "hardware_identifier": sensor.hardware_identifier,
                    "hardware_name": sensor.hardware_name,
                    "hardware_type": sensor.hardware_type,
                    "sensor_identifier": sensor.sensor_identifier,
                    "sensor_name": sensor.sensor_name,
                    "sensor_type": sensor.sensor_type,
                    "value": sensor.value,
                    "min_value": sensor.min_value,
                    "max_value": sensor.max_value,
                }
                for sensor in snapshot.sensors
            ],
        },
    }


def snapshot_from_message(message: dict[str, Any]) -> TelemetrySnapshot | None:
    if message.get("type") == ResponseType.ERROR.value:
        raise IPCProtocolError(str(message.get("error", "Telemetry service error")))
    if message.get("type") != ResponseType.SNAPSHOT.value:
        raise IPCProtocolError("Unexpected IPC response type")
    payload = message.get("snapshot")
    if payload is None:
        return None
    if not isinstance(payload, dict) or not isinstance(payload.get("sensors"), list):
        raise IPCProtocolError("Snapshot payload is invalid")
    try:
        return TelemetrySnapshot(
            sequence=int(payload["sequence"]),
            captured_at=datetime.fromisoformat(payload["captured_at"]),
            sensors=tuple(SensorReading(**sensor) for sensor in payload["sensors"]),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise IPCProtocolError("Snapshot payload is invalid") from exc


def error_message(error: str) -> dict[str, Any]:
    return {
        "protocol_version": PROTOCOL_VERSION,
        "type": ResponseType.ERROR.value,
        "error": error,
    }
