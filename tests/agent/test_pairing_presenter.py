from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import Mock
from uuid import uuid4

from app.agent.pairing import WindowsPairingCodePresenter
from app.auth.models import PairingChallenge


def test_pairing_code_is_presented_on_a_transient_local_thread(monkeypatch) -> None:
    thread = Mock()
    thread_type = Mock(return_value=thread)
    monkeypatch.setattr("app.agent.pairing.threading.Thread", thread_type)
    challenge = PairingChallenge(
        pairing_id=uuid4(),
        code="042731",
        expires_at=datetime(2026, 8, 11, 12, 30, tzinfo=timezone.utc),
    )

    WindowsPairingCodePresenter().present(challenge)

    assert thread_type.call_args.kwargs["daemon"] is True
    assert challenge.code in thread_type.call_args.kwargs["args"][0]
    thread.start.assert_called_once_with()


def test_agent_composition_uses_windows_presenter(monkeypatch, tmp_path) -> None:
    from app.agent.composition import build_agent_app
    from app.config import AppSettings

    monkeypatch.setattr("app.agent.composition.TelemetryPipeClient", Mock())
    application = build_agent_app(AppSettings(data_dir=tmp_path))

    assert isinstance(
        application.state.pairing_code_presenter,
        WindowsPairingCodePresenter,
    )
