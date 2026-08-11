from __future__ import annotations

from datetime import datetime, timezone

import pytest

from app.ipc.protocol import (
    Command,
    IPCProtocolError,
    PROTOCOL_VERSION,
    command_message,
    decode_message,
    encode_message,
    snapshot_from_message,
    snapshot_message,
)
from app.telemetry.models import SensorReading, TelemetrySnapshot


def sample_snapshot() -> TelemetrySnapshot:
    return TelemetrySnapshot(
        sequence=27,
        captured_at=datetime(2026, 8, 10, 18, 30, tzinfo=timezone.utc),
        sensors=(
            SensorReading(
                hardware_identifier="/cpu/0",
                hardware_name="CPU",
                hardware_type="Cpu",
                sensor_identifier="/cpu/0/load/0",
                sensor_name="CPU Total",
                sensor_type="Load",
                value=31.5,
                min_value=0.0,
                max_value=100.0,
            ),
        ),
    )


def test_snapshot_json_round_trip_preserves_raw_model() -> None:
    original = sample_snapshot()
    decoded = decode_message(encode_message(snapshot_message(original)))

    assert snapshot_from_message(decoded) == original


def test_protocol_version_is_required_and_incompatible_version_is_rejected() -> None:
    assert command_message(Command.GET_STATUS)["protocol_version"] == PROTOCOL_VERSION
    with pytest.raises(IPCProtocolError, match="version"):
        decode_message(encode_message({"protocol_version": 999}))


@pytest.mark.parametrize("frame", [b"", b"\x02\x00\x00\x00{}", b"\x01\x00\x00\x00{"])
def test_invalid_message_is_rejected(frame: bytes) -> None:
    with pytest.raises(IPCProtocolError):
        decode_message(frame)


def test_protocol_exposes_only_two_read_only_commands() -> None:
    assert {command.value for command in Command} == {
        "GET_LATEST_SNAPSHOT",
        "GET_STATUS",
    }
    serialized = " ".join(command.value for command in Command).lower()
    assert "execute" not in serialized
    assert "shell" not in serialized
