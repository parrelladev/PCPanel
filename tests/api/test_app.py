from __future__ import annotations

import asyncio
from unittest.mock import Mock

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
