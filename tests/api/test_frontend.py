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
    assert "Hardware telemetry" in response.text
    assert 'src="/js/app.js"' in response.text


def test_frontend_css_is_available() -> None:
    with _client() as client:
        response = client.get("/css/app.css")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/css")
    assert ".metrics" in response.text


def test_frontend_javascript_is_available() -> None:
    with _client() as client:
        response = client.get("/js/app.js")

    assert response.status_code == 200
    assert "javascript" in response.headers["content-type"]
    assert "window.location.host" in response.text
    assert '"wss:"' in response.text
