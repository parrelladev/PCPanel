from dataclasses import FrozenInstanceError, fields
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from app.auth import (
    DEVICE_NAME_MAX_LENGTH,
    AuthorizedDevice,
    Device,
    DeviceStatus,
    IssuedDeviceToken,
    PairingChallenge,
    PairingSession,
    PairingStatus,
)


NOW = datetime(2026, 8, 10, 12, 0, tzinfo=timezone.utc)


def device(name: str = "Galaxy S24", **changes: object) -> Device:
    values = {
        "id": uuid4(),
        "name": name,
        "status": DeviceStatus.AUTHORIZED,
        "created_at": NOW,
        "authorized_at": NOW + timedelta(seconds=1),
        "revoked_at": None,
    }
    values.update(changes)
    return Device(**values)  # type: ignore[arg-type]


def pairing(name: str = "Tablet da sala", **changes: object) -> PairingSession:
    values = {
        "pairing_id": uuid4(),
        "device_name": name,
        "code_hash": "a-secure-derived-value",
        "created_at": NOW,
        "expires_at": NOW + timedelta(minutes=5),
        "attempts_remaining": 5,
        "status": PairingStatus.PENDING,
    }
    values.update(changes)
    return PairingSession(**values)  # type: ignore[arg-type]


def test_creates_authorized_device() -> None:
    created = device()

    assert created.name == "Galaxy S24"
    assert created.status is DeviceStatus.AUTHORIZED
    assert created.authorized_at is not None
    assert created.revoked_at is None


def test_creates_revoked_device() -> None:
    revoked_at = NOW + timedelta(days=1)
    created = device(status=DeviceStatus.REVOKED, revoked_at=revoked_at)

    assert created.status is DeviceStatus.REVOKED
    assert created.revoked_at == revoked_at


def test_device_status_and_timestamps_cannot_conflict() -> None:
    with pytest.raises(ValueError, match="authorized device"):
        device(revoked_at=NOW)

    with pytest.raises(ValueError, match="revoked device"):
        device(status=DeviceStatus.REVOKED)


def test_pairing_session_is_pending_and_expiration_is_derived() -> None:
    session = pairing()

    assert session.status is PairingStatus.PENDING
    assert session.attempts_remaining == 5
    assert not session.is_expired(session.expires_at - timedelta(microseconds=1))
    assert session.is_expired(session.expires_at)


def test_pairing_challenge_contains_transient_plain_code() -> None:
    challenge = PairingChallenge(
        pairing_id=uuid4(),
        code="582104",
        expires_at=NOW + timedelta(minutes=5),
    )

    assert challenge.code == "582104"


def test_pairing_session_has_no_plain_code_field() -> None:
    assert "code" not in {field.name for field in fields(PairingSession)}


def test_issued_token_represents_plaintext_only_at_issuance() -> None:
    issued = IssuedDeviceToken(device_id=uuid4(), token="new-secret")

    assert issued.token == "new-secret"


def test_authorized_device_exposes_no_credentials() -> None:
    identity = AuthorizedDevice(
        id=uuid4(),
        name="iPhone",
        status=DeviceStatus.AUTHORIZED,
    )

    assert {field.name for field in fields(identity)} == {"id", "name", "status"}


@pytest.mark.parametrize("name", ["Galaxy S24", "iPhone", "Tablet da sala"])
def test_accepts_valid_device_names(name: str) -> None:
    assert device(name).name == name


def test_trims_external_whitespace() -> None:
    assert device("  iPhone  ").name == "iPhone"
    assert pairing("  Tablet da sala  ").device_name == "Tablet da sala"


@pytest.mark.parametrize("name", ["", " ", "\u00a0"])
def test_rejects_empty_device_name(name: str) -> None:
    with pytest.raises(ValueError, match="must not be empty"):
        device(name)


def test_rejects_excessive_device_name_length() -> None:
    with pytest.raises(ValueError, match=str(DEVICE_NAME_MAX_LENGTH)):
        device("x" * (DEVICE_NAME_MAX_LENGTH + 1))


@pytest.mark.parametrize(
    "name",
    [
        "phone\nname",
        "phone\rname",
        "phone\tname",
        "phone\0name",
        "phone\x1fname",
        "phone\u0085name",
    ],
)
def test_rejects_control_characters(name: str) -> None:
    with pytest.raises(ValueError, match="control characters"):
        device(name)


def test_rejects_control_characters_even_at_external_edges() -> None:
    with pytest.raises(ValueError, match="control characters"):
        device("iPhone\n")


def test_duplicate_names_are_allowed() -> None:
    first = device("iPhone")
    second = device("iPhone")

    assert first.name == second.name
    assert first.id != second.id


def test_models_are_immutable() -> None:
    created = device()

    with pytest.raises(FrozenInstanceError):
        created.name = "changed"  # type: ignore[misc]

