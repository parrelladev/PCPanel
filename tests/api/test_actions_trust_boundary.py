from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from urllib.parse import quote
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.actions import ActionDefinition, ActionRegistry, ActionService
from app.api import actions as actions_api
from app.api.app import create_app
from app.auth import Device, DeviceRegistry, DeviceStatus, TokenService
from app.telemetry.manager import TelemetryStatus
from app.telemetry.models import SensorReading, TelemetrySnapshot
from tests.actions.fakes import FakeActionExecutor


NOW = datetime(2026, 8, 10, 19, 0, tzinfo=timezone.utc)
REGISTERED_ACTION = ActionDefinition(
    id="notepad",
    label="Bloco de Notas",
    executable=Path("C:/Windows/System32/notepad.exe"),
    arguments=("server-owned",),
    working_directory=Path("C:/Windows/System32"),
)
SNAPSHOT = TelemetrySnapshot(
    sequence=1,
    captured_at=NOW,
    sensors=(
        SensorReading(
            hardware_identifier="/cpu/0",
            hardware_name="CPU",
            hardware_type="Cpu",
            sensor_identifier="/cpu/0/load/total",
            sensor_name="CPU Total",
            sensor_type="Load",
            value=20.0,
            min_value=None,
            max_value=None,
        ),
    ),
)


class StubTelemetryManager:
    status = TelemetryStatus.RUNNING

    def __init__(self) -> None:
        self._lock = Lock()

    def start(self) -> None:
        pass

    def stop(self) -> None:
        pass

    def get_snapshot(self) -> TelemetrySnapshot:
        with self._lock:
            return SNAPSHOT


def boundary_client(
    *,
    enabled: bool = True,
) -> tuple[TestClient, str, FakeActionExecutor]:
    executor = FakeActionExecutor()
    service = ActionService(ActionRegistry((REGISTERED_ACTION,)), executor)
    devices = DeviceRegistry(clock=lambda: NOW)
    token = TokenService.generate_device_token()
    devices.register(
        Device(
            id=uuid4(),
            name="Boundary test device",
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
        enable_actions_api=enabled,
    )
    return TestClient(application), token, executor


@pytest.mark.parametrize(
    "body",
    [
        {"executable": r"C:\Windows\System32\cmd.exe"},
        {"command": "whoami"},
        {"arguments": ["/c", "calc"]},
        {"working_directory": "C:\\"},
    ],
)
def test_arbitrary_json_never_changes_registered_definition(
    body: dict[str, object],
) -> None:
    client, token, executor = boundary_client()

    with client:
        response = client.post(
            "/api/v1/actions/notepad/execute",
            headers={"Authorization": f"Bearer {token}"},
            json=body,
        )

    assert response.status_code == 200
    assert executor.executed_actions == [REGISTERED_ACTION]
    assert executor.executed_actions[0] is REGISTERED_ACTION


def test_arbitrary_query_parameters_never_reach_executor() -> None:
    client, token, executor = boundary_client()

    with client:
        response = client.post(
            "/api/v1/actions/notepad/execute",
            headers={"Authorization": f"Bearer {token}"},
            params={
                "executable": r"C:\Windows\System32\cmd.exe",
                "command": "whoami",
                "arguments": "/c calc",
                "working_directory": "C:\\",
            },
        )

    assert response.status_code == 200
    assert executor.executed_actions == [REGISTERED_ACTION]
    assert executor.executed_actions[0] is REGISTERED_ACTION


@pytest.mark.parametrize(
    "action_id",
    [
        "../cmd",
        "cmd.exe",
        r"C:\Windows\System32\cmd.exe",
        "%COMSPEC%",
        "powershell",
    ],
)
def test_hostile_unregistered_ids_never_reach_executor(action_id: str) -> None:
    client, token, executor = boundary_client()
    encoded_action_id = quote(action_id, safe="")

    with client:
        response = client.post(
            f"/api/v1/actions/{encoded_action_id}/execute",
            headers={"Authorization": f"Bearer {token}"},
        )

    assert response.status_code == 404
    assert executor.execution_count == 0


def test_catalog_never_leaks_credentials_or_process_configuration() -> None:
    client, token, _ = boundary_client()

    with client:
        response = client.get(
            "/api/v1/actions",
            headers={"Authorization": f"Bearer {token}"},
        )

    assert response.status_code == 200
    assert response.json() == {
        "actions": [{"id": "notepad", "label": "Bloco de Notas"}]
    }
    for forbidden in (
        "executable",
        "arguments",
        "working_directory",
        token,
        "token_hash",
    ):
        assert forbidden not in response.text


def test_actions_executor_security_invariants_are_present() -> None:
    actions_root = Path(actions_api.__file__).parents[1] / "actions"
    source = "\n".join(
        path.read_text(encoding="utf-8") for path in actions_root.glob("*.py")
    )

    assert '"shell": False' in source
    assert "shell=True" not in source
    assert "os.system(" not in source
    assert "cmd.exe /c" not in source


def test_api_layer_has_no_process_or_registry_implementation_coupling() -> None:
    api_root = Path(actions_api.__file__).parent
    source = "\n".join(
        path.read_text(encoding="utf-8") for path in api_root.glob("*.py")
    )

    assert "subprocess" not in source
    assert "WindowsProcessExecutor" not in source
    assert "ActionRegistry" not in source


def test_public_http_and_websocket_telemetry_remain_anonymous() -> None:
    client, _, _ = boundary_client()

    with client:
        for path in (
            "/api/v1/health",
            "/api/v1/telemetry",
            "/api/v1/sensors",
            "/api/v1/metrics",
        ):
            assert client.get(path).status_code == 200

        with client.websocket_connect("/ws/v1/telemetry") as telemetry:
            assert telemetry.receive_json()["sequence"] == 1
        with client.websocket_connect("/ws/v1/metrics") as metrics:
            assert metrics.receive_json()["sequence"] == 1
