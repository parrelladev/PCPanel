from __future__ import annotations

from pathlib import Path

import pytest

from app.config import AppSettings


ENVIRONMENT_VARIABLES = (
    "PCPANEL_LHM_DLL",
    "PCPANEL_TELEMETRY_INTERVAL",
    "PCPANEL_HOST",
    "PCPANEL_PORT",
    "PCPANEL_ENABLE_ACTIONS_API",
    "PCPANEL_DATA_DIR",
)


def _clear_settings_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ENVIRONMENT_VARIABLES:
        monkeypatch.delenv(name, raising=False)


def test_from_env_uses_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_settings_environment(monkeypatch)

    settings = AppSettings.from_env()

    assert settings == AppSettings(
        lhm_dll_path=None,
        telemetry_interval=0.5,
        host="0.0.0.0",
        port=8000,
        enable_actions_api=False,
        data_dir=Path("data"),
    )


def test_from_env_parses_valid_values(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_settings_environment(monkeypatch)
    monkeypatch.setenv("PCPANEL_LHM_DLL", "C:/PCPanel/LibreHardwareMonitorLib.dll")
    monkeypatch.setenv("PCPANEL_TELEMETRY_INTERVAL", "1.25")
    monkeypatch.setenv("PCPANEL_HOST", "192.168.1.10")
    monkeypatch.setenv("PCPANEL_PORT", "9000")

    settings = AppSettings.from_env()

    assert settings.lhm_dll_path == Path("C:/PCPanel/LibreHardwareMonitorLib.dll")
    assert settings.telemetry_interval == 1.25
    assert settings.host == "192.168.1.10"
    assert settings.port == 9000
    assert settings.enable_actions_api is False
    assert settings.data_dir == Path("data")


def test_from_env_uses_default_data_dir(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_settings_environment(monkeypatch)

    settings = AppSettings.from_env()

    assert settings.data_dir == Path("data")
    assert not settings.data_dir.is_absolute()
    assert settings.data_dir / "pcpanel.db" == Path("data/pcpanel.db")


def test_from_env_parses_custom_relative_data_dir(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _clear_settings_environment(monkeypatch)
    monkeypatch.setenv("PCPANEL_DATA_DIR", "./runtime/local-data")

    settings = AppSettings.from_env()

    assert isinstance(settings.data_dir, Path)
    assert settings.data_dir == Path("runtime/local-data")
    assert not settings.data_dir.is_absolute()


def test_from_env_preserves_absolute_data_dir(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _clear_settings_environment(monkeypatch)
    absolute_data_dir = tmp_path / "pcpanel-data"
    monkeypatch.setenv("PCPANEL_DATA_DIR", str(absolute_data_dir))

    settings = AppSettings.from_env()

    assert settings.data_dir == absolute_data_dir
    assert settings.data_dir.is_absolute()


@pytest.mark.parametrize("value", ["", "   "])
def test_from_env_rejects_empty_data_dir(
    monkeypatch: pytest.MonkeyPatch,
    value: str,
) -> None:
    _clear_settings_environment(monkeypatch)
    monkeypatch.setenv("PCPANEL_DATA_DIR", value)

    with pytest.raises(ValueError, match="PCPANEL_DATA_DIR must not be empty"):
        AppSettings.from_env()


@pytest.mark.parametrize("value", ["true", "TRUE", " True "])
def test_from_env_enables_actions_api_case_insensitively(
    monkeypatch: pytest.MonkeyPatch,
    value: str,
) -> None:
    _clear_settings_environment(monkeypatch)
    monkeypatch.setenv("PCPANEL_ENABLE_ACTIONS_API", value)

    assert AppSettings.from_env().enable_actions_api is True


@pytest.mark.parametrize("value", ["false", "FALSE", " False "])
def test_from_env_disables_actions_api_case_insensitively(
    monkeypatch: pytest.MonkeyPatch,
    value: str,
) -> None:
    _clear_settings_environment(monkeypatch)
    monkeypatch.setenv("PCPANEL_ENABLE_ACTIONS_API", value)

    assert AppSettings.from_env().enable_actions_api is False


@pytest.mark.parametrize("value", ["", "1", "yes", "enabled", "invalid"])
def test_from_env_rejects_invalid_actions_api_flag(
    monkeypatch: pytest.MonkeyPatch,
    value: str,
) -> None:
    _clear_settings_environment(monkeypatch)
    monkeypatch.setenv("PCPANEL_ENABLE_ACTIONS_API", value)

    with pytest.raises(
        ValueError,
        match="PCPANEL_ENABLE_ACTIONS_API.*'true'.*'false'",
    ):
        AppSettings.from_env()


@pytest.mark.parametrize("value", ["0", "-0.1", "invalid", "nan", "inf"])
def test_from_env_rejects_invalid_telemetry_interval(
    monkeypatch: pytest.MonkeyPatch,
    value: str,
) -> None:
    _clear_settings_environment(monkeypatch)
    monkeypatch.setenv("PCPANEL_TELEMETRY_INTERVAL", value)

    with pytest.raises(ValueError, match="PCPANEL_TELEMETRY_INTERVAL|telemetry_interval"):
        AppSettings.from_env()


@pytest.mark.parametrize("value", ["0", "65536", "invalid", "8000.5"])
def test_from_env_rejects_invalid_port(
    monkeypatch: pytest.MonkeyPatch,
    value: str,
) -> None:
    _clear_settings_environment(monkeypatch)
    monkeypatch.setenv("PCPANEL_PORT", value)

    with pytest.raises(ValueError, match="PCPANEL_PORT|port"):
        AppSettings.from_env()


def test_from_env_treats_empty_dll_path_as_absent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _clear_settings_environment(monkeypatch)
    monkeypatch.setenv("PCPANEL_LHM_DLL", "   ")

    settings = AppSettings.from_env()

    assert settings.lhm_dll_path is None
