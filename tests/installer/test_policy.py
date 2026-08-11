from pathlib import Path


SCRIPT = Path("packaging/PCPanel.iss").read_text(encoding="utf-8")


def test_installer_contains_no_development_database_or_secrets() -> None:
    files = SCRIPT[SCRIPT.index("[Files]"):SCRIPT.index("[Registry]")]
    assert "venv" not in files.lower()
    assert "pcpanel.db" not in files.lower()
    assert "token" not in files.lower()
    assert "data\\" not in files.lower()


def test_autostart_and_firewall_require_explicit_tasks() -> None:
    assert 'Name: "serviceautostart"' in SCRIPT
    assert 'Name: "agentautostart"' in SCRIPT
    assert 'Name: "firewall"' in SCRIPT
    assert SCRIPT.count("Flags: unchecked") >= 4


def test_firewall_is_private_executable_scoped_and_local_subnet() -> None:
    rule = next(line for line in SCRIPT.splitlines() if "firewall add rule" in line)
    assert "dir=in" in rule
    assert "profile=private" in rule
    assert "remoteip=LocalSubnet" in rule
    assert "PCPanelAgent.exe" in rule


def test_service_identity_and_name_are_fixed() -> None:
    assert "PCPanelTelemetry" in SCRIPT
    assert "obj= LocalSystem" in SCRIPT
    assert "LocalService" not in SCRIPT


def test_default_uninstall_preserves_data() -> None:
    assert "MB_DEFBUTTON2" in SCRIPT
    assert "{localappdata}\\PCPanel" in SCRIPT


def test_postinstall_agent_runs_as_original_non_elevated_user() -> None:
    agent_run = next(
        line
        for line in SCRIPT.splitlines()
        if 'Filename: "{app}\\Agent\\PCPanelAgent.exe"' in line
        and "postinstall" in line
    )
    assert "runasoriginaluser" in agent_run


def test_upgrade_and_uninstall_wait_for_service_to_stop() -> None:
    assert SCRIPT.count('net.exe') >= 2
    assert SCRIPT.count('stop PCPanelTelemetry /y') >= 2
