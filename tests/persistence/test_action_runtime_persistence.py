from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.actions import (
    ActionDefinition,
    ActionNotFoundError,
    ActionRegistry,
    ActionService,
)
from app.api.app import create_app
from app.auth import Device, DeviceRegistry, DeviceStatus, TokenService
from app.persistence import Database, SQLiteActionStore, StoredAction
from app.telemetry.manager import TelemetryStatus
from tests.actions.fakes import FakeActionExecutor


NOW = datetime(2026, 8, 10, 19, 0, tzinfo=timezone.utc)


class StubTelemetryManager:
    status = TelemetryStatus.RUNNING

    def start(self) -> None:
        pass

    def stop(self) -> None:
        pass


def definition(action_id: str, *, arguments: tuple[str, ...] = ()) -> ActionDefinition:
    return ActionDefinition(
        id=action_id,
        label=action_id.title(),
        executable=Path(f"bin/{action_id}.exe"),
        arguments=arguments,
        working_directory=Path("workspace"),
    )


def compose_from_store(
    store: SQLiteActionStore,
    executor: FakeActionExecutor,
) -> ActionService:
    active = tuple(
        record.definition for record in store.load_actions() if record.enabled
    )
    return ActionService(ActionRegistry(active), executor)


def test_empty_database_builds_empty_registry(tmp_path: Path) -> None:
    database = Database(tmp_path)
    database.initialize()

    service = compose_from_store(SQLiteActionStore(database), FakeActionExecutor())

    assert service.list_actions() == ()
    with pytest.raises(ActionNotFoundError):
        service.execute("notepad")


def test_enabled_actions_enter_registry_and_disabled_actions_stay_stored(
    tmp_path: Path,
) -> None:
    database = Database(tmp_path)
    database.initialize()
    store = SQLiteActionStore(database)
    first = StoredAction(definition("editor"), enabled=True)
    second = StoredAction(definition("terminal"), enabled=True)
    disabled = StoredAction(definition("notepad"), enabled=False)
    for record in (first, second, disabled):
        store.save_action(record)

    service = compose_from_store(store, FakeActionExecutor())

    assert service.list_actions() == (first.definition, second.definition)
    assert store.load_actions() == (first, disabled, second)
    with pytest.raises(ActionNotFoundError):
        service.execute("notepad")


def test_restart_reconstructs_action_and_service_resolves_without_real_process(
    tmp_path: Path,
) -> None:
    first_database = Database(tmp_path)
    first_database.initialize()
    persisted = StoredAction(
        definition(
            "editor",
            arguments=("--profile", "value with spaces"),
        ),
        enabled=True,
    )
    SQLiteActionStore(first_database).save_action(persisted)

    second_database = Database(tmp_path)
    second_database.initialize()
    executor = FakeActionExecutor()
    service = compose_from_store(SQLiteActionStore(second_database), executor)

    assert service.list_actions() == (persisted.definition,)
    loaded = service.list_actions()[0]
    assert loaded.arguments == ("--profile", "value with spaces")
    assert loaded.working_directory == Path("workspace")
    result = service.execute("editor")
    assert result.started is True
    assert executor.executed_actions == [persisted.definition]

    devices = DeviceRegistry()
    token = TokenService.generate_device_token()
    devices.register(
        Device(
            id=uuid4(),
            name="Restart test phone",
            status=DeviceStatus.AUTHORIZED,
            created_at=NOW,
            authorized_at=NOW,
        ),
        token,
    )
    application = create_app(
        StubTelemetryManager(),  # type: ignore[arg-type]
        action_service=service,
        device_registry=devices,
        enable_actions_api=True,
    )
    with TestClient(application) as client:
        response = client.get(
            "/api/v1/actions",
            headers={"Authorization": f"Bearer {token}"},
        )
    assert response.status_code == 200
    assert response.json() == {
        "actions": [{"id": "editor", "label": "Editor"}]
    }


def test_authenticated_empty_catalog_and_unknown_action_are_safe(
    tmp_path: Path,
) -> None:
    database = Database(tmp_path)
    database.initialize()
    service = compose_from_store(SQLiteActionStore(database), FakeActionExecutor())
    devices = DeviceRegistry()
    token = TokenService.generate_device_token()
    devices.register(
        Device(
            id=uuid4(),
            name="Test phone",
            status=DeviceStatus.AUTHORIZED,
            created_at=NOW,
            authorized_at=NOW,
        ),
        token,
    )
    application = create_app(
        StubTelemetryManager(),  # type: ignore[arg-type]
        action_service=service,
        device_registry=devices,
        enable_actions_api=True,
    )
    authorization = {"Authorization": f"Bearer {token}"}

    with TestClient(application) as client:
        catalog = client.get("/api/v1/actions", headers=authorization)
        unknown = client.post(
            "/api/v1/actions/unknown/execute",
            headers=authorization,
        )

    assert catalog.status_code == 200
    assert catalog.json() == {"actions": []}
    assert unknown.status_code == 404
