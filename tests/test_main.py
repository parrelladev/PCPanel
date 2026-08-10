from __future__ import annotations

from unittest.mock import Mock

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
    app_factory = Mock(return_value=application)
    monkeypatch.setattr("app.main.LibreHardwareMonitorProvider", provider_factory)
    monkeypatch.setattr("app.main.TelemetryManager", manager_factory)
    monkeypatch.setattr("app.main.create_app", app_factory)

    result = build_app(settings)

    assert result is application
    provider_factory.assert_called_once_with(dll_path=None)
    manager_factory.assert_called_once_with(provider, interval=1.25)
    app_factory.assert_called_once_with(manager)
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


def test_uvicorn_has_a_websocket_protocol_available() -> None:
    config = Config(FastAPI(), ws="auto")

    config.load()

    assert config.ws_protocol_class is not None
