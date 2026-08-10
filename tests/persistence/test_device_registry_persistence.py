from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path
from threading import Barrier
import sqlite3

import pytest

from app.auth import (
    DeviceRegistry,
    DeviceRevokedError,
    DeviceStatus,
    InvalidDeviceTokenError,
    PairingAlreadyConsumedError,
    PairingNotFoundError,
    PairingService,
    PairingStatus,
    TokenService,
)
from app.persistence import Database, DeviceStore, SQLiteDeviceStore, StoredDevice


NOW = datetime(2026, 8, 10, 15, 0, tzinfo=timezone.utc)


def persistent_registry(data_dir: Path, *, clock=lambda: NOW) -> DeviceRegistry:
    database = Database(data_dir)
    database.initialize()
    return DeviceRegistry(store=SQLiteDeviceStore(database), clock=clock)


def pair_device(registry: DeviceRegistry, name: str) -> tuple[str, object]:
    pairing = PairingService(registry, clock=lambda: NOW)
    challenge = pairing.start_pairing(name)
    issued = pairing.complete_pairing(challenge.pairing_id, challenge.code)
    return issued.token, issued.device_id


def test_registry_loads_device_and_authenticates_after_restart(tmp_path: Path) -> None:
    first_instance = persistent_registry(tmp_path)
    token, device_id = pair_device(first_instance, "Restarted phone")

    second_instance = persistent_registry(tmp_path)

    identity = second_instance.authenticate(token)
    assert identity.id == device_id
    assert identity.name == "Restarted phone"
    assert identity.status is DeviceStatus.AUTHORIZED
    assert second_instance is not first_instance


def test_two_devices_survive_restart(tmp_path: Path) -> None:
    first_instance = persistent_registry(tmp_path)
    first_token, first_id = pair_device(first_instance, "Phone")
    second_token, second_id = pair_device(first_instance, "Tablet")

    restarted = persistent_registry(tmp_path)

    assert restarted.authenticate(first_token).id == first_id
    assert restarted.authenticate(second_token).id == second_id
    assert {device.id for device in restarted.list_devices()} == {
        first_id,
        second_id,
    }


def test_revocation_survives_restart_and_old_token_fails(tmp_path: Path) -> None:
    revoked_at = NOW + timedelta(hours=1)
    first_instance = persistent_registry(tmp_path, clock=lambda: revoked_at)
    token, device_id = pair_device(first_instance, "Revoked phone")

    revoked = first_instance.revoke(device_id)
    restarted = persistent_registry(tmp_path)

    assert revoked.revoked_at == revoked_at
    assert restarted.get(device_id).status is DeviceStatus.REVOKED
    assert restarted.get(device_id).revoked_at == revoked_at
    with pytest.raises(DeviceRevokedError):
        restarted.authenticate(token)


def test_pairing_token_plaintext_is_never_persisted(tmp_path: Path) -> None:
    registry = persistent_registry(tmp_path)
    token, _ = pair_device(registry, "Secure phone")

    database_bytes = Database(tmp_path).path.read_bytes()

    assert token.encode() not in database_bytes
    assert TokenService.hash_device_token(token).encode() in database_bytes


class FailingStore(DeviceStore):
    def __init__(self, records: tuple[StoredDevice, ...] = ()) -> None:
        self.records = records
        self.fail_save = False
        self.fail_revoke = False

    def load_devices(self) -> tuple[StoredDevice, ...]:
        return self.records

    def save_device(self, record: StoredDevice) -> None:
        if self.fail_save:
            raise RuntimeError("save failed")
        self.records += (record,)

    def revoke_device(self, device_id, revoked_at) -> None:
        if self.fail_revoke:
            raise RuntimeError("revoke failed")


def test_store_failure_does_not_register_device_only_in_memory() -> None:
    store = FailingStore()
    store.fail_save = True
    registry = DeviceRegistry(store=store)
    pairing = PairingService(registry, clock=lambda: NOW)
    challenge = pairing.start_pairing("Phone")

    with pytest.raises(RuntimeError, match="save failed"):
        pairing.complete_pairing(challenge.pairing_id, challenge.code)

    assert registry.list_devices() == ()
    assert pairing.get_session(challenge.pairing_id).status is PairingStatus.CONSUMED
    with pytest.raises(PairingAlreadyConsumedError):
        pairing.complete_pairing(challenge.pairing_id, challenge.code)


def test_revoke_failure_keeps_memory_authorized() -> None:
    store = FailingStore()
    registry = DeviceRegistry(store=store, clock=lambda: NOW + timedelta(hours=1))
    token, device_id = pair_device(registry, "Phone")
    store.fail_revoke = True

    with pytest.raises(RuntimeError, match="revoke failed"):
        registry.revoke(device_id)

    assert registry.get(device_id).status is DeviceStatus.AUTHORIZED
    assert registry.authenticate(token).id == device_id


def test_concurrent_authentication_after_restart(tmp_path: Path) -> None:
    token, device_id = pair_device(persistent_registry(tmp_path), "Concurrent phone")
    restarted = persistent_registry(tmp_path)
    workers = 12
    barrier = Barrier(workers)

    def authenticate() -> object:
        barrier.wait()
        return restarted.authenticate(token)

    with ThreadPoolExecutor(max_workers=workers) as executor:
        identities = list(executor.map(lambda _: authenticate(), range(workers)))

    assert all(identity.id == device_id for identity in identities)


def test_pending_pairing_is_memory_only_and_restart_cancels_it(
    tmp_path: Path,
) -> None:
    database = Database(tmp_path)
    database.initialize()
    first_registry = DeviceRegistry(store=SQLiteDeviceStore(database))
    first_pairing = PairingService(first_registry, clock=lambda: NOW)
    challenge = first_pairing.start_pairing("Pending phone")

    with database.connection() as connection:
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
        }
        device_count = connection.execute("SELECT COUNT(*) FROM devices").fetchone()[0]
    assert tables == {"actions", "devices"}
    assert device_count == 0
    assert challenge.code.encode() not in database.path.read_bytes()

    restarted_registry = DeviceRegistry(store=SQLiteDeviceStore(database))
    restarted_pairing = PairingService(restarted_registry, clock=lambda: NOW)

    with pytest.raises(PairingNotFoundError):
        restarted_pairing.get_session(challenge.pairing_id)
    with pytest.raises(PairingNotFoundError):
        restarted_pairing.complete_pairing(challenge.pairing_id, challenge.code)


def test_complete_pairing_commits_hash_before_returning_token(tmp_path: Path) -> None:
    database = Database(tmp_path)
    database.initialize()
    registry = DeviceRegistry(store=SQLiteDeviceStore(database))
    pairing = PairingService(registry, clock=lambda: NOW)
    challenge = pairing.start_pairing("Committed phone")

    issued = pairing.complete_pairing(challenge.pairing_id, challenge.code)

    expected_hash = TokenService.hash_device_token(issued.token)
    with database.connection() as connection:
        row = connection.execute(
            "SELECT device_id, token_hash FROM devices"
        ).fetchone()
    assert row["device_id"] == str(issued.device_id)
    assert row["token_hash"] == expected_hash
    assert issued.token.encode() not in database.path.read_bytes()
    assert persistent_registry(tmp_path).authenticate(issued.token).id == issued.device_id


def test_sqlite_failure_returns_no_token_and_leaves_no_partial_credential(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    database = Database(tmp_path)
    database.initialize()
    with database.connection() as connection:
        connection.execute("CREATE TABLE pairing_failure_audit (device_id TEXT)")
        connection.execute(
            """
            CREATE TRIGGER fail_pairing BEFORE INSERT ON devices BEGIN
                INSERT INTO pairing_failure_audit VALUES (NEW.device_id);
                SELECT RAISE(ABORT, 'pairing persistence failed');
            END
            """
        )
    registry = DeviceRegistry(store=SQLiteDeviceStore(database))
    pairing = PairingService(registry, clock=lambda: NOW)
    challenge = pairing.start_pairing("Failed phone")
    generated_token = "generated-but-never-issued-token"
    monkeypatch.setattr(
        TokenService,
        "generate_device_token",
        staticmethod(lambda: generated_token),
    )

    with pytest.raises(sqlite3.IntegrityError, match="pairing persistence failed"):
        pairing.complete_pairing(challenge.pairing_id, challenge.code)

    assert pairing.get_session(challenge.pairing_id).status is PairingStatus.CONSUMED
    assert registry.list_devices() == ()
    with pytest.raises(InvalidDeviceTokenError):
        registry.authenticate(generated_token)
    with database.connection() as connection:
        assert connection.execute("SELECT COUNT(*) FROM devices").fetchone()[0] == 0
        assert connection.execute(
            "SELECT COUNT(*) FROM pairing_failure_audit"
        ).fetchone()[0] == 0
    with pytest.raises(PairingAlreadyConsumedError):
        pairing.complete_pairing(challenge.pairing_id, challenge.code)


def test_concurrent_completion_persists_and_returns_exactly_one_token(
    tmp_path: Path,
) -> None:
    database = Database(tmp_path)
    database.initialize()
    registry = DeviceRegistry(store=SQLiteDeviceStore(database))
    pairing = PairingService(registry, clock=lambda: NOW)
    challenge = pairing.start_pairing("Raced phone")
    barrier = Barrier(2)

    def complete() -> object:
        barrier.wait()
        try:
            return pairing.complete_pairing(challenge.pairing_id, challenge.code)
        except PairingAlreadyConsumedError as exc:
            return exc

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(lambda _: complete(), range(2)))

    issued = [result for result in results if not isinstance(result, Exception)]
    rejected = [result for result in results if isinstance(result, Exception)]
    assert len(issued) == 1
    assert len(rejected) == 1
    assert isinstance(rejected[0], PairingAlreadyConsumedError)
    with database.connection() as connection:
        assert connection.execute("SELECT COUNT(*) FROM devices").fetchone()[0] == 1
    assert persistent_registry(tmp_path).authenticate(issued[0].token).id == issued[0].device_id
