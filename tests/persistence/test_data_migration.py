from __future__ import annotations

import hashlib
import shutil
import sqlite3
from datetime import datetime, timezone
from uuid import uuid4

import pytest

from app.persistence.data_migration import migrate_database
from app.persistence.database import Database
from app.auth.models import Device, DeviceStatus
from app.auth.registry import DeviceRegistry
from app.persistence.sqlite_device_store import SQLiteDeviceStore


def create_populated_database(directory) -> Database:
    database = Database(directory)
    database.initialize()
    with database.connection() as connection:
        connection.execute(
            """
            INSERT INTO devices (
                device_id, name, status, created_at, authorized_at, token_hash
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            ("device-1", "Phone", "authorized", "2026-08-11", "2026-08-11", "hash"),
        )
        connection.execute(
            """
            INSERT INTO actions (id, label, executable, arguments_json, enabled)
            VALUES (?, ?, ?, ?, ?)
            """,
            ("notepad", "Notepad", r"C:\Windows\notepad.exe", "[]", 1),
        )
    return database


def test_migration_preserves_database_byte_for_byte(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(
        "app.persistence.data_migration.harden_user_data_directory",
        lambda _path: None,
    )
    source = tmp_path / "source"
    destination = tmp_path / "destination"
    source_database = create_populated_database(source)
    original_digest = hashlib.sha256(source_database.path.read_bytes()).digest()

    migrated = migrate_database(source, destination)

    assert hashlib.sha256(migrated.read_bytes()).digest() == original_digest
    with sqlite3.connect(migrated) as connection:
        assert connection.execute("PRAGMA user_version").fetchone()[0] == 1
        assert connection.execute("SELECT token_hash FROM devices").fetchone()[0] == "hash"
        assert connection.execute("SELECT id FROM actions").fetchone()[0] == "notepad"


def test_existing_destination_is_never_overwritten(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(
        "app.persistence.data_migration.harden_user_data_directory",
        lambda _path: None,
    )
    source = tmp_path / "source"
    destination = tmp_path / "destination"
    create_populated_database(source)
    destination.mkdir()
    existing = destination / Database.filename
    existing.write_bytes(b"keep me")

    with pytest.raises(FileExistsError):
        migrate_database(source, destination)

    assert existing.read_bytes() == b"keep me"


def test_copy_failure_preserves_source_and_leaves_no_destination(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(
        "app.persistence.data_migration.harden_user_data_directory",
        lambda _path: None,
    )
    source = tmp_path / "source"
    destination = tmp_path / "destination"
    database = create_populated_database(source)
    source_bytes = database.path.read_bytes()
    monkeypatch.setattr(shutil, "copy2", lambda *_args: (_ for _ in ()).throw(OSError("disk")))

    with pytest.raises(OSError, match="disk"):
        migrate_database(source, destination)

    assert database.path.read_bytes() == source_bytes
    assert not (destination / Database.filename).exists()
    assert not list(destination.glob("*.migrating-*"))


def test_migration_preserves_device_token_authentication(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(
        "app.persistence.data_migration.harden_user_data_directory",
        lambda _path: None,
    )
    source = tmp_path / "source"
    destination = tmp_path / "destination"
    source_database = Database(source)
    source_database.initialize()
    registry = DeviceRegistry(store=SQLiteDeviceStore(source_database))
    now = datetime(2026, 8, 11, tzinfo=timezone.utc)
    device = Device(
        id=uuid4(),
        name="Phone",
        status=DeviceStatus.AUTHORIZED,
        created_at=now,
        authorized_at=now,
    )
    token = "pcpanel_device_token_that_must_remain_valid"
    registry.register(device, token)

    migrated_path = migrate_database(source, destination)
    migrated_database = Database(migrated_path.parent)
    migrated_registry = DeviceRegistry(store=SQLiteDeviceStore(migrated_database))

    assert migrated_registry.authenticate(token).id == device.id
