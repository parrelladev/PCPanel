"""Thread-safe, in-memory storage for authorized devices and credentials."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
from threading import Lock
from typing import Callable
from uuid import UUID

from app.auth.errors import (
    DeviceNotFoundError,
    DeviceRevokedError,
    InvalidDeviceTokenError,
)
from app.auth.models import AuthorizedDevice, Device, DeviceStatus
from app.auth.tokens import TokenService


class DeviceRegistry:
    """Process-local registry that retains hashes, never plaintext tokens."""

    def __init__(
        self,
        *,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._devices_by_id: dict[UUID, Device] = {}
        self._credentials: dict[str, UUID] = {}
        self._lock = Lock()
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def register(self, device: Device, token: str) -> None:
        """Atomically register an authorized device and its token hash."""
        if device.status is not DeviceStatus.AUTHORIZED:
            raise ValueError("only authorized devices can be registered")
        token_hash = TokenService.hash_device_token(token)

        with self._lock:
            if device.id in self._devices_by_id:
                raise ValueError(f"device {device.id} is already registered")
            if token_hash in self._credentials:
                raise ValueError("device credential is already registered")
            self._devices_by_id[device.id] = device
            self._credentials[token_hash] = device.id

    def get(self, device_id: UUID) -> Device:
        """Return an immutable device, or raise DeviceNotFoundError."""
        with self._lock:
            device = self._devices_by_id.get(device_id)
            if device is None:
                raise DeviceNotFoundError(device_id)
            return device

    def authenticate(self, token: str) -> AuthorizedDevice:
        """Resolve a bearer token to a sanitized authorized identity."""
        token_hash = TokenService.hash_device_token(token)

        with self._lock:
            device_id = self._credentials.get(token_hash)
            if device_id is None:
                raise InvalidDeviceTokenError()
            device = self._devices_by_id[device_id]
            if device.status is DeviceStatus.REVOKED:
                raise DeviceRevokedError(device.id)
            return AuthorizedDevice(
                id=device.id,
                name=device.name,
                status=device.status,
            )

    def revoke(self, device_id: UUID) -> Device:
        """Atomically revoke a device; repeated revocation is idempotent."""
        with self._lock:
            device = self._devices_by_id.get(device_id)
            if device is None:
                raise DeviceNotFoundError(device_id)
            if device.status is DeviceStatus.REVOKED:
                return device

            revoked = replace(
                device,
                status=DeviceStatus.REVOKED,
                revoked_at=self._clock(),
            )
            self._devices_by_id[device_id] = revoked
            return revoked

    def list_devices(self) -> tuple[Device, ...]:
        """Return a stable immutable snapshot of registered devices."""
        with self._lock:
            return tuple(self._devices_by_id.values())

