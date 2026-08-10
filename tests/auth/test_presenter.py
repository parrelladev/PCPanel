import ast
import inspect
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from app.auth import ConsolePairingCodePresenter, PairingChallenge
from app.auth import presenter as presenter_module
from tests.auth.fakes import FakePairingCodePresenter


def challenge() -> PairingChallenge:
    return PairingChallenge(
        pairing_id=uuid4(),
        code="004271",
        expires_at=datetime(2026, 8, 10, 17, 5, tzinfo=timezone.utc),
    )


def test_fake_presenter_receives_and_captures_complete_challenge() -> None:
    expected = challenge()
    presenter = FakePairingCodePresenter()

    presenter.present(expected)

    assert presenter.presented == [expected]
    assert presenter.presented[0].code == expected.code
    assert presenter.presented[0].pairing_id == expected.pairing_id
    assert presenter.presented[0].expires_at == expected.expires_at


def test_console_presenter_writes_challenge_to_local_stdout(capsys) -> None:  # type: ignore[no-untyped-def]
    expected = challenge()

    ConsolePairingCodePresenter().present(expected)

    output = capsys.readouterr().out
    assert "PCPanel pairing request" in output
    assert str(expected.pairing_id) in output
    assert f"Pairing code: {expected.code}" in output
    assert expected.expires_at.isoformat() in output


def test_console_presenter_does_not_change_or_retain_challenge() -> None:
    expected = challenge()
    original = (
        expected.pairing_id,
        expected.code,
        expected.expires_at,
    )
    presenter = ConsolePairingCodePresenter()

    presenter.present(expected)

    assert (
        expected.pairing_id,
        expected.code,
        expected.expires_at,
    ) == original
    assert not hasattr(presenter, "__dict__")
    assert expected.code not in repr(presenter)


def test_console_presenter_does_not_use_logging() -> None:
    source = inspect.getsource(presenter_module)
    tree = ast.parse(source)

    imported_modules = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    }
    imported_from = {
        node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)
    }

    assert "logging" not in imported_modules
    assert "logging" not in imported_from


def test_console_presenter_retains_no_history_between_calls(capsys) -> None:  # type: ignore[no-untyped-def]
    presenter = ConsolePairingCodePresenter()
    first = challenge()
    second = PairingChallenge(
        pairing_id=uuid4(),
        code="483921",
        expires_at=first.expires_at + timedelta(minutes=1),
    )

    presenter.present(first)
    capsys.readouterr()
    presenter.present(second)
    second_output = capsys.readouterr().out

    assert first.code not in second_output
    assert second.code in second_output
    assert not hasattr(presenter, "__dict__")

