from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID

from app.auth.models import Device


@dataclass(slots=True, frozen=True)
class StoredDevice:
    """Persistence record combining a domain device with its credential hash."""

    device: Device
    token_hash: str

    def __post_init__(self) -> None:
        if not isinstance(self.device, Device):
            raise TypeError("device must be a Device")
        if not isinstance(self.token_hash, str) or not self.token_hash:
            raise ValueError("token_hash must be a non-empty string")


class DeviceStore(Protocol):
    """Storage boundary for durable devices and hashed credentials."""

    def load_devices(self) -> tuple[StoredDevice, ...]: ...

    def save_device(self, record: StoredDevice) -> None: ...

    def revoke_device(self, device_id: UUID, revoked_at: datetime) -> None: ...
