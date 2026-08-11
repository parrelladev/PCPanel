from __future__ import annotations

from uuid import uuid4

from app.agent.single_instance import AgentInstanceLock


def test_agent_mutex_rejects_second_instance_in_same_session() -> None:
    mutex_name = rf"Local\PCPanelAgent-Test-{uuid4()}"
    first = AgentInstanceLock(mutex_name)
    second = AgentInstanceLock(mutex_name)

    assert first.acquire() is True
    try:
        assert second.acquire() is False
    finally:
        first.release()

    assert second.acquire() is True
    second.release()
