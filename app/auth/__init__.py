"""Pairing and device authorization domain."""

from app.auth.errors import (
    AuthenticationError,
    AuthError,
    DeviceNotFoundError,
    DeviceRevokedError,
    InvalidDeviceTokenError,
    PairingAlreadyConsumedError,
    PairingAttemptsExceededError,
    PairingCapacityError,
    PairingError,
    PairingExpiredError,
    PairingInvalidCodeError,
    PairingNotFoundError,
)
from app.auth.models import (
    DEVICE_NAME_MAX_LENGTH,
    AuthorizedDevice,
    Device,
    DeviceStatus,
    IssuedDeviceToken,
    PairingChallenge,
    PairingSession,
    PairingStatus,
)
from app.auth.tokens import DEVICE_TOKEN_BYTES, PAIRING_CODE_DIGITS, TokenService
from app.auth.registry import DeviceRegistry
from app.auth.pairing import (
    DEFAULT_MAX_PAIRING_ATTEMPTS,
    DEFAULT_MAX_PENDING_PAIRINGS,
    DEFAULT_PAIRING_TTL,
    PairingService,
)
from app.auth.presenter import ConsolePairingCodePresenter, PairingCodePresenter

__all__ = [
    "AuthenticationError",
    "AuthError",
    "AuthorizedDevice",
    "DEVICE_NAME_MAX_LENGTH",
    "DEVICE_TOKEN_BYTES",
    "Device",
    "DeviceNotFoundError",
    "DeviceRegistry",
    "DeviceRevokedError",
    "DeviceStatus",
    "ConsolePairingCodePresenter",
    "DEFAULT_MAX_PAIRING_ATTEMPTS",
    "DEFAULT_MAX_PENDING_PAIRINGS",
    "DEFAULT_PAIRING_TTL",
    "InvalidDeviceTokenError",
    "IssuedDeviceToken",
    "PairingAlreadyConsumedError",
    "PairingAttemptsExceededError",
    "PairingCapacityError",
    "PairingChallenge",
    "PairingError",
    "PairingExpiredError",
    "PairingInvalidCodeError",
    "PairingNotFoundError",
    "PairingSession",
    "PairingService",
    "PairingCodePresenter",
    "PairingStatus",
    "PAIRING_CODE_DIGITS",
    "TokenService",
]
