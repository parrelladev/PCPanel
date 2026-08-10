from __future__ import annotations

import inspect
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import Mock
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.actions import (
    ActionDefinition,
    ActionExecution,
    ActionExecutionError,
    ActionNotFoundError,
    ActionService,
    ActionUnavailableError,
)
from app.api import actions as actions_api
from app.api.app import create_app
from app.auth import Device, DeviceRegistry, DeviceStatus, TokenService
from app.telemetry.manager import TelemetryStatus


NOW = datetime(2026, 8, 10, 19, 0, tzinfo=timezone.utc)
NOTEPAD = ActionDefinition(
    id="notepad",
    label="Bloco de Notas",
    executable=Path("C:/Windows/System32/notepad.exe"),
)


class StubTelemetryManager:
    status = TelemetryStatus.RUNNING

    def start(self) -> None:
        pass

    def stop(self) -> None:
        pass

    def get_snapshot(self) -> None:
        return None


def actions_client(
    *,
    enabled: bool = True,
) -> tuple[TestClient, DeviceRegistry, Device, str, Mock]:
    registry = DeviceRegistry(clock=lambda: NOW)
    device = Device(
        id=uuid4(),
        name="Galaxy S24",
        status=DeviceStatus.AUTHORIZED,
        created_at=NOW,
        authorized_at=NOW,
    )
    token = TokenService.generate_device_token()
    registry.register(device, token)
    service = Mock(spec=ActionService)
    service.list_actions.return_value = (NOTEPAD,)
    application = create_app(
        StubTelemetryManager(),  # type: ignore[arg-type]
        action_service=service,
        device_registry=registry,
        enable_actions_api=enabled,
    )
    return TestClient(application), registry, device, token, service


@pytest.mark.parametrize(
    "headers",
    [
        {},
        {"Authorization": "Bearer invalid-token"},
    ],
)
def test_actions_catalog_rejects_missing_or_invalid_bearer(
    headers: dict[str, str],
) -> None:
    client, _, _, _, service = actions_client()

    with client:
        response = client.get("/api/v1/actions", headers=headers)

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"
    service.list_actions.assert_not_called()


def test_actions_catalog_rejects_revoked_bearer() -> None:
    client, registry, device, token, service = actions_client()
    registry.revoke(device.id)

    with client:
        response = client.get(
            "/api/v1/actions",
            headers={"Authorization": f"Bearer {token}"},
        )

    assert response.status_code == 401
    service.list_actions.assert_not_called()


@pytest.mark.parametrize(
    "headers",
    [
        {},
        {"Authorization": "Bearer invalid-token"},
    ],
)
def test_action_execution_rejects_missing_or_invalid_bearer(
    headers: dict[str, str],
) -> None:
    client, _, _, _, service = actions_client()

    with client:
        response = client.post(
            "/api/v1/actions/notepad/execute",
            headers=headers,
        )

    assert response.status_code == 401
    service.execute.assert_not_called()


def test_unauthorized_unknown_action_returns_auth_error_before_lookup() -> None:
    client, _, _, _, service = actions_client()

    with client:
        response = client.post("/api/v1/actions/unknown/execute")

    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid or missing bearer token"}
    service.execute.assert_not_called()


def test_action_execution_rejects_revoked_bearer() -> None:
    client, registry, device, token, service = actions_client()
    registry.revoke(device.id)

    with client:
        response = client.post(
            "/api/v1/actions/notepad/execute",
            headers={"Authorization": f"Bearer {token}"},
        )

    assert response.status_code == 401
    service.execute.assert_not_called()


def test_authorized_catalog_returns_only_safe_metadata() -> None:
    client, _, _, token, service = actions_client()

    with client:
        response = client.get(
            "/api/v1/actions",
            headers={"Authorization": f"Bearer {token}"},
        )

    assert response.status_code == 200
    assert response.json() == {
        "actions": [{"id": "notepad", "label": "Bloco de Notas"}]
    }
    assert "executable" not in response.text
    assert "arguments" not in response.text
    assert "working_directory" not in response.text
    service.list_actions.assert_called_once_with()


def test_authorized_execution_needs_no_body_and_passes_exact_action_id() -> None:
    client, _, _, token, service = actions_client()
    service.execute.return_value = ActionExecution(
        action_id="notepad",
        started=True,
        process_id=4321,
    )

    with client:
        response = client.post(
            "/api/v1/actions/notepad/execute",
            headers={"Authorization": f"Bearer {token}"},
        )

    assert response.status_code == 200
    assert response.json() == {"action_id": "notepad", "started": True}
    service.execute.assert_called_once_with("notepad")


def test_remote_process_parameters_do_not_influence_execution() -> None:
    client, _, _, token, service = actions_client()
    service.execute.return_value = ActionExecution(
        action_id="notepad",
        started=True,
        process_id=None,
    )

    with client:
        response = client.post(
            "/api/v1/actions/notepad/execute",
            headers={"Authorization": f"Bearer {token}"},
            params={"executable": "query.exe", "arguments": "--query"},
            json={
                "executable": "cmd.exe",
                "arguments": ["/c", "whoami"],
                "working_directory": "C:/",
                "command": "cmd.exe",
                "shell": True,
            },
        )

    assert response.status_code == 200
    service.execute.assert_called_once_with("notepad")
    assert response.json() == {"action_id": "notepad", "started": True}


def test_unknown_action_is_safely_mapped_to_not_found() -> None:
    client, _, _, token, service = actions_client()
    service.execute.side_effect = ActionNotFoundError("missing")

    with client:
        response = client.post(
            "/api/v1/actions/missing/execute",
            headers={"Authorization": f"Bearer {token}"},
        )

    assert response.status_code == 404
    assert response.json() == {"detail": "Action not found."}
    service.execute.assert_called_once_with("missing")


@pytest.mark.parametrize(
    ("error", "expected_status", "expected_detail"),
    [
        (
            ActionUnavailableError(
                "notepad",
                reason="executable C:/secret cwd command line",
            ),
            409,
            "Action is unavailable.",
        ),
        (
            ActionExecutionError("notepad", reason="private OSError detail"),
            500,
            "Action execution failed.",
        ),
    ],
)
def test_execution_errors_do_not_expose_host_details(
    error: Exception,
    expected_status: int,
    expected_detail: str,
) -> None:
    client, _, _, token, service = actions_client()
    service.execute.side_effect = error

    with client:
        response = client.post(
            "/api/v1/actions/notepad/execute",
            headers={"Authorization": f"Bearer {token}"},
        )

    assert response.status_code == expected_status
    assert response.json() == {"detail": expected_detail}
    assert "secret" not in response.text
    assert "OSError" not in response.text
    assert "executable" not in response.text
    assert "cwd" not in response.text
    assert "command line" not in response.text


def test_disabled_actions_api_does_not_register_catalog_route() -> None:
    client, _, _, token, service = actions_client(enabled=False)

    with client:
        response = client.get(
            "/api/v1/actions",
            headers={"Authorization": f"Bearer {token}"},
        )

    assert response.status_code == 404
    service.list_actions.assert_not_called()
    with client:
        execution_response = client.post("/api/v1/actions/notepad/execute")
    assert execution_response.status_code == 404
    service.execute.assert_not_called()


@pytest.mark.parametrize("path", ["/api/v1/health", "/api/v1/metrics"])
def test_existing_read_routes_remain_public_when_actions_are_enabled(path: str) -> None:
    client, _, _, _, _ = actions_client()

    with client:
        response = client.get(path)

    assert response.status_code not in {401, 403}


def test_actions_route_has_no_registry_or_executor_coupling() -> None:
    source = inspect.getsource(actions_api.list_actions)
    source += inspect.getsource(actions_api.execute_action)

    assert "ActionRegistry" not in source
    assert "WindowsProcessExecutor" not in source
    assert "subprocess" not in source


def test_execute_operation_declares_no_request_body() -> None:
    client, _, _, _, _ = actions_client()

    with client:
        schema = client.get("/openapi.json").json()

    operation = schema["paths"]["/api/v1/actions/{action_id}/execute"]["post"]
    assert "requestBody" not in operation


def test_actions_domain_has_no_fastapi_or_http_status_coupling() -> None:
    actions_root = Path(actions_api.__file__).parents[1] / "actions"

    domain_source = "\n".join(
        source.read_text(encoding="utf-8")
        for source in actions_root.glob("*.py")
    )

    assert "fastapi" not in domain_source.lower()
    assert "HTTPException" not in domain_source
    assert "status.HTTP_" not in domain_source
