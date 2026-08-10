from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any

from ..models import SensorReading
from .base import TelemetryProvider


_DLL_NAME = "LibreHardwareMonitorLib.dll"
_DLL_ENV_VAR = "PCPANEL_LHM_DLL"
_PROJECT_ROOT = Path(__file__).resolve().parents[3]
_DEFAULT_DLL_PATHS = (
    Path("libs") / "LibreHardwareMonitor" / _DLL_NAME,
    Path("libs") / _DLL_NAME,
)


class LibreHardwareMonitorProvider(TelemetryProvider):
    """Telemetry provider backed by LibreHardwareMonitorLib on Windows."""

    def __init__(self, dll_path: str | Path | None = None) -> None:
        self._configured_dll_path = Path(dll_path).expanduser() if dll_path else None
        self._resolved_dll_path: Path | None = None
        self._computer_type: Any | None = None
        self._computer: Any | None = None

    def open(self) -> None:
        """Load LibreHardwareMonitor and open a Computer instance."""

        if self._computer is not None:
            return

        computer_type = self._get_computer_type()
        computer = computer_type()

        computer.IsCpuEnabled = True
        computer.IsGpuEnabled = True
        computer.IsMotherboardEnabled = True
        computer.IsMemoryEnabled = True
        computer.IsStorageEnabled = True
        computer.IsNetworkEnabled = True

        # Keep self._computer unset until Open() succeeds. If LibreHardwareMonitor
        # raises here, a subsequent call to open() can retry cleanly.
        computer.Open()
        self._computer = computer

    def close(self) -> None:
        """Close the current Computer instance. Repeated calls are harmless."""

        computer = self._computer
        if computer is None:
            return

        # Mark the provider closed before invoking external cleanup so our
        # Python-side state remains consistent even if Close() raises.
        self._computer = None
        computer.Close()

    def update(self) -> None:
        """Refresh all hardware and subhardware currently exposed by the library."""

        computer = self._require_open_computer()

        for hardware in computer.Hardware:
            self._update_hardware_tree(hardware)

    def get_sensors(self) -> list[SensorReading]:
        """Return a Python-only snapshot of the sensors in the current state."""

        computer = self._require_open_computer()
        readings: list[SensorReading] = []

        for hardware in computer.Hardware:
            self._collect_sensor_tree(hardware, readings)

        return readings

    def _get_computer_type(self) -> Any:
        if self._computer_type is not None:
            return self._computer_type

        if sys.platform != "win32":
            raise OSError(
                "LibreHardwareMonitorProvider requires Windows. "
                f"Current platform: {sys.platform!r}."
            )

        dll_path = self._resolve_dll_path()
        self._load_netfx_runtime()

        try:
            import clr
        except ImportError as exc:
            raise RuntimeError(
                "Failed to import the 'clr' module provided by pythonnet. "
                "Install the dependencies from requirements.txt and make sure "
                "the unrelated PyPI package named 'clr' is not shadowing pythonnet."
            ) from exc

        if not hasattr(clr, "AddReference"):
            raise RuntimeError(
                "The imported 'clr' module does not provide AddReference(). "
                "Ensure that 'clr' comes from pythonnet, not from another package."
            )

        # Python.NET searches sys.path when resolving managed assemblies.
        # Keep the LibreHardwareMonitor directory available so dependencies
        # shipped next to the main DLL can also be resolved later/lazily.
        assembly_dir = str(dll_path.parent)
        if assembly_dir not in sys.path:
            sys.path.insert(0, assembly_dir)

        try:
            from System import BadImageFormatException
            from System.IO import FileLoadException, FileNotFoundException
        except ImportError as exc:
            raise RuntimeError(
                "The .NET Framework runtime was loaded, but core System assemblies "
                "could not be imported through pythonnet."
            ) from exc

        try:
            clr.AddReference(str(dll_path))
        except (FileNotFoundException, FileLoadException, BadImageFormatException) as exc:
            raise RuntimeError(
                "Failed to load LibreHardwareMonitorLib.dll. "
                f"Path: {dll_path}. Ensure that you are using a compatible "
                ".NET Framework build (net472 for this POC), that its dependent "
                "DLLs are present beside it, and that Python/.NET architectures "
                "are compatible."
            ) from exc

        try:
            from LibreHardwareMonitor.Hardware import Computer
        except ImportError as exc:
            raise RuntimeError(
                "LibreHardwareMonitorLib.dll was referenced, but "
                "'LibreHardwareMonitor.Hardware.Computer' could not be imported. "
                "Verify that the DLL is a valid LibreHardwareMonitorLib build."
            ) from exc

        self._computer_type = Computer
        return Computer

    @staticmethod
    def _load_netfx_runtime() -> None:
        try:
            from pythonnet import load
        except ImportError as exc:
            raise RuntimeError(
                "pythonnet is not installed. Install the dependencies from "
                "requirements.txt before using LibreHardwareMonitorProvider."
            ) from exc

        try:
            # The POC intentionally targets the LibreHardwareMonitor net472 build.
            # pythonnet requires the runtime to be selected before importing clr.
            # Calling load() again after a successful load is harmless.
            load("netfx")
        except RuntimeError as exc:
            raise RuntimeError(
                "Failed to initialize the .NET Framework runtime through pythonnet. "
                "Install .NET Framework 4.7.2 or newer and verify that the Python "
                "process architecture is compatible with the runtime."
            ) from exc

    def _resolve_dll_path(self) -> Path:
        if self._resolved_dll_path is not None:
            return self._resolved_dll_path

        if self._configured_dll_path is not None:
            dll_path = self._configured_dll_path.resolve()
            if not dll_path.is_file():
                raise FileNotFoundError(
                    f"LibreHardwareMonitor DLL not found at configured path: {dll_path}"
                )
            self._resolved_dll_path = dll_path
            return dll_path

        env_path = os.environ.get(_DLL_ENV_VAR)
        if env_path:
            dll_path = Path(env_path).expanduser().resolve()
            if not dll_path.is_file():
                raise FileNotFoundError(
                    f"{_DLL_ENV_VAR} points to a missing file: {dll_path}"
                )
            self._resolved_dll_path = dll_path
            return dll_path

        searched_paths: list[Path] = []
        for relative_path in _DEFAULT_DLL_PATHS:
            dll_path = (_PROJECT_ROOT / relative_path).resolve()
            searched_paths.append(dll_path)
            if dll_path.is_file():
                self._resolved_dll_path = dll_path
                return dll_path

        raise FileNotFoundError(
            "LibreHardwareMonitorLib.dll was not found. "
            "Pass dll_path=..., set the PCPANEL_LHM_DLL environment variable, "
            "or run scripts/install_lhm.ps1.\n"
            "Searched:\n  - " + "\n  - ".join(map(str, searched_paths))
        )

    def _require_open_computer(self) -> Any:
        if self._computer is None:
            raise RuntimeError(
                "LibreHardwareMonitorProvider is not open. "
                "Call open() first or use it as a context manager."
            )
        return self._computer

    def _update_hardware_tree(self, hardware: Any) -> None:
        hardware.Update()

        for subhardware in hardware.SubHardware:
            self._update_hardware_tree(subhardware)

    def _collect_sensor_tree(
        self,
        hardware: Any,
        readings: list[SensorReading],
    ) -> None:
        hardware_identifier = str(hardware.Identifier)
        hardware_name = str(hardware.Name)
        hardware_type = str(hardware.HardwareType)

        for sensor in hardware.Sensors:
            readings.append(
                SensorReading(
                    hardware_identifier=hardware_identifier,
                    hardware_name=hardware_name,
                    hardware_type=hardware_type,
                    sensor_identifier=str(sensor.Identifier),
                    sensor_name=str(sensor.Name),
                    sensor_type=str(sensor.SensorType),
                    value=self._to_optional_float(sensor.Value),
                    min_value=self._to_optional_float(sensor.Min),
                    max_value=self._to_optional_float(sensor.Max),
                )
            )

        for subhardware in hardware.SubHardware:
            self._collect_sensor_tree(subhardware, readings)

    @staticmethod
    def _to_optional_float(value: Any | None) -> float | None:
        if value is None:
            return None
        return float(value)
