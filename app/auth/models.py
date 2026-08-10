from __future__ import annotations

import unicodedata
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from uuid import UUID


DEVICE_NAME_MAX_LENGTH = 100


def _validated_device_name(value: str) -> str:
    if not isinstance(value, str):
        raise TypeError("device name must be a string")
    if any(unicodedata.category(character) == "Cc" for character in value):
        raise ValueError("device name must not contain control characters")

    normalized = value.strip()
    if not normalized:
        raise ValueError("device name must not be empty")
    if len(normalized) > DEVICE_NAME_MAX_LENGTH:
        raise ValueError(
            f"device name must not exceed {DEVICE_NAME_MAX_LENGTH} characters"
        )
    return normalized


class DeviceStatus(str, Enum):
    AUTHORIZED = "authorized"
    REVOKED = "revoked"


class PairingStatus(str, Enum):
    PENDING = "pending"
    CONSUMED = "consumed"
    LOCKED = "locked"


@dataclass(slots=True, frozen=True)
class Device:
    """A device whose pairing was completed successfully."""

    id: UUID
    name: str
    status: DeviceStatus
    created_at: datetime
    authorized_at: datetime
    revoked_at: datetime | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "name", _validated_device_name(self.name))
        if self.status is DeviceStatus.AUTHORIZED and self.revoked_at is not None:
            raise ValueError("an authorized device cannot have a revocation time")
        if self.status is DeviceStatus.REVOKED and self.revoked_at is None:
            raise ValueError("a revoked device must have a revocation time")


@dataclass(slots=True, frozen=True)
class PairingSession:
    """Temporary pairing state; it deliberately never contains the plain code."""

    pairing_id: UUID
    device_name: str
    code_hash: str
    created_at: datetime
    expires_at: datetime
    attempts_remaining: int
    status: PairingStatus = PairingStatus.PENDING

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "device_name",
            _validated_device_name(self.device_name),
        )
        if not self.code_hash:
            raise ValueError("code hash must not be empty")
        if self.expires_at <= self.created_at:
            raise ValueError("pairing expiration must be after creation")
        if self.attempts_remaining < 0:
            raise ValueError("pairing attempts remaining must not be negative")
        if self.status is PairingStatus.PENDING and self.attempts_remaining == 0:
            raise ValueError("a pending pairing must have at least one attempt")
        if self.status is PairingStatus.LOCKED and self.attempts_remaining != 0:
            raise ValueError("a locked pairing must have no attempts remaining")

    def is_expired(self, at: datetime) -> bool:
        return at >= self.expires_at


@dataclass(slots=True, frozen=True)
class PairingChallenge:
    """Transient plain pairing code intended only for a trusted presenter."""

    pairing_id: UUID
    code: str
    expires_at: datetime


@dataclass(slots=True, frozen=True)
class IssuedDeviceToken:
    """A newly issued credential that must not be retained as server state."""

    device_id: UUID
    token: str


@dataclass(slots=True, frozen=True)
class AuthorizedDevice:
    """Sanitized authenticated identity safe to pass to authorization code."""

    id: UUID
    name: str
    status: DeviceStatus

    def __post_init__(self) -> None:
        object.__setattr__(self, "name", _validated_device_name(self.name))

