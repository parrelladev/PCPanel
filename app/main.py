from __future__ import annotations

import sys

from .telemetry.manager import TelemetryManager, TelemetryStatus
from .telemetry.models import TelemetrySnapshot
from .telemetry.providers.librehardwaremonitor import (
    LibreHardwareMonitorProvider,
)


def print_summary(snapshot: TelemetrySnapshot) -> None:
    sensors = snapshot.sensors
    hardware = {
        sensor.hardware_identifier
        for sensor in sensors
    }
    sensor_types = sorted({sensor.sensor_type for sensor in sensors})

    print("PCPanel telemetry POC")
    print(f"Sequence: {snapshot.sequence}")
    print(f"Captured at: {snapshot.captured_at.isoformat()}")
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
            f"{sensor.value:.2f} [{sensor.sensor_identifier}]"
        )


def main() -> int:
    manager = TelemetryManager(LibreHardwareMonitorProvider())

    try:
        manager.start()
        snapshot = manager.wait_for_snapshot(timeout=10.0)
        if snapshot is None:
            if manager.status is TelemetryStatus.FAILED:
                error = manager.last_error
                if error is not None:
                    raise error
                raise RuntimeError("Telemetry manager failed without an error")
            raise RuntimeError("Timed out waiting for the first telemetry snapshot")
    except FileNotFoundError as exc:
        print(f"DLL error: {exc}", file=sys.stderr)
        return 2
    except OSError as exc:
        print(f"Platform error: {exc}", file=sys.stderr)
        return 3
    except RuntimeError as exc:
        print(f"Provider initialization error: {exc}", file=sys.stderr)
        return 4
    except KeyboardInterrupt:
        print("Telemetry interrupted.", file=sys.stderr)
        return 130
    finally:
        manager.stop()

    print_summary(snapshot)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
