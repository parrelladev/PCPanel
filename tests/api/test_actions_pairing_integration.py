from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import Mock
from uuid import UUID

from fastapi.testclient import TestClient

from pathlib import Path

from app.actions import ActionDefinition, ActionRegistry, ActionService
from app.api.app import create_app
from app.auth import DeviceRegistry, PairingService
from app.telemetry.manager import TelemetryStatus
from tests.actions.fakes import FakeActionExecutor
from tests.auth.fakes import FakePairingCodePresenter


NOW = datetime(2026, 8, 10, 19, 0, tzinfo=timezone.utc)
NOTEPAD_ACTION = ActionDefinition(
    id="notepad",
    label="Notepad",
    executable=Path(r"C:\Windows\System32\notepad.exe"),
)


class StubTelemetryManager:
    status = TelemetryStatus.RUNNING

    def start(self) -> None:
        pass

    def stop(self) -> None:
        pass


def test_pairing_token_actions_execution_and_revocation_end_to_end() -> None:
    devices = DeviceRegistry(clock=lambda: NOW)
    pairing = PairingService(devices, clock=lambda: NOW)
    presenter = FakePairingCodePresenter()
    executor = FakeActionExecutor()
    action_service = ActionService(
        ActionRegistry((NOTEPAD_ACTION,)),
        executor,
    )
    action_service_spy = Mock(spec=ActionService, wraps=action_service)
    application = create_app(
        StubTelemetryManager(),  # type: ignore[arg-type]
        action_service=action_service_spy,
        device_registry=devices,
        pairing_service=pairing,
        pairing_code_presenter=presenter,
        enable_actions_api=True,
    )

    with TestClient(application) as client:
        assert client.get("/api/v1/actions").status_code == 401
        assert client.post("/api/v1/actions/notepad/execute").status_code == 401
        assert executor.execution_count == 0

        started = client.post(
            "/api/v1/pairing/start",
            json={"device_name": "Integration test device"},
        )
        assert started.status_code == 201
        pairing_id = started.json()["pairing_id"]
        challenge = presenter.presented[0]
        assert str(challenge.pairing_id) == pairing_id

        completed = client.post(
            "/api/v1/pairing/complete",
            json={"pairing_id": pairing_id, "code": challenge.code},
        )
        assert completed.status_code == 200
        token = completed.json()["token"]
        authorization = {"Authorization": f"Bearer {token}"}

        catalog = client.get("/api/v1/actions", headers=authorization)
        assert catalog.status_code == 200
        assert catalog.json() == {
            "actions": [{"id": "notepad", "label": "Notepad"}]
        }
        assert "executable" not in catalog.text
        assert "arguments" not in catalog.text
        assert "working_directory" not in catalog.text

        execution = client.post(
            "/api/v1/actions/notepad/execute",
            headers=authorization,
        )
        assert execution.status_code == 200
        assert execution.json() == {"action_id": "notepad", "started": True}
        assert "executable" not in execution.text
        assert "arguments" not in execution.text

        action_service_spy.list_actions.assert_called_once_with()
        action_service_spy.execute.assert_called_once_with("notepad")
        assert executor.executed_actions == [NOTEPAD_ACTION]
        assert executor.executed_actions[0] is NOTEPAD_ACTION

        devices.revoke(UUID(completed.json()["device_id"]))
        rejected = client.post(
            "/api/v1/actions/notepad/execute",
            headers=authorization,
        )
        assert rejected.status_code == 401
        assert rejected.json() == {"detail": "Invalid or missing bearer token"}

    action_service_spy.execute.assert_called_once_with("notepad")
    assert executor.execution_count == 1
