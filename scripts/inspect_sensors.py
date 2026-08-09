from __future__ import annotations

import argparse
import sys
from collections import defaultdict
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.telemetry.models import SensorReading
from app.telemetry.providers.librehardwaremonitor import (
    LibreHardwareMonitorProvider,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Inspect hardware and sensors exposed by LibreHardwareMonitor."
        )
    )
    parser.add_argument(
        "--dll-path",
        type=Path,
        default=None,
        help=(
            "Path to LibreHardwareMonitorLib.dll. "
            "If omitted, the provider uses its normal discovery strategy."
        ),
    )
    return parser.parse_args()


def format_value(value: float | None) -> str:
    if value is None:
        return "-"
    return f"{value:.2f}"


def print_sensors(sensors: list[SensorReading]) -> None:
    if not sensors:
        print("No sensors were reported by LibreHardwareMonitor.")
        return

    grouped: dict[
        tuple[str, str],
        dict[str, list[SensorReading]],
    ] = defaultdict(lambda: defaultdict(list))

    for sensor in sensors:
        hardware_key = (sensor.hardware_name, sensor.hardware_type)
        grouped[hardware_key][sensor.sensor_type].append(sensor)

    print(f"Detected {len(sensors)} sensor(s).")

    for (hardware_name, hardware_type), sensor_types in grouped.items():
        print()
        print("=" * 80)
        print(f"{hardware_name} [{hardware_type}]")
        print("=" * 80)

        for sensor_type, readings in sensor_types.items():
            print()
            print(f"  {sensor_type}")
            print(f"  {'Sensor':<38} {'Current':>12} {'Min':>12} {'Max':>12}")
            print(f"  {'-' * 38} {'-' * 12} {'-' * 12} {'-' * 12}")

            for reading in readings:
                print(
                    f"  {reading.sensor_name:<38} "
                    f"{format_value(reading.value):>12} "
                    f"{format_value(reading.min_value):>12} "
                    f"{format_value(reading.max_value):>12}"
                )


def main() -> int:
    args = parse_args()

    try:
        with LibreHardwareMonitorProvider(dll_path=args.dll_path) as provider:
            provider.update()
            sensors = provider.get_sensors()
    except FileNotFoundError as exc:
        print(f"DLL error: {exc}", file=sys.stderr)
        return 2
    except OSError as exc:
        print(f"Platform error: {exc}", file=sys.stderr)
        return 3
    except RuntimeError as exc:
        print(f"Provider initialization error: {exc}", file=sys.stderr)
        return 4

    print_sensors(sensors)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
