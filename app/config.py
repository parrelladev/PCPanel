from __future__ import annotations

import math
import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(slots=True, frozen=True)
class AppSettings:
    """Application settings loaded explicitly from environment variables."""

    lhm_dll_path: Path | None = None
    telemetry_interval: float = 0.5
    host: str = "0.0.0.0"
    port: int = 8000
    enable_actions_api: bool = False
    data_dir: Path = Path("data")

    def __post_init__(self) -> None:
        if (
            not math.isfinite(self.telemetry_interval)
            or self.telemetry_interval <= 0
        ):
            raise ValueError(
                "telemetry_interval must be a finite number greater than zero"
            )

        if not 1 <= self.port <= 65535:
            raise ValueError("port must be between 1 and 65535")

        if not self.host.strip():
            raise ValueError("host must not be empty")

        if not isinstance(self.enable_actions_api, bool):
            raise TypeError("enable_actions_api must be a bool")

        if not isinstance(self.data_dir, Path):
            raise TypeError("data_dir must be a pathlib.Path")

    @classmethod
    def from_env(cls) -> AppSettings:
        """Build settings from the current process environment."""

        dll_value = os.environ.get("PCPANEL_LHM_DLL")
        dll_path = (
            Path(dll_value).expanduser()
            if dll_value and dll_value.strip()
            else None
        )

        interval_value = os.environ.get("PCPANEL_TELEMETRY_INTERVAL")
        telemetry_interval = cls._parse_float(
            "PCPANEL_TELEMETRY_INTERVAL",
            interval_value,
            default=0.5,
        )

        host = os.environ.get("PCPANEL_HOST", "0.0.0.0")

        port_value = os.environ.get("PCPANEL_PORT")
        port = cls._parse_int("PCPANEL_PORT", port_value, default=8000)

        enable_actions_api = cls._parse_bool(
            "PCPANEL_ENABLE_ACTIONS_API",
            os.environ.get("PCPANEL_ENABLE_ACTIONS_API"),
            default=False,
        )

        data_dir = cls._parse_data_dir(os.environ.get("PCPANEL_DATA_DIR"))

        return cls(
            lhm_dll_path=dll_path,
            telemetry_interval=telemetry_interval,
            host=host,
            port=port,
            enable_actions_api=enable_actions_api,
            data_dir=data_dir,
        )

    @staticmethod
    def _parse_data_dir(value: str | None) -> Path:
        if value is None:
            return Path("data")

        normalized = value.strip()
        if not normalized:
            raise ValueError("PCPANEL_DATA_DIR must not be empty")
        return Path(normalized).expanduser()

    @staticmethod
    def _parse_bool(name: str, value: str | None, *, default: bool) -> bool:
        """Parse case-insensitive ``true`` or ``false`` after trimming whitespace."""

        if value is None:
            return default

        normalized = value.strip().lower()
        if normalized == "true":
            return True
        if normalized == "false":
            return False
        raise ValueError(
            f"{name} must be either 'true' or 'false'; received {value!r}"
        )

    @staticmethod
    def _parse_float(name: str, value: str | None, *, default: float) -> float:
        if value is None:
            return default

        try:
            return float(value)
        except ValueError as exc:
            raise ValueError(
                f"{name} must be a valid number; received {value!r}"
            ) from exc

    @staticmethod
    def _parse_int(name: str, value: str | None, *, default: int) -> int:
        if value is None:
            return default

        try:
            return int(value)
        except ValueError as exc:
            raise ValueError(
                f"{name} must be a valid integer; received {value!r}"
            ) from exc
