from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import Mock
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.actions import ActionDefinition
from app.auth import Device, DeviceRevokedError, DeviceStatus, TokenService
from app.config import AppSettings
from app.main import build_app
from app.persistence import (
    CorruptStoredActionError,
    Database,
    SQLiteActionStore,
    SQLiteDeviceStore,
    StoredAction,
    StoredDevice,
)
from app.telemetry.manager import TelemetryStatus


NOW = datetime(2026, 8, 10, 18, 0, tzinfo=timezone.utc)


def isolate_telemetry(monkeypatch: pytest.MonkeyPatch) -> Mock:
    manager = Mock()
    manager.status = TelemetryStatus.RUNNING
    monkeypatch.setattr(
        "app.main.LibreHardwareMonitorProvider",
        Mock(return_value=Mock()),
    )
    monkeypatch.setattr("app.main.TelemetryManager", Mock(return_value=manager))
    return manager


def settings(data_dir: Path) -> AppSettings:
    return AppSettings(data_dir=data_dir, enable_actions_api=True)


def test_fresh_startup_initializes_database(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    isolate_telemetry(monkeypatch)

    application = build_app(settings(tmp_path))

    assert (tmp_path / "pcpanel.db").is_file()
    assert application.state.device_registry.list_devices() == ()
    assert application.state.action_service.list_actions() == ()


def test_restart_reuses_devices_actions_and_shared_services(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    isolate_telemetry(monkeypatch)
    first_application = build_app(settings(tmp_path))
    database = Database(tmp_path)
    device_store = SQLiteDeviceStore(database)
    action_store = SQLiteActionStore(database)
    token = TokenService.generate_device_token()
    token_hash = TokenService.hash_device_token(token)
    revoked_token = TokenService.generate_device_token()
    device = Device(
        id=uuid4(),
        name="Persistent phone",
        status=DeviceStatus.AUTHORIZED,
        created_at=NOW,
        authorized_at=NOW,
    )
    revoked_device = Device(
        id=uuid4(),
        name="Revoked phone",
        status=DeviceStatus.REVOKED,
        created_at=NOW,
        authorized_at=NOW,
        revoked_at=NOW + timedelta(minutes=5),
    )
    device_store.save_device(StoredDevice(device, token_hash))
    device_store.save_device(
        StoredDevice(
            revoked_device,
            TokenService.hash_device_token(revoked_token),
        )
    )
    enabled = StoredAction(
        ActionDefinition(
            id="editor",
            label="Editor",
            executable=Path("editor.exe"),
            arguments=("--profile", "value with spaces"),
            working_directory=Path("workspace"),
        ),
        enabled=True,
    )
    disabled = StoredAction(
        ActionDefinition(
            id="hidden",
            label="Hidden",
            executable=Path("hidden.exe"),
        ),
        enabled=False,
    )
    action_store.save_action(enabled)
    action_store.save_action(disabled)

    restarted = build_app(settings(tmp_path))

    registry = restarted.state.device_registry
    action_service = restarted.state.action_service
    pairing_service = restarted.state.pairing_service
    assert restarted is not first_application
    assert registry.authenticate(token).id == device.id
    assert registry.get(revoked_device.id) == revoked_device
    with pytest.raises(DeviceRevokedError):
        registry.authenticate(revoked_token)
    assert action_service.list_actions() == (enabled.definition,)
    assert action_service._registry.list() == (enabled.definition,)
    assert pairing_service._registry is registry
    assert restarted.state.action_service is action_service
    assert restarted.state.pairing_service is pairing_service


def test_database_is_composed_once_not_per_request(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manager = isolate_telemetry(monkeypatch)
    real_database = Database
    created: list[Database] = []

    def database_factory(data_dir: Path) -> Database:
        database = real_database(data_dir)
        created.append(database)
        return database

    monkeypatch.setattr("app.main.Database", database_factory)
    application = build_app(settings(tmp_path))

    with TestClient(application) as client:
        assert client.get("/api/v1/health").status_code == 200
        assert client.get("/api/v1/health").status_code == 200

    assert len(created) == 1
    manager.start.assert_called_once_with()
    manager.stop.assert_called_once_with()


def test_corrupt_persisted_configuration_aborts_startup(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manager = isolate_telemetry(monkeypatch)
    database = Database(tmp_path)
    database.initialize()
    with database.connection() as connection:
        connection.execute(
            """
            INSERT INTO actions (
                id, label, executable, arguments_json, working_directory, enabled
            ) VALUES ('Invalid ID', 'Bad', 'bad.exe', '[]', NULL, 1)
            """
        )

    with pytest.raises(CorruptStoredActionError):
        build_app(settings(tmp_path))

    manager.start.assert_not_called()
