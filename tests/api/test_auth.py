import inspect
from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi.security import HTTPAuthorizationCredentials
from fastapi.testclient import TestClient

from app.api import dependencies
from app.api.app import create_app
from app.api.dependencies import bearer_scheme, require_authorized_device
from app.auth import AuthorizedDevice, Device, DeviceRegistry, DeviceStatus, TokenService
from app.telemetry.manager import TelemetryStatus


NOW = datetime(2026, 8, 10, 19, 0, tzinfo=timezone.utc)


class StubTelemetryManager:
    status = TelemetryStatus.RUNNING

    def start(self) -> None:
        pass

    def stop(self) -> None:
        pass

    def get_snapshot(self) -> None:
        return None


def registered_client() -> tuple[TestClient, DeviceRegistry, Device, str]:
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
    application = create_app(
        StubTelemetryManager(),  # type: ignore[arg-type]
        device_registry=registry,
    )
    return TestClient(application), registry, device, token


def test_valid_token_returns_sanitized_authenticated_device() -> None:
    client, _, device, token = registered_client()

    with client:
        response = client.get(
            "/api/v1/auth/status",
            headers={"Authorization": f"Bearer {token}"},
        )

    assert response.status_code == 200
    assert response.json() == {
        "authenticated": True,
        "device": {"id": str(device.id), "name": "Galaxy S24"},
    }
    assert token not in response.text
    assert "token_hash" not in response.text


def test_missing_authorization_is_401_with_bearer_challenge() -> None:
    client, _, _, _ = registered_client()

    with client:
        response = client.get("/api/v1/auth/status")

    assert response.status_code == 401
    assert response.status_code != 403
    assert response.headers["www-authenticate"] == "Bearer"


def test_invalid_token_is_401() -> None:
    client, _, _, _ = registered_client()

    with client:
        response = client.get(
            "/api/v1/auth/status",
            headers={"Authorization": "Bearer invalid-token"},
        )

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"


def test_revoked_token_has_same_external_401_semantics() -> None:
    client, registry, device, token = registered_client()
    registry.revoke(device.id)

    with client:
        response = client.get(
            "/api/v1/auth/status",
            headers={"Authorization": f"Bearer {token}"},
        )

    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid or missing bearer token"}
    assert "revoked" not in response.text.lower()
    assert response.headers["www-authenticate"] == "Bearer"


@pytest.mark.parametrize(
    "authorization",
    ["Basic dXNlcjpwYXNz", "Bearer", "Bearer "],
)
def test_wrong_scheme_or_malformed_bearer_is_401(authorization: str) -> None:
    client, _, _, _ = registered_client()

    with client:
        response = client.get(
            "/api/v1/auth/status",
            headers={"Authorization": authorization},
        )

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"


def test_http_bearer_explicitly_disables_automatic_errors() -> None:
    assert bearer_scheme.auto_error is False


def test_dependency_returns_authorized_device_not_credentials() -> None:
    _, registry, device, token = registered_client()
    request = SimpleNamespace(
        app=SimpleNamespace(state=SimpleNamespace(device_registry=registry))
    )
    credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)

    identity = require_authorized_device(request, credentials)  # type: ignore[arg-type]

    assert isinstance(identity, AuthorizedDevice)
    assert identity.id == device.id


@pytest.mark.parametrize(
    "path",
    [
        "/api/v1/health",
        "/api/v1/telemetry",
        "/api/v1/sensors",
        "/api/v1/metrics",
    ],
)
def test_read_only_http_routes_remain_public(path: str) -> None:
    client, _, _, _ = registered_client()

    with client:
        response = client.get(path)

    assert response.status_code != 401
    assert response.status_code != 403


def test_dependency_has_no_actions_coupling() -> None:
    source = inspect.getsource(dependencies)

    assert "ActionService" not in source
    assert "app.actions" not in source


def test_openapi_declares_http_bearer_security() -> None:
    client, _, _, _ = registered_client()

    with client:
        schema = client.get("/openapi.json").json()

    security_scheme = schema["components"]["securitySchemes"]["HTTPBearer"]
    operation = schema["paths"]["/api/v1/auth/status"]["get"]
    assert security_scheme == {"type": "http", "scheme": "bearer"}
    assert {"HTTPBearer": []} in operation["security"]
