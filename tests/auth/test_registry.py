from concurrent.futures import ThreadPoolExecutor
from dataclasses import fields
from datetime import datetime, timedelta, timezone
from threading import Barrier
from uuid import uuid4

import pytest

from app.auth import (
    AuthorizedDevice,
    Device,
    DeviceNotFoundError,
    DeviceRegistry,
    DeviceRevokedError,
    DeviceStatus,
    InvalidDeviceTokenError,
    TokenService,
)


NOW = datetime(2026, 8, 10, 15, 0, tzinfo=timezone.utc)


def authorized_device(name: str = "Phone") -> Device:
    return Device(
        id=uuid4(),
        name=name,
        status=DeviceStatus.AUTHORIZED,
        created_at=NOW,
        authorized_at=NOW + timedelta(seconds=1),
    )


def test_registry_starts_empty() -> None:
    assert DeviceRegistry().list_devices() == ()


def test_registers_and_gets_device_by_id() -> None:
    registry = DeviceRegistry()
    device = authorized_device()

    registry.register(device, TokenService.generate_device_token())

    assert registry.get(device.id) == device


def test_get_unknown_device_has_explicit_error() -> None:
    device_id = uuid4()

    with pytest.raises(DeviceNotFoundError) as raised:
        DeviceRegistry().get(device_id)

    assert raised.value.device_id == device_id


def test_correct_token_authenticates_to_sanitized_identity() -> None:
    registry = DeviceRegistry()
    device = authorized_device("Galaxy S24")
    token = TokenService.generate_device_token()
    registry.register(device, token)

    identity = registry.authenticate(token)

    assert identity == AuthorizedDevice(
        id=device.id,
        name=device.name,
        status=DeviceStatus.AUTHORIZED,
    )
    assert {field.name for field in fields(identity)} == {"id", "name", "status"}


def test_incorrect_token_fails() -> None:
    registry = DeviceRegistry()
    registry.register(authorized_device(), TokenService.generate_device_token())

    with pytest.raises(InvalidDeviceTokenError):
        registry.authenticate(TokenService.generate_device_token())


def test_registry_never_retains_plaintext_token() -> None:
    registry = DeviceRegistry()
    token = TokenService.generate_device_token()
    device = authorized_device()

    registry.register(device, token)

    assert token not in repr(registry.__dict__)
    assert TokenService.hash_device_token(token) in repr(registry.__dict__)
    assert "token_hash" not in {field.name for field in fields(registry.get(device.id))}


def test_devices_have_independent_credentials() -> None:
    registry = DeviceRegistry()
    first = authorized_device("Phone")
    second = authorized_device("Phone")
    first_token = TokenService.generate_device_token()
    second_token = TokenService.generate_device_token()
    registry.register(first, first_token)
    registry.register(second, second_token)

    assert registry.authenticate(first_token).id == first.id
    assert registry.authenticate(second_token).id == second.id


def test_revoke_changes_state_and_prevents_authentication() -> None:
    revoked_at = NOW + timedelta(hours=1)
    registry = DeviceRegistry(clock=lambda: revoked_at)
    device = authorized_device()
    token = TokenService.generate_device_token()
    registry.register(device, token)

    revoked = registry.revoke(device.id)

    assert revoked.status is DeviceStatus.REVOKED
    assert revoked.revoked_at == revoked_at
    assert registry.get(device.id) == revoked
    with pytest.raises(DeviceRevokedError) as raised:
        registry.authenticate(token)
    assert raised.value.device_id == device.id


def test_concurrent_authentication_is_consistent() -> None:
    workers = 12
    barrier = Barrier(workers)
    registry = DeviceRegistry()
    device = authorized_device()
    token = TokenService.generate_device_token()
    registry.register(device, token)

    def authenticate() -> object:
        barrier.wait()
        return registry.authenticate(token)

    with ThreadPoolExecutor(max_workers=workers) as executor:
        identities = list(executor.map(lambda _: authenticate(), range(workers)))

    assert all(identity.id == device.id for identity in identities)


def test_concurrent_registration_does_not_corrupt_registry() -> None:
    workers = 12
    barrier = Barrier(workers)
    registry = DeviceRegistry()
    registrations = [
        (authorized_device(f"Phone {index}"), TokenService.generate_device_token())
        for index in range(workers)
    ]

    def register(item: tuple[Device, str]) -> None:
        barrier.wait()
        registry.register(*item)

    with ThreadPoolExecutor(max_workers=workers) as executor:
        list(executor.map(register, registrations))

    assert {device.id for device in registry.list_devices()} == {
        device.id for device, _ in registrations
    }
    for device, token in registrations:
        assert registry.authenticate(token).id == device.id


def test_concurrent_revoke_is_idempotent_and_thread_safe() -> None:
    workers = 12
    barrier = Barrier(workers)
    revoked_at = NOW + timedelta(hours=2)
    registry = DeviceRegistry(clock=lambda: revoked_at)
    device = authorized_device()
    registry.register(device, TokenService.generate_device_token())

    def revoke() -> Device:
        barrier.wait()
        return registry.revoke(device.id)

    with ThreadPoolExecutor(max_workers=workers) as executor:
        results = list(executor.map(lambda _: revoke(), range(workers)))

    assert all(result == results[0] for result in results)
    assert results[0].status is DeviceStatus.REVOKED
    assert results[0].revoked_at == revoked_at


def test_listing_returns_an_immutable_snapshot() -> None:
    registry = DeviceRegistry()
    first = authorized_device()
    registry.register(first, TokenService.generate_device_token())

    snapshot = registry.list_devices()
    registry.register(authorized_device(), TokenService.generate_device_token())

    assert isinstance(snapshot, tuple)
    assert snapshot == (first,)

