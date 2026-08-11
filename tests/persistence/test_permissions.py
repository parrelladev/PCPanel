from pathlib import Path
from unittest.mock import Mock

from app.persistence.permissions import harden_user_data_directory


def test_windows_acl_is_user_and_system_only(monkeypatch) -> None:
    run = Mock()
    monkeypatch.setattr("app.persistence.permissions.os.name", "nt")
    monkeypatch.setattr(
        "app.persistence.permissions.current_user_sid",
        lambda: "S-1-5-21-1-2-3-1001",
    )
    monkeypatch.setattr("app.persistence.permissions.subprocess.run", run)

    harden_user_data_directory(Path(r"C:\Users\User\AppData\Local\PCPanel"))

    argv = run.call_args.args[0]
    assert argv[0] == "icacls.exe"
    assert "/inheritance:r" in argv
    assert "*S-1-5-21-1-2-3-1001:(OI)(CI)F" in argv
    assert "*S-1-5-18:(OI)(CI)F" in argv
    assert not any("Everyone" in value or "S-1-1-0" in value for value in argv)
    assert run.call_args.kwargs["shell"] is False
