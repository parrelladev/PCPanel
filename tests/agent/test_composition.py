from __future__ import annotations

import ast
from datetime import datetime, timezone
from pathlib import Path

from fastapi.testclient import TestClient

from app.agent.composition import build_agent_app
from app.config import AppSettings
from app.ipc.protocol import IPCUnavailableError
from app.telemetry.models import TelemetrySnapshot


class OfflineThenOnlineClient:
    snapshot = TelemetrySnapshot(
        sequence=8,
        captured_at=datetime(2026, 8, 10, tzinfo=timezone.utc),
        sensors=(),
    )

    def __init__(self) -> None:
        self.online = False

    def get_status(self) -> str:
        if not self.online:
            raise IPCUnavailableError("service absent")
        return "telemetry_available"

    def get_snapshot(self) -> TelemetrySnapshot:
        if not self.online:
            raise IPCUnavailableError("service absent")
        return self.snapshot


def test_agent_stays_alive_without_service_and_recovers(monkeypatch, tmp_path) -> None:
    pipe_client = OfflineThenOnlineClient()
    monkeypatch.setattr(
        "app.agent.composition.TelemetryPipeClient",
        lambda **_kwargs: pipe_client,
    )
    application = build_agent_app(AppSettings(data_dir=tmp_path))

    with TestClient(application) as client:
        assert client.get("/").status_code == 200
        assert client.get("/api/v1/health").json()["telemetry_status"] == "unavailable"
        assert client.get("/api/v1/telemetry").status_code == 503
        assert client.get("/api/v1/metrics").status_code == 503

        pipe_client.online = True
        assert client.get("/api/v1/health").json()["telemetry_status"] == "running"
        assert client.get("/api/v1/telemetry").json()["sequence"] == 8
        assert client.get("/api/v1/metrics").json()["sequence"] == 8

    assert application.state.telemetry_manager is None


def test_agent_runtime_does_not_import_hardware_provider_or_service_control() -> None:
    imports: list[str] = []
    for path in Path("app/agent").glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imports.append(node.module)

    joined = " ".join(imports).lower()
    assert "librehardwaremonitor" not in joined
    assert "app.service" not in joined
    assert "windows_service" not in joined
