from __future__ import annotations

import inspect
from datetime import datetime, timezone
from pathlib import Path
from typing import get_type_hints
from uuid import UUID, uuid4

import pytest

from app.auth.models import Device, DeviceStatus
from app.persistence.device_store import DeviceStore, StoredDevice


def authorized_device() -> Device:
    now = datetime.now(timezone.utc)
    return Device(
        id=uuid4(),
        name="Office panel",
        status=DeviceStatus.AUTHORIZED,
        created_at=now,
        authorized_at=now,
    )


def test_stored_device_keeps_hash_separate_from_domain_device() -> None:
    device = authorized_device()

    record = StoredDevice(device=device, token_hash="hashed-credential")

    assert record.device is device
    assert record.token_hash == "hashed-credential"
    assert not hasattr(record.device, "token_hash")
    assert not hasattr(record.device, "token")


def test_stored_device_requires_non_empty_hash() -> None:
    with pytest.raises(ValueError, match="token_hash must be a non-empty string"):
        StoredDevice(device=authorized_device(), token_hash="")


def test_contract_exposes_only_python_and_domain_friendly_types() -> None:
    load_types = get_type_hints(DeviceStore.load_devices)
    save_types = get_type_hints(DeviceStore.save_device)
    revoke_types = get_type_hints(DeviceStore.revoke_device)

    assert load_types["return"] == tuple[StoredDevice, ...]
    assert save_types == {"record": StoredDevice, "return": type(None)}
    assert revoke_types == {
        "device_id": UUID,
        "revoked_at": datetime,
        "return": type(None),
    }


def test_contract_does_not_expose_sqlite_types_or_plaintext_token() -> None:
    source = Path(inspect.getfile(DeviceStore)).read_text(encoding="utf-8")
    signatures = " ".join(
        str(inspect.signature(method))
        for method in (
            DeviceStore.load_devices,
            DeviceStore.save_device,
            DeviceStore.revoke_device,
        )
    )

    assert "sqlite3" not in source
    assert "Connection" not in signatures
    assert "Cursor" not in signatures
    assert "Row" not in signatures
    assert "token: str" not in signatures
    assert "plaintext" not in signatures.lower()


def test_plain_python_store_can_satisfy_protocol_shape() -> None:
    class MemoryDeviceStore:
        def __init__(self) -> None:
            self.records: list[StoredDevice] = []

        def load_devices(self) -> tuple[StoredDevice, ...]:
            return tuple(self.records)

        def save_device(self, record: StoredDevice) -> None:
            self.records.append(record)

        def revoke_device(self, device_id: UUID, revoked_at: datetime) -> None:
            return None

    store: DeviceStore = MemoryDeviceStore()
    record = StoredDevice(authorized_device(), "hash")

    store.save_device(record)

    assert store.load_devices() == (record,)
