from __future__ import annotations

import asyncio
from unittest.mock import Mock

from fastapi.testclient import TestClient

from app.actions import ActionService
from app.api.app import create_app
from app.telemetry.manager import TelemetryManager


def test_lifespan_starts_and_stops_shared_manager() -> None:
    manager = Mock(spec=TelemetryManager)
    application = create_app(manager)

    async def exercise_lifespan() -> None:
        assert application.state.telemetry_manager is manager

        async with application.router.lifespan_context(application):
            manager.start.assert_called_once_with()
            manager.stop.assert_not_called()
            assert application.state.telemetry_manager is manager

        manager.stop.assert_called_once_with()

    asyncio.run(exercise_lifespan())


def test_app_composes_one_shared_auth_runtime() -> None:
    manager = Mock(spec=TelemetryManager)
    application = create_app(manager)

    registry = application.state.device_registry
    pairing = application.state.pairing_service

    assert application.state.device_registry is registry
    assert application.state.pairing_service is pairing
    assert pairing._registry is registry


def test_app_keeps_injected_action_service_shared_across_requests() -> None:
    manager = Mock(spec=TelemetryManager)
    action_service = Mock(spec=ActionService)
    application = create_app(manager, action_service=action_service)

    with TestClient(application) as client:
        assert client.get("/").status_code == 200
        assert client.get("/").status_code == 200

    assert application.state.action_service is action_service


def test_app_composes_default_action_service_only_once(monkeypatch) -> None:
    manager = Mock(spec=TelemetryManager)
    action_service = Mock(spec=ActionService)
    factory = Mock(return_value=action_service)
    monkeypatch.setattr("app.api.app.create_action_service", factory)

    application = create_app(manager)
    with TestClient(application) as client:
        assert client.get("/").status_code == 200
        assert client.get("/").status_code == 200

    factory.assert_called_once_with()
    assert application.state.action_service is action_service


def test_actions_api_flag_registers_protected_actions_routes() -> None:
    manager = Mock(spec=TelemetryManager)
    application = create_app(manager, enable_actions_api=True)

    assert application.state.enable_actions_api is True
    with TestClient(application) as client:
        assert client.get("/api/v1/actions").status_code == 401
        assert client.post("/api/v1/actions/notepad/execute").status_code == 401
