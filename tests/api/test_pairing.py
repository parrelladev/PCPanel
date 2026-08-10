from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from app.api.app import create_app
from app.auth import DeviceRegistry, PairingService
from app.telemetry.manager import TelemetryStatus
from tests.auth.fakes import FakePairingCodePresenter


NOW = datetime(2026, 8, 10, 18, 0, tzinfo=timezone.utc)


class StubTelemetryManager:
    status = TelemetryStatus.RUNNING

    def start(self) -> None:
        pass

    def stop(self) -> None:
        pass


class MutableClock:
    def __init__(self) -> None:
        self.now = NOW

    def __call__(self) -> datetime:
        return self.now


def auth_client(
    *,
    max_attempts: int = 5,
    max_pending_pairings: int = 10,
) -> tuple[TestClient, FakePairingCodePresenter, DeviceRegistry, MutableClock]:
    clock = MutableClock()
    registry = DeviceRegistry(clock=clock)
    pairing = PairingService(
        registry,
        max_attempts=max_attempts,
        max_pending_pairings=max_pending_pairings,
        clock=clock,
    )
    presenter = FakePairingCodePresenter()
    application = create_app(
        StubTelemetryManager(),  # type: ignore[arg-type]
        device_registry=registry,
        pairing_service=pairing,
        pairing_code_presenter=presenter,
    )
    return TestClient(application), presenter, registry, clock


def start(client: TestClient, name: str = "Galaxy S24"):  # type: ignore[no-untyped-def]
    return client.post("/api/v1/pairing/start", json={"device_name": name})


def test_start_returns_sanitized_response_and_presents_code() -> None:
    client, presenter, _, _ = auth_client()

    with client:
        response = start(client)

    assert response.status_code == 201
    body = response.json()
    assert set(body) == {"pairing_id", "expires_at"}
    assert "code" not in body
    assert "code_hash" not in body
    assert "token" not in body
    assert presenter.presented[0].code
    assert str(presenter.presented[0].pairing_id) == body["pairing_id"]
    assert presenter.presented[0].expires_at.isoformat().replace("+00:00", "Z") == body[
        "expires_at"
    ]


@pytest.mark.parametrize("name", ["", "Phone\nname"])
def test_start_rejects_invalid_device_name(name: str) -> None:
    client, presenter, _, _ = auth_client()

    with client:
        response = start(client, name)

    assert response.status_code == 422
    assert response.json() == {"detail": "Invalid device name"}
    assert presenter.presented == []


def test_start_maps_pending_capacity() -> None:
    client, presenter, _, _ = auth_client(max_pending_pairings=1)

    with client:
        assert start(client, "Phone").status_code == 201
        response = start(client, "Tablet")

    assert response.status_code == 429
    assert response.json() == {"detail": "Pairing capacity has been reached"}
    assert len(presenter.presented) == 1


def test_complete_creates_device_and_returns_one_time_token() -> None:
    client, presenter, registry, _ = auth_client()

    with client:
        start_response = start(client)
        challenge = presenter.presented[0]
        response = client.post(
            "/api/v1/pairing/complete",
            json={
                "pairing_id": start_response.json()["pairing_id"],
                "code": challenge.code,
            },
        )

    assert response.status_code == 200
    body = response.json()
    assert set(body) == {"device_id", "token"}
    assert body["token"]
    assert registry.authenticate(body["token"]).id == registry.list_devices()[0].id
    assert body["device_id"] == str(registry.list_devices()[0].id)
    assert "token" not in start_response.json()
    assert "token_hash" not in start_response.json()


def test_complete_maps_wrong_code_without_creating_device() -> None:
    client, presenter, registry, _ = auth_client()

    with client:
        started = start(client)
        correct = presenter.presented[0].code
        wrong = "000000" if correct != "000000" else "000001"
        response = client.post(
            "/api/v1/pairing/complete",
            json={"pairing_id": started.json()["pairing_id"], "code": wrong},
        )

    assert response.status_code == 401
    assert response.json() == {"detail": "Pairing code is invalid"}
    assert registry.list_devices() == ()


def test_complete_maps_expired_pairing() -> None:
    client, presenter, registry, clock = auth_client()

    with client:
        started = start(client)
        challenge = presenter.presented[0]
        clock.now = challenge.expires_at
        response = client.post(
            "/api/v1/pairing/complete",
            json={"pairing_id": started.json()["pairing_id"], "code": challenge.code},
        )

    assert response.status_code == 410
    assert response.json() == {"detail": "Pairing has expired"}
    assert registry.list_devices() == ()


def test_complete_maps_consumed_pairing_and_does_not_reissue_token() -> None:
    client, presenter, registry, _ = auth_client()

    with client:
        started = start(client)
        payload = {
            "pairing_id": started.json()["pairing_id"],
            "code": presenter.presented[0].code,
        }
        first = client.post("/api/v1/pairing/complete", json=payload)
        replay = client.post("/api/v1/pairing/complete", json=payload)

    assert first.status_code == 200
    assert replay.status_code == 409
    assert replay.json() == {"detail": "Pairing was already consumed"}
    assert "token" not in replay.json()
    assert len(registry.list_devices()) == 1


def test_complete_maps_exhausted_attempts() -> None:
    client, presenter, registry, _ = auth_client(max_attempts=1)

    with client:
        started = start(client)
        correct = presenter.presented[0].code
        wrong = "000000" if correct != "000000" else "000001"
        response = client.post(
            "/api/v1/pairing/complete",
            json={"pairing_id": started.json()["pairing_id"], "code": wrong},
        )
        after_lock = client.post(
            "/api/v1/pairing/complete",
            json={"pairing_id": started.json()["pairing_id"], "code": correct},
        )

    assert response.status_code == 429
    assert after_lock.status_code == 429
    assert response.json() == {"detail": "Pairing attempts have been exhausted"}
    assert registry.list_devices() == ()


def test_pairing_public_schemas_do_not_expose_internal_secrets() -> None:
    client, _, _, _ = auth_client()

    with client:
        schema = client.get("/openapi.json").json()["components"]["schemas"]

    start_fields = schema["PairingStartResponse"]["properties"]
    complete_request_fields = schema["PairingCompleteRequest"]["properties"]
    assert set(start_fields) == {"pairing_id", "expires_at"}
    assert set(complete_request_fields) == {"pairing_id", "code"}
    assert "code_hash" not in str(schema)
    assert "token_hash" not in str(schema)
    assert "attempts_remaining" not in str(schema)

