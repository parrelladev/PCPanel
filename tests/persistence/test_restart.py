from __future__ import annotations

import gc
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import UUID

import pytest

from app.actions import ActionDefinition, ActionRegistry, ActionService
from app.auth import (
    DeviceRegistry,
    DeviceRevokedError,
    InvalidDeviceTokenError,
    PairingNotFoundError,
    PairingService,
    TokenService,
)
from app.config import AppSettings
from app.main import build_app
from app.persistence import (
    Database,
    SQLiteActionStore,
    SQLiteDeviceStore,
    StoredAction,
    StoredDevice,
    UnsupportedSchemaVersionError,
)
from app.persistence import migrations
from tests.actions.fakes import FakeActionExecutor


NOW = datetime(2026, 8, 10, 20, 0, tzinfo=timezone.utc)


def auth_stack(data_dir: Path) -> tuple[
    Database,
    SQLiteDeviceStore,
    DeviceRegistry,
    PairingService,
]:
    database = Database(data_dir)
    database.initialize()
    store = SQLiteDeviceStore(database)
    registry = DeviceRegistry(store=store, clock=lambda: NOW)
    pairing = PairingService(registry, clock=lambda: NOW)
    return database, store, registry, pairing


def action_stack(data_dir: Path) -> tuple[
    Database,
    SQLiteActionStore,
    ActionRegistry,
    ActionService,
]:
    database = Database(data_dir)
    database.initialize()
    store = SQLiteActionStore(database)
    registry = ActionRegistry(
        record.definition for record in store.load_actions() if record.enabled
    )
    return database, store, registry, ActionService(registry, FakeActionExecutor())


def pair(pairing: PairingService, name: str = "Restart phone") -> tuple[str, UUID]:
    challenge = pairing.start_pairing(name)
    issued = pairing.complete_pairing(challenge.pairing_id, challenge.code)
    return issued.token, issued.device_id


def test_token_authenticates_after_all_first_instance_memory_is_destroyed(
    tmp_path: Path,
) -> None:
    database_a, store_a, registry_a, pairing_a = auth_stack(tmp_path)
    token, device_id = pair(pairing_a)
    assert registry_a.authenticate(token).id == device_id

    del pairing_a, registry_a, store_a, database_a
    gc.collect()

    database_b, store_b, registry_b, pairing_b = auth_stack(tmp_path)

    assert registry_b.authenticate(token).id == device_id
    assert database_b.path == tmp_path / "pcpanel.db"
    assert store_b is not None
    assert pairing_b._registry is registry_b


def test_revoked_token_remains_rejected_after_restart(tmp_path: Path) -> None:
    database_a, store_a, registry_a, pairing_a = auth_stack(tmp_path)
    token, device_id = pair(pairing_a)
    registry_a.revoke(device_id)

    del pairing_a, registry_a, store_a, database_a
    gc.collect()

    _, _, registry_b, _ = auth_stack(tmp_path)

    assert registry_b.get(device_id).revoked_at == NOW
    with pytest.raises(DeviceRevokedError):
        registry_b.authenticate(token)


def test_pending_pairing_session_disappears_on_restart(tmp_path: Path) -> None:
    database_a, store_a, registry_a, pairing_a = auth_stack(tmp_path)
    challenge = pairing_a.start_pairing("Ephemeral pairing")

    del pairing_a, registry_a, store_a, database_a
    gc.collect()

    _, _, registry_b, pairing_b = auth_stack(tmp_path)

    assert registry_b.list_devices() == ()
    with pytest.raises(PairingNotFoundError):
        pairing_b.complete_pairing(challenge.pairing_id, challenge.code)


def test_action_round_trip_rebuilds_active_registry_exactly(tmp_path: Path) -> None:
    database_a, store_a, registry_a, service_a = action_stack(tmp_path)
    definition = ActionDefinition(
        id="editor",
        label="Editorial workspace",
        executable=Path("tools/editor.exe"),
        arguments=("--profile", "value with spaces", "--safe-mode"),
        working_directory=Path("editor-workspace"),
    )
    store_a.save_action(StoredAction(definition, enabled=True))

    del service_a, registry_a, store_a, database_a
    gc.collect()

    _, _, registry_b, service_b = action_stack(tmp_path)
    loaded = registry_b.get("editor")

    assert service_b.list_actions() == (loaded,)
    assert loaded.id == definition.id
    assert loaded.label == definition.label
    assert loaded.arguments == definition.arguments
    assert loaded.arguments[1] == "value with spaces"
    assert loaded.working_directory == definition.working_directory
    assert loaded.executable == definition.executable


def test_disabled_action_survives_but_is_not_active_after_restart(
    tmp_path: Path,
) -> None:
    database_a, store_a, registry_a, service_a = action_stack(tmp_path)
    disabled = StoredAction(
        ActionDefinition(
            id="hidden",
            label="Hidden action",
            executable=Path("hidden.exe"),
        ),
        enabled=False,
    )
    store_a.save_action(disabled)

    del service_a, registry_a, store_a, database_a
    gc.collect()

    _, store_b, registry_b, service_b = action_stack(tmp_path)

    assert store_b.load_actions() == (disabled,)
    assert registry_b.list() == ()
    assert service_b.list_actions() == ()


def test_device_save_failure_leaves_no_partial_row(tmp_path: Path) -> None:
    database = Database(tmp_path)
    database.initialize()
    store = SQLiteDeviceStore(database)
    _, device_id = pair(auth_stack(tmp_path)[3], "Existing phone")
    existing = store.load_devices()[0]
    candidate = StoredDevice(
        device=existing.device.__class__(
            id=device_id,
            name="Replacement",
            status=existing.device.status,
            created_at=existing.device.created_at,
            authorized_at=existing.device.authorized_at,
        ),
        token_hash="replacement-hash",
    )
    with database.connection() as connection:
        connection.execute(
            """
            CREATE TRIGGER fail_device_update BEFORE UPDATE ON devices BEGIN
                SELECT RAISE(ABORT, 'device save failed');
            END
            """
        )

    with pytest.raises(sqlite3.IntegrityError, match="device save failed"):
        store.save_device(candidate)

    assert store.load_devices() == (existing,)


def test_action_save_failure_leaves_no_partial_row(tmp_path: Path) -> None:
    database = Database(tmp_path)
    database.initialize()
    store = SQLiteActionStore(database)
    with database.connection() as connection:
        connection.execute("CREATE TABLE action_failure_audit (id TEXT)")
        connection.execute(
            """
            CREATE TRIGGER fail_action BEFORE INSERT ON actions BEGIN
                INSERT INTO action_failure_audit VALUES (NEW.id);
                SELECT RAISE(ABORT, 'action save failed');
            END
            """
        )
    record = StoredAction(
        ActionDefinition(id="editor", label="Editor", executable=Path("editor.exe"))
    )

    with pytest.raises(sqlite3.IntegrityError, match="action save failed"):
        store.save_action(record)

    with database.connection() as connection:
        assert connection.execute("SELECT COUNT(*) FROM actions").fetchone()[0] == 0
        assert connection.execute(
            "SELECT COUNT(*) FROM action_failure_audit"
        ).fetchone()[0] == 0


def test_migration_failure_rolls_back_schema_and_version(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    database = Database(tmp_path)

    def fail_after_ddl(connection: sqlite3.Connection) -> None:
        connection.execute("CREATE TABLE partial_migration (id INTEGER)")
        raise RuntimeError("injected migration failure")

    monkeypatch.setitem(migrations._MIGRATIONS, 0, fail_after_ddl)

    with pytest.raises(RuntimeError, match="injected migration failure"):
        database.initialize()

    with database.connection() as connection:
        assert connection.execute("PRAGMA user_version").fetchone()[0] == 0
        tables = connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        ).fetchall()
    assert tables == []


def test_pairing_persistence_failure_returns_no_usable_token(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    database, _, registry, pairing_service = auth_stack(tmp_path)
    with database.connection() as connection:
        connection.execute(
            """
            CREATE TRIGGER fail_pairing_device BEFORE INSERT ON devices BEGIN
                SELECT RAISE(ABORT, 'pairing save failed');
            END
            """
        )
    token = "generated-but-not-returned"
    monkeypatch.setattr(
        TokenService,
        "generate_device_token",
        staticmethod(lambda: token),
    )
    challenge = pairing_service.start_pairing("Failed phone")

    with pytest.raises(sqlite3.IntegrityError, match="pairing save failed"):
        pairing_service.complete_pairing(challenge.pairing_id, challenge.code)

    assert registry.list_devices() == ()
    with pytest.raises(InvalidDeviceTokenError):
        registry.authenticate(token)
    with database.connection() as connection:
        assert connection.execute("SELECT COUNT(*) FROM devices").fetchone()[0] == 0


def test_future_schema_version_aborts_application_startup(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    database = Database(tmp_path)
    with database.connection() as connection:
        connection.execute("PRAGMA user_version = 999")
    telemetry_factory = MockTelemetryFactory()
    monkeypatch.setattr(
        "app.main.LibreHardwareMonitorProvider",
        telemetry_factory.provider,
    )
    monkeypatch.setattr("app.main.TelemetryManager", telemetry_factory.manager)

    with pytest.raises(UnsupportedSchemaVersionError):
        build_app(AppSettings(data_dir=tmp_path))


class MockTelemetryFactory:
    def __init__(self) -> None:
        self.provider = lambda **kwargs: object()
        self.manager = lambda provider, interval: object()
