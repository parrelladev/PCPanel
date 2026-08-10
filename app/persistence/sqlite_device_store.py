from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from uuid import UUID

from app.auth.models import Device, DeviceStatus
from app.persistence.database import Database
from app.persistence.device_store import StoredDevice


class DevicePersistenceError(RuntimeError):
    """Base error for durable device data."""


class CorruptStoredDeviceError(DevicePersistenceError):
    """Raised when a stored row cannot reconstruct a valid Device."""


class StoredDeviceNotFoundError(DevicePersistenceError):
    """Raised when a persisted device cannot be found."""


class SQLiteDeviceStore:
    """Persist devices using one short-lived SQLite connection per operation."""

    def __init__(self, database: Database) -> None:
        self._database = database

    def load_devices(self) -> tuple[StoredDevice, ...]:
        with self._database.connection() as connection:
            rows = connection.execute(
                """
                SELECT device_id, name, status, created_at, authorized_at,
                       revoked_at, token_hash
                FROM devices
                ORDER BY created_at, device_id
                """
            ).fetchall()
        return tuple(self._decode_row(row) for row in rows)

    def save_device(self, record: StoredDevice) -> None:
        device = record.device
        values = (
            str(device.id),
            device.name,
            device.status.value,
            self._encode_datetime(device.created_at),
            self._encode_datetime(device.authorized_at),
            self._encode_datetime(device.revoked_at) if device.revoked_at else None,
            record.token_hash,
        )
        with self._database.connection() as connection:
            connection.execute(
                """
                INSERT INTO devices (
                    device_id, name, status, created_at, authorized_at,
                    revoked_at, token_hash
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(device_id) DO UPDATE SET
                    name = excluded.name,
                    status = excluded.status,
                    created_at = excluded.created_at,
                    authorized_at = excluded.authorized_at,
                    revoked_at = excluded.revoked_at,
                    token_hash = excluded.token_hash
                """,
                values,
            )

    def revoke_device(self, device_id: UUID, revoked_at: datetime) -> None:
        revoked_at_value = self._encode_datetime(revoked_at)
        with self._database.connection() as connection:
            cursor = connection.execute(
                """
                UPDATE devices
                SET status = ?, revoked_at = ?
                WHERE device_id = ?
                """,
                (DeviceStatus.REVOKED.value, revoked_at_value, str(device_id)),
            )
            if cursor.rowcount != 1:
                raise StoredDeviceNotFoundError(
                    f"persisted device {device_id} was not found"
                )

    @staticmethod
    def _encode_datetime(value: datetime) -> str:
        if not isinstance(value, datetime) or value.utcoffset() is None:
            raise ValueError("persisted device timestamps must be timezone-aware")
        return value.astimezone(timezone.utc).isoformat()

    @classmethod
    def _decode_datetime(cls, value: object, field: str) -> datetime:
        if not isinstance(value, str):
            raise ValueError(f"{field} is not an ISO 8601 string")
        parsed = datetime.fromisoformat(value)
        if parsed.utcoffset() is None:
            raise ValueError(f"{field} is not timezone-aware")
        return parsed.astimezone(timezone.utc)

    @classmethod
    def _decode_row(cls, row: sqlite3.Row) -> StoredDevice:
        device_id = row["device_id"]
        try:
            status = DeviceStatus(row["status"])
            revoked_at = (
                cls._decode_datetime(row["revoked_at"], "revoked_at")
                if row["revoked_at"] is not None
                else None
            )
            device = Device(
                id=UUID(device_id),
                name=row["name"],
                status=status,
                created_at=cls._decode_datetime(row["created_at"], "created_at"),
                authorized_at=cls._decode_datetime(
                    row["authorized_at"], "authorized_at"
                ),
                revoked_at=revoked_at,
            )
            return StoredDevice(device=device, token_hash=row["token_hash"])
        except (TypeError, ValueError) as exc:
            raise CorruptStoredDeviceError(
                f"persisted device {device_id!r} contains invalid data: {exc}"
            ) from exc
