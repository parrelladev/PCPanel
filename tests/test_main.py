from __future__ import annotations

from unittest.mock import Mock

import pytest
from fastapi import FastAPI
from uvicorn import Config

from app.config import AppSettings
from app.main import build_app, main


def test_build_app_composes_runtime_without_starting_manager(monkeypatch) -> None:
    provider = Mock()
    manager = Mock()
    application = FastAPI()
    settings = AppSettings(
        lhm_dll_path=None,
        telemetry_interval=1.25,
        host="127.0.0.1",
        port=9000,
    )
    provider_factory = Mock(return_value=provider)
    manager_factory = Mock(return_value=manager)
    action_service = Mock()
    action_service_factory = Mock(return_value=action_service)
    app_factory = Mock(return_value=application)
    database = Mock()
    database_factory = Mock(return_value=database)
    device_store = Mock()
    device_store_factory = Mock(return_value=device_store)
    action_store = Mock()
    action_store.load_actions.return_value = ()
    action_store_factory = Mock(return_value=action_store)
    device_registry = Mock()
    registry_factory = Mock(return_value=device_registry)
    token_service = Mock()
    token_service_factory = Mock(return_value=token_service)
    pairing_service = Mock()
    pairing_service_factory = Mock(return_value=pairing_service)
    monkeypatch.setattr("app.main.LibreHardwareMonitorProvider", provider_factory)
    monkeypatch.setattr("app.main.TelemetryManager", manager_factory)
    monkeypatch.setattr("app.main.create_action_service", action_service_factory)
    monkeypatch.setattr("app.main.create_app", app_factory)
    monkeypatch.setattr("app.main.Database", database_factory)
    monkeypatch.setattr("app.main.SQLiteDeviceStore", device_store_factory)
    monkeypatch.setattr("app.main.SQLiteActionStore", action_store_factory)
    monkeypatch.setattr("app.main.DeviceRegistry", registry_factory)
    monkeypatch.setattr("app.main.TokenService", token_service_factory)
    monkeypatch.setattr("app.main.PairingService", pairing_service_factory)

    result = build_app(settings)

    assert result is application
    provider_factory.assert_called_once_with(dll_path=None)
    manager_factory.assert_called_once_with(provider, interval=1.25)
    action_store_factory.assert_called_once_with(database)
    action_store.load_actions.assert_called_once_with()
    action_service_factory.assert_called_once_with(actions=())
    database_factory.assert_called_once_with(settings.data_dir)
    database.initialize.assert_called_once_with()
    device_store_factory.assert_called_once_with(database)
    registry_factory.assert_called_once_with(store=device_store)
    token_service_factory.assert_called_once_with()
    pairing_service_factory.assert_called_once_with(device_registry, token_service)
    app_factory.assert_called_once_with(
        manager,
        action_service=action_service,
        enable_actions_api=False,
        token_service=token_service,
        device_registry=device_registry,
        pairing_service=pairing_service,
    )
    manager.start.assert_not_called()


def test_main_runs_uvicorn_with_configured_network_settings(monkeypatch) -> None:
    settings = AppSettings(host="192.168.1.20", port=9100)
    application = FastAPI()
    monkeypatch.setattr("app.main.AppSettings.from_env", Mock(return_value=settings))
    build = Mock(return_value=application)
    run = Mock()
    monkeypatch.setattr("app.main.build_app", build)
    monkeypatch.setattr("app.main.uvicorn.run", run)

    result = main()

    assert result is None
    build.assert_called_once_with(settings)
    run.assert_called_once_with(application, host="192.168.1.20", port=9100)


def test_database_initialization_failure_aborts_before_stores_or_fastapi(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    failure = RuntimeError("database initialization failed")
    database = Mock()
    database.initialize.side_effect = failure
    action_store_factory = Mock()
    device_store_factory = Mock()
    app_factory = Mock()
    monkeypatch.setattr("app.main.LibreHardwareMonitorProvider", Mock())
    monkeypatch.setattr("app.main.TelemetryManager", Mock())
    monkeypatch.setattr("app.main.Database", Mock(return_value=database))
    monkeypatch.setattr("app.main.SQLiteActionStore", action_store_factory)
    monkeypatch.setattr("app.main.SQLiteDeviceStore", device_store_factory)
    monkeypatch.setattr("app.main.create_app", app_factory)

    with pytest.raises(RuntimeError, match="database initialization failed"):
        build_app(AppSettings())

    action_store_factory.assert_not_called()
    device_store_factory.assert_not_called()
    app_factory.assert_not_called()


def test_uvicorn_has_a_websocket_protocol_available() -> None:
    config = Config(FastAPI(), ws="auto")

    config.load()

    assert config.ws_protocol_class is not None
