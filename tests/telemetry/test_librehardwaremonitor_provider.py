from pathlib import Path

import pytest

from app.telemetry.providers import librehardwaremonitor as module
from app.telemetry.providers.librehardwaremonitor import LibreHardwareMonitorProvider


def touch_dll(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.touch()
    return path.resolve()


def test_default_path_prefers_dedicated_distribution_directory(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    preferred = touch_dll(
        tmp_path / "libs" / "LibreHardwareMonitor" / "LibreHardwareMonitorLib.dll"
    )
    touch_dll(tmp_path / "libs" / "LibreHardwareMonitorLib.dll")
    monkeypatch.setattr(module, "_PROJECT_ROOT", tmp_path)

    provider = LibreHardwareMonitorProvider()

    assert provider._resolve_dll_path() == preferred


def test_default_path_keeps_legacy_flat_layout_compatible(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    legacy = touch_dll(tmp_path / "libs" / "LibreHardwareMonitorLib.dll")
    monkeypatch.setattr(module, "_PROJECT_ROOT", tmp_path)

    provider = LibreHardwareMonitorProvider()

    assert provider._resolve_dll_path() == legacy


def test_missing_dll_error_lists_both_default_locations(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(module, "_PROJECT_ROOT", tmp_path)

    with pytest.raises(FileNotFoundError) as error:
        LibreHardwareMonitorProvider()._resolve_dll_path()

    message = str(error.value)
    assert str(tmp_path / "libs" / "LibreHardwareMonitor" / "LibreHardwareMonitorLib.dll") in message
    assert str(tmp_path / "libs" / "LibreHardwareMonitorLib.dll") in message
    assert "scripts/install_lhm.ps1" in message
