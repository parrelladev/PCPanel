from __future__ import annotations

from unittest.mock import Mock

from app.agent import tray


def test_urls_never_expose_bind_all_address(monkeypatch) -> None:
    monkeypatch.setattr(tray, "discover_lan_ipv4", lambda: "192.168.1.20")
    assert tray.local_panel_url("0.0.0.0", 8000) == "http://127.0.0.1:8000/"
    assert tray.lan_panel_url(8000) == "http://192.168.1.20:8000/"
    assert "0.0.0.0" not in tray.lan_panel_url(8000)


def test_status_mapping_uses_explicit_service_state() -> None:
    assert tray.telemetry_label("running") == "Online"
    assert tray.telemetry_label("starting") == "Service starting"
    assert tray.telemetry_label("unavailable") == "Offline"
    assert tray.telemetry_label("failed") == "Hardware unavailable"


def test_restart_uses_only_fixed_service_name(monkeypatch) -> None:
    execute = Mock(return_value=42)
    monkeypatch.setattr(tray.ctypes, "windll", Mock(shell32=Mock(ShellExecuteW=execute)))
    tray.restart_telemetry_service()
    arguments = execute.call_args.args
    assert arguments[1] == "runas"
    assert arguments[2] == "powershell.exe"
    assert "PCPanelTelemetry" in arguments[3]
    assert tray.SERVICE_NAME == "PCPanelTelemetry"


def test_exit_stops_tray_and_agent_only() -> None:
    controller = object.__new__(tray.AgentTray)
    controller._request_exit = Mock()
    icon = Mock()
    controller._exit(icon, object())
    icon.stop.assert_called_once_with()
    controller._request_exit.assert_called_once_with()
