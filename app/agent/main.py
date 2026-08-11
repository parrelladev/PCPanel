from __future__ import annotations

import argparse
import tempfile
from pathlib import Path

import uvicorn

from ..api.app import WEB_ROOT
from ..config import AppSettings
from .composition import build_agent_app
from .single_instance import AgentInstanceLock, notify_existing_instance
from .telemetry import AgentTelemetrySource
from .tray import AgentTray
from .shutdown import AgentShutdownMonitor, request_existing_agent_shutdown


def main() -> None:
    parser = argparse.ArgumentParser(description="PCPanel Agent")
    parser.add_argument("--smoke-test", action="store_true")
    parser.add_argument("--shutdown-existing", action="store_true")
    args = parser.parse_args()
    if args.shutdown_existing:
        request_existing_agent_shutdown()
        return
    if args.smoke_test:
        with tempfile.TemporaryDirectory(prefix="pcpanel-agent-smoke-") as directory:
            build_agent_app(AppSettings(data_dir=Path(directory)))
            if not (WEB_ROOT / "index.html").is_file():
                raise RuntimeError("Packaged web assets are unavailable")
        print("PCPanelAgent smoke test passed")
        return
    instance_lock = AgentInstanceLock()
    if not instance_lock.acquire():
        notify_existing_instance()
        return
    try:
        settings = AppSettings.from_env()
        application = build_agent_app(settings)
        source = application.state.telemetry_source
        if not isinstance(source, AgentTelemetrySource):
            raise RuntimeError("Agent telemetry source is invalid")
        server = uvicorn.Server(uvicorn.Config(
            application,
            host=settings.host,
            port=settings.port,
            log_config=None,
        ))
        tray = AgentTray(source, settings.host, settings.port, lambda: setattr(server, "should_exit", True))
        shutdown_monitor = AgentShutdownMonitor(lambda: setattr(server, "should_exit", True))
        shutdown_monitor.start()
        tray.start()
        try:
            server.run()
        finally:
            tray.stop()
            shutdown_monitor.stop()
    finally:
        instance_lock.release()


if __name__ == "__main__":
    main()
