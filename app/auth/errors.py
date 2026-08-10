"""Framework-independent errors for pairing and device authentication."""

from __future__ import annotations

from uuid import UUID


class AuthError(Exception):
    """Base error for the Auth domain."""


class DeviceNotFoundError(AuthError):
    """Raised when a device identifier is not registered."""

    def __init__(self, device_id: UUID) -> None:
        self.device_id = device_id
        super().__init__(f"device {device_id} was not found")


class PairingError(AuthError):
    """Base error for a pairing operation."""

    def __init__(self, pairing_id: UUID | None, message: str) -> None:
        self.pairing_id = pairing_id
        super().__init__(message)


class PairingNotFoundError(PairingError):
    def __init__(self, pairing_id: UUID) -> None:
        super().__init__(pairing_id, f"pairing {pairing_id} was not found")


class PairingExpiredError(PairingError):
    def __init__(self, pairing_id: UUID) -> None:
        super().__init__(pairing_id, f"pairing {pairing_id} has expired")


class PairingInvalidCodeError(PairingError):
    def __init__(self, pairing_id: UUID) -> None:
        super().__init__(pairing_id, f"the code for pairing {pairing_id} is invalid")


class PairingAttemptsExceededError(PairingError):
    def __init__(self, pairing_id: UUID) -> None:
        super().__init__(pairing_id, f"pairing {pairing_id} has no attempts remaining")


class PairingAlreadyConsumedError(PairingError):
    def __init__(self, pairing_id: UUID) -> None:
        super().__init__(pairing_id, f"pairing {pairing_id} was already consumed")


class PairingCapacityError(PairingError):
    """Raised when no additional pending pairing can be accepted."""

    def __init__(self) -> None:
        super().__init__(None, "pairing capacity has been reached")


class AuthenticationError(AuthError):
    """Base error for device authentication."""


class InvalidDeviceTokenError(AuthenticationError):
    def __init__(self) -> None:
        super().__init__("device token is invalid")


class DeviceRevokedError(AuthenticationError):
    def __init__(self, device_id: UUID) -> None:
        self.device_id = device_id
        super().__init__(f"device {device_id} is revoked")
