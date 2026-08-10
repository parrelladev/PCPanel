from uuid import uuid4

import pytest

from app.auth import (
    AuthenticationError,
    AuthError,
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


@pytest.mark.parametrize(
    "error_type",
    [
        PairingNotFoundError,
        PairingExpiredError,
        PairingInvalidCodeError,
        PairingAttemptsExceededError,
        PairingAlreadyConsumedError,
    ],
)
def test_pairing_errors_preserve_only_pairing_identity(error_type: type[PairingError]) -> None:
    pairing_id = uuid4()
    error = error_type(pairing_id)

    assert isinstance(error, AuthError)
    assert error.pairing_id == pairing_id


def test_capacity_error_does_not_require_a_pairing_identity() -> None:
    error = PairingCapacityError()

    assert isinstance(error, PairingError)
    assert error.pairing_id is None


def test_invalid_token_error_does_not_retain_the_token() -> None:
    error = InvalidDeviceTokenError()

    assert isinstance(error, AuthenticationError)
    assert vars(error) == {}


def test_revoked_error_preserves_device_identity() -> None:
    device_id = uuid4()
    error = DeviceRevokedError(device_id)

    assert isinstance(error, AuthenticationError)
    assert error.device_id == device_id
