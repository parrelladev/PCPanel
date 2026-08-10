from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
import sqlite3
from uuid import UUID, uuid4

import pytest

from app.auth.models import Device, DeviceStatus
from app.auth.tokens import TokenService
from app.persistence import (
    CorruptStoredDeviceError,
    Database,
    SQLiteDeviceStore,
    StoredDevice,
)


def make_store(tmp_path: Path) -> tuple[Database, SQLiteDeviceStore]:
    database = Database(tmp_path)
    database.initialize()
    return database, SQLiteDeviceStore(database)


def make_record(
    *,
    device_id: UUID | None = None,
    name: str = "Office panel",
    token_hash: str = "credential-hash",
) -> StoredDevice:
    created_at = datetime(2026, 8, 10, 12, 30, 15, 123456, tzinfo=timezone.utc)
    device = Device(
        id=device_id or uuid4(),
        name=name,
        status=DeviceStatus.AUTHORIZED,
        created_at=created_at,
        authorized_at=created_at + timedelta(seconds=5),
    )
    return StoredDevice(device=device, token_hash=token_hash)


def test_save_and_load_authorized_device_round_trip(tmp_path: Path) -> None:
    _, store = make_store(tmp_path)
    record = make_record(name="Painel da redação")

    store.save_device(record)

    assert store.load_devices() == (record,)
    loaded = store.load_devices()[0]
    assert loaded.device.id == record.device.id
    assert loaded.device.name == "Painel da redação"
    assert loaded.device.created_at == record.device.created_at
    assert loaded.device.authorized_at == record.device.authorized_at
    assert loaded.token_hash == record.token_hash
    assert loaded.device.created_at.utcoffset() == timedelta(0)


@pytest.mark.parametrize("name", ["Sala 1", "João — PC", "編集室パネル"])
def test_valid_names_survive_round_trip(tmp_path: Path, name: str) -> None:
    _, store = make_store(tmp_path)
    store.save_device(make_record(name=name))

    assert store.load_devices()[0].device.name == name


def test_plaintext_token_never_reaches_database(tmp_path: Path) -> None:
    database, store = make_store(tmp_path)
    plaintext = "secret-device-token-that-must-not-be-stored"
    token_hash = TokenService.hash_device_token(plaintext)

    store.save_device(make_record(token_hash=token_hash))

    with database.connection() as connection:
        stored_hash = connection.execute(
            "SELECT token_hash FROM devices"
        ).fetchone()[0]
    database_bytes = database.path.read_bytes()
    assert stored_hash == token_hash
    assert token_hash.encode() in database_bytes
    assert plaintext.encode() not in database_bytes


def test_revoke_persists_across_reload(tmp_path: Path) -> None:
    database, store = make_store(tmp_path)
    record = make_record()
    revoked_at = datetime(2026, 8, 11, 9, 45, tzinfo=timezone(timedelta(hours=-3)))
    store.save_device(record)

    store.revoke_device(record.device.id, revoked_at)

    loaded = SQLiteDeviceStore(database).load_devices()[0]
    assert loaded.device.status is DeviceStatus.REVOKED
    assert loaded.device.revoked_at == revoked_at
    assert loaded.device.revoked_at is not None
    assert loaded.device.revoked_at.utcoffset() == timedelta(0)
    assert loaded.token_hash == record.token_hash


def test_two_devices_are_persisted_separately(tmp_path: Path) -> None:
    _, store = make_store(tmp_path)
    first = make_record(name="First", token_hash="first-hash")
    second = make_record(name="Second", token_hash="second-hash")

    store.save_device(first)
    store.save_device(second)

    loaded = {record.device.id: record for record in store.load_devices()}
    assert loaded == {first.device.id: first, second.device.id: second}


def test_invalid_stored_status_fails_with_controlled_error(tmp_path: Path) -> None:
    database, store = make_store(tmp_path)
    record = make_record()
    store.save_device(record)
    with database.connection() as connection:
        connection.execute(
            "UPDATE devices SET status = 'unknown' WHERE device_id = ?",
            (str(record.device.id),),
        )

    with pytest.raises(CorruptStoredDeviceError, match="invalid data"):
        store.load_devices()


def test_failed_save_rolls_back_all_trigger_changes(tmp_path: Path) -> None:
    database, store = make_store(tmp_path)
    with database.connection() as connection:
        connection.execute("CREATE TABLE save_audit (device_id TEXT)")
        connection.execute(
            """
            CREATE TRIGGER reject_device BEFORE INSERT ON devices BEGIN
                INSERT INTO save_audit VALUES (NEW.device_id);
                SELECT RAISE(ABORT, 'rejected for test');
            END
            """
        )

    with pytest.raises(sqlite3.IntegrityError, match="rejected for test"):
        store.save_device(make_record())

    with database.connection() as connection:
        assert connection.execute("SELECT COUNT(*) FROM devices").fetchone()[0] == 0
        assert connection.execute("SELECT COUNT(*) FROM save_audit").fetchone()[0] == 0


def test_concurrent_saves_use_independent_connections(tmp_path: Path) -> None:
    _, store = make_store(tmp_path)
    records = [
        make_record(name=f"Device {index}", token_hash=f"hash-{index}")
        for index in range(12)
    ]

    with ThreadPoolExecutor(max_workers=4) as executor:
        list(executor.map(store.save_device, records))

    loaded = store.load_devices()
    assert len(loaded) == len(records)
    assert {record.device.id for record in loaded} == {
        record.device.id for record in records
    }


def test_timezone_naive_timestamp_is_rejected_before_write(tmp_path: Path) -> None:
    _, store = make_store(tmp_path)
    record = make_record()
    invalid = StoredDevice(
        device=replace(record.device, created_at=datetime(2026, 8, 10, 12, 0)),
        token_hash=record.token_hash,
    )

    with pytest.raises(ValueError, match="timezone-aware"):
        store.save_device(invalid)

    assert store.load_devices() == ()
