"""Thread-safe, in-memory storage for authorized devices and credentials."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
from threading import Lock
from typing import TYPE_CHECKING, Callable
from uuid import UUID

from app.auth.errors import (
    DeviceNotFoundError,
    DeviceRevokedError,
    InvalidDeviceTokenError,
)
from app.auth.models import AuthorizedDevice, Device, DeviceStatus
from app.auth.tokens import TokenService

if TYPE_CHECKING:
    from app.persistence.device_store import DeviceStore


class DeviceRegistry:
    """Process-local registry that retains hashes, never plaintext tokens."""

    def __init__(
        self,
        *,
        clock: Callable[[], datetime] | None = None,
        store: DeviceStore | None = None,
    ) -> None:
        self._devices_by_id: dict[UUID, Device] = {}
        self._credentials: dict[str, UUID] = {}
        self._lock = Lock()
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._store = store
        if store is not None:
            self._load_from_store(store)

    def _load_from_store(self, store: DeviceStore) -> None:
        for record in store.load_devices():
            device = record.device
            if device.id in self._devices_by_id:
                raise ValueError(f"duplicate persisted device id: {device.id}")
            if record.token_hash in self._credentials:
                raise ValueError("duplicate persisted device credential hash")
            self._devices_by_id[device.id] = device
            self._credentials[record.token_hash] = device.id

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
            if self._store is not None:
                from app.persistence.device_store import StoredDevice

                self._store.save_device(
                    StoredDevice(device=device, token_hash=token_hash)
                )
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
            if self._store is not None:
                self._store.revoke_device(device_id, revoked.revoked_at)
            self._devices_by_id[device_id] = revoked
            return revoked

    def list_devices(self) -> tuple[Device, ...]:
        """Return a stable immutable snapshot of registered devices."""
        with self._lock:
            return tuple(self._devices_by_id.values())
