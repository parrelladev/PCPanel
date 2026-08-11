from pathlib import Path


SCRIPT = Path("scripts/install-lifecycle.ps1").read_text(encoding="utf-8")


def test_autostart_options_require_explicit_switches() -> None:
    assert "[switch] $EnableServiceAutoStart" in SCRIPT
    assert "[switch] $EnableAgentAutoStart" in SCRIPT
    assert "[switch] $StartServiceNow" in SCRIPT


def test_default_service_mode_is_manual() -> None:
    assert 'if ($EnableServiceAutoStart) { "auto" } else { "demand" }' in SCRIPT


def test_agent_run_key_is_written_only_after_consent() -> None:
    guard = SCRIPT.index("if ($EnableAgentAutoStart)")
    write = SCRIPT.index("Set-ItemProperty", guard)
    guard_end = SCRIPT.index("\n    }", write)
    assert guard < write < guard_end
