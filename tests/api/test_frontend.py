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
    assert 'type="module" src="/js/app.js"' in response.text


def test_frontend_css_is_available() -> None:
    with _client() as client:
        response = client.get("/css/app.css")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/css")
    assert '@import url("/css/variables.css")' in response.text
    assert '@import url("/css/layout.css")' in response.text
    assert '@import url("/css/components.css")' in response.text


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
        "/js/services/websocket-telemetry.js",
        "/js/components/cat-gauge.js",
        "/js/components/thermal-state.js",
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
    assert "window.location.host" in response.text
    assert '"wss:"' in response.text


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
