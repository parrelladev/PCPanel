from __future__ import annotations

from unittest.mock import Mock

from fastapi.testclient import TestClient

from app.api.app import create_app
from app.telemetry.manager import TelemetryManager, TelemetryStatus


def _client() -> TestClient:
    manager = Mock(spec=TelemetryManager)
    manager.status = TelemetryStatus.RUNNING
    return TestClient(create_app(manager))


def test_root_serves_frontend_html() -> None:
    with _client() as client:
        response = client.get("/")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert "Performance do hardware" in response.text
    assert 'type="module" src="/js/app.js?v=m9a10-20260810-1"' in response.text


def test_frontend_css_is_available() -> None:
    with _client() as client:
        response = client.get("/css/app.css")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/css")
    assert '@import url("/css/variables.css?v=m9a5-20260810-1")' in response.text
    assert '@import url("/css/layout.css?v=m9a5-20260810-1")' in response.text
    assert '@import url("/css/components.css?v=m9a5-20260810-1")' in response.text


def test_frontend_javascript_is_available() -> None:
    with _client() as client:
        response = client.get("/js/app.js")

    assert response.status_code == 200
    assert "javascript" in response.headers["content-type"]
    assert 'from "./services/websocket-telemetry.js"' in response.text
    assert 'from "./state/telemetry.js"' in response.text
    assert '"cpu.temperature"' in response.text
    assert '"gpu.load"' in response.text
    assert '"memory.load"' in response.text


def test_frontend_module_files_are_available() -> None:
    module_paths = (
        "/js/state/telemetry.js",
        "/js/state/auth.js",
        "/js/services/websocket-telemetry.js",
        "/js/services/authenticated-fetch.js",
        "/js/services/auth-bootstrap.js",
        "/js/services/pairing.js",
        "/js/services/actions-catalog.js",
        "/js/services/action-execution.js",
        "/js/services/fullscreen.js",
        "/js/services/theme-preference.js",
        "/js/components/cat-gauge.js",
        "/js/components/apps-launcher.js",
        "/js/components/system-status.js",
        "/js/components/dashboard-metrics.js",
        "/js/components/pairing-view.js",
        "/js/components/thermal-state.js",
        "/js/components/hardware-vendor.js",
    )

    with _client() as client:
        responses = [client.get(path) for path in module_paths]

    assert all(response.status_code == 200 for response in responses)
    assert all(
        "javascript" in response.headers["content-type"]
        for response in responses
    )


def test_frontend_websocket_uses_only_canonical_metrics_contract() -> None:
    with _client() as client:
        response = client.get("/js/services/websocket-telemetry.js")

    assert response.status_code == 200
    assert "/ws/v1/metrics" in response.text
    assert "/ws/v1/telemetry" not in response.text
    assert "browserWindow.location.host" in response.text
    assert '"wss:"' in response.text
    assert '"reconnecting"' in response.text
    assert '"offline"' in response.text
    assert '"visibilitychange"' in response.text
    assert "RECONNECT_DELAYS_MS" in response.text


def test_frontend_exposes_installable_fullscreen_manifest_and_icon() -> None:
    with _client() as client:
        html = client.get("/")
        manifest = client.get("/manifest.webmanifest")
        icon = client.get("/assets/pcpanel-icon.svg")

    assert 'rel="manifest" href="/manifest.webmanifest"' in html.text
    assert 'id="fullscreen-toggle"' in html.text
    assert manifest.status_code == 200
    assert manifest.headers["content-type"].startswith("application/manifest+json")
    assert manifest.json()["display"] == "fullscreen"
    assert manifest.json()["start_url"] == "/"
    assert icon.status_code == 200
    assert "svg" in icon.headers["content-type"]


def test_frontend_has_no_raw_sensor_resolution_terms() -> None:
    forbidden_terms = (
        "CPU Package",
        "CPU Total",
        "GPU Core",
        "GpuNvidia",
        "GpuAmd",
        "GpuIntel",
        "D3D",
        "selectMetric",
        "resolveMetrics",
    )
    module_paths = (
        "/js/app.js",
        "/js/state/telemetry.js",
        "/js/services/websocket-telemetry.js",
        "/js/components/cat-gauge.js",
        "/js/components/thermal-state.js",
    )

    with _client() as client:
        source = "\n".join(client.get(path).text for path in module_paths)

    assert all(term not in source for term in forbidden_terms)


def test_unpaired_frontend_has_mobile_pairing_form_without_secret_output() -> None:
    with _client() as client:
        response = client.get("/")

    assert 'id="pairing-name-form"' in response.text
    assert 'name="device_name"' in response.text
    assert 'maxlength="100"' in response.text
    assert 'id="pairing-code-form"' in response.text
    assert 'inputmode="numeric"' in response.text
    assert 'autocomplete="one-time-code"' in response.text
    assert 'maxlength="6"' in response.text
    assert "token" not in response.text.lower()


def test_apps_tab_has_real_launcher_states_and_preserves_navigation() -> None:
    with _client() as client:
        response = client.get("/")

    assert 'id="apps-grid"' in response.text
    assert 'id="apps-status"' in response.text
    assert 'id="apps-refresh"' in response.text
    assert 'data-target="performance"' in response.text
    assert 'data-target="apps"' in response.text
    assert 'data-target="system"' in response.text
    assert "reservada para uma próxima etapa" not in response.text


def test_system_tab_is_status_only_and_contains_no_mutating_controls() -> None:
    with _client() as client:
        response = client.get("/")

    assert 'id="system-device-name"' in response.text
    assert 'id="system-device-status"' in response.text
    assert 'id="system-server-status"' in response.text
    assert 'id="system-actions-status"' in response.text
    assert 'id="system-telemetry-status"' in response.text
    forbidden_actions = ("Shutdown", "Restart", "Sleep", "Lock Windows", "Desparear")
    assert all(action not in response.text for action in forbidden_actions)
