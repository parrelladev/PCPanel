from __future__ import annotations

import sys

from .telemetry.models import SensorReading
from .telemetry.providers.librehardwaremonitor import (
    LibreHardwareMonitorProvider,
)


def print_summary(sensors: list[SensorReading]) -> None:
    hardware = {
        (sensor.hardware_name, sensor.hardware_type)
        for sensor in sensors
    }
    sensor_types = sorted({sensor.sensor_type for sensor in sensors})

    print("PCPanel telemetry POC")
    print(f"Sensors detected: {len(sensors)}")
    print(f"Hardware devices: {len(hardware)}")
    print(
        "Sensor types: "
        + (", ".join(sensor_types) if sensor_types else "none")
    )

    representative = [
        sensor
        for sensor in sensors
        if sensor.value is not None
    ][:5]

    if not representative:
        print("Representative readings: none available")
        return

    print("Representative readings:")
    for sensor in representative:
        print(
            f"  {sensor.hardware_name} | "
            f"{sensor.sensor_name} ({sensor.sensor_type}): "
            f"{sensor.value:.2f}"
        )


def main() -> int:
    try:
        with LibreHardwareMonitorProvider() as provider:
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

    print_summary(sensors)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
