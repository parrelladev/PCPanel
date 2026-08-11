from __future__ import annotations

from datetime import datetime, timezone

from app.telemetry.metrics import (
    CELSIUS,
    CPU_CLOCK,
    CPU_LOAD,
    CPU_PEAK_TEMPERATURE,
    CPU_POWER,
    CPU_TEMPERATURE,
    GPU_CLOCK,
    GPU_HOTSPOT_TEMPERATURE,
    GPU_LOAD,
    GPU_MEMORY_TOTAL,
    GPU_MEMORY_USED,
    GPU_TEMPERATURE,
    INITIAL_METRIC_KEYS,
    MEGABYTE,
    MEGAHERTZ,
    MEMORY_LOAD,
    MEMORY_TOTAL,
    MEMORY_USED,
    PERCENT,
    WATT,
    MetricReading,
    MetricResolver,
    MetricSnapshot,
)
from app.telemetry.models import SensorReading, TelemetrySnapshot


CAPTURED_AT = datetime(2026, 8, 10, 18, 30, tzinfo=timezone.utc)
EXPECTED_UNITS = {
    CPU_TEMPERATURE: CELSIUS,
    CPU_LOAD: PERCENT,
    CPU_CLOCK: MEGAHERTZ,
    CPU_POWER: WATT,
    CPU_PEAK_TEMPERATURE: CELSIUS,
    GPU_TEMPERATURE: CELSIUS,
    GPU_LOAD: PERCENT,
    GPU_CLOCK: MEGAHERTZ,
    GPU_HOTSPOT_TEMPERATURE: CELSIUS,
    GPU_MEMORY_USED: MEGABYTE,
    GPU_MEMORY_TOTAL: MEGABYTE,
    MEMORY_LOAD: PERCENT,
    MEMORY_USED: MEGABYTE,
    MEMORY_TOTAL: MEGABYTE,
}


def sensor(
    hardware_type: str,
    hardware_identifier: str,
    sensor_type: str,
    sensor_identifier: str,
    sensor_name: str,
    value: float | None,
    *,
    hardware_name: str | None = None,
    max_value: float | None = None,
) -> SensorReading:
    return SensorReading(
        hardware_identifier=hardware_identifier,
        hardware_name=hardware_name or hardware_identifier,
        hardware_type=hardware_type,
        sensor_identifier=sensor_identifier,
        sensor_name=sensor_name,
        sensor_type=sensor_type,
        value=value,
        min_value=None,
        max_value=max_value,
    )


def snapshot(
    *sensors: SensorReading,
    sequence: int = 17,
    captured_at: datetime = CAPTURED_AT,
) -> TelemetrySnapshot:
    return TelemetrySnapshot(
        sequence=sequence,
        captured_at=captured_at,
        sensors=sensors,
    )


def readings_by_key(result: MetricSnapshot) -> dict[str, MetricReading]:
    return {reading.key: reading for reading in result.metrics}


def resolve(*sensors: SensorReading) -> dict[str, MetricReading]:
    return readings_by_key(MetricResolver().resolve(snapshot(*sensors)))


def assert_reading(
    readings: dict[str, MetricReading],
    key: str,
    value: float | None,
    source: str | None,
) -> None:
    assert readings[key] == MetricReading(
        key=key,
        value=value,
        unit=EXPECTED_UNITS[key],
        source_sensor_identifier=source,
    )


def test_resolves_intel_cpu_nvidia_gpu_and_system_memory() -> None:
    readings = resolve(
        sensor("Cpu", "/intelcpu/0", "Temperature", "/intelcpu/0/temp/0", "CPU Package", 58.0),
        sensor("Cpu", "/intelcpu/0", "Load", "/intelcpu/0/load/0", "CPU Total", 34.2),
        sensor(
            "GpuNvidia",
            "/gpu-nvidia/0",
            "Temperature",
            "/gpu-nvidia/0/temp/0",
            "GPU Core",
            63.0,
        ),
        sensor("GpuNvidia", "/gpu-nvidia/0", "Load", "/gpu-nvidia/0/load/0", "GPU Core", 68.0),
        sensor("Memory", "/memory", "Load", "/memory/load/0", "Memory", 73.0),
    )

    assert_reading(readings, CPU_TEMPERATURE, 58.0, "/intelcpu/0/temp/0")
    assert_reading(readings, CPU_LOAD, 34.2, "/intelcpu/0/load/0")
    assert_reading(readings, GPU_TEMPERATURE, 63.0, "/gpu-nvidia/0/temp/0")
    assert_reading(readings, GPU_LOAD, 68.0, "/gpu-nvidia/0/load/0")
    assert_reading(readings, MEMORY_LOAD, 73.0, "/memory/load/0")


def test_resolves_amd_cpu_and_amd_gpu_without_vendor_name_coupling() -> None:
    readings = resolve(
        sensor("Cpu", "/amdcpu/0", "Temperature", "/amdcpu/0/temp/0", "Core (Tctl/Tdie)", 67.0),
        sensor("Cpu", "/amdcpu/0", "Load", "/amdcpu/0/load/0", "CPU Total", 48.0),
        sensor("GpuAmd", "/gpu-amd/0", "Temperature", "/gpu-amd/0/temp/0", "GPU Edge", 72.0),
        sensor("GpuAmd", "/gpu-amd/0", "Load", "/gpu-amd/0/load/0", "GPU Core", 81.0),
        sensor("Memory", "/memory", "Load", "/memory/load/0", "Memory", 61.0),
    )

    assert_reading(readings, CPU_TEMPERATURE, 67.0, "/amdcpu/0/temp/0")
    assert_reading(readings, CPU_LOAD, 48.0, "/amdcpu/0/load/0")
    assert_reading(readings, GPU_TEMPERATURE, 72.0, "/gpu-amd/0/temp/0")
    assert_reading(readings, GPU_LOAD, 81.0, "/gpu-amd/0/load/0")
    assert_reading(readings, MEMORY_LOAD, 61.0, "/memory/load/0")


def test_resolves_intel_cpu_with_intel_integrated_gpu() -> None:
    readings = resolve(
        sensor(
            "Cpu", "/intelcpu/0", "Temperature",
            "/intelcpu/0/temp/package", "CPU Package", 52.0,
        ),
        sensor(
            "Cpu", "/intelcpu/0", "Load",
            "/intelcpu/0/load/total", "CPU Total", 28.0,
        ),
        sensor("GpuIntel", "/gpu-intel/0", "Temperature", "/gpu-intel/0/temp/0", "GPU Core", 54.0),
        sensor("GpuIntel", "/gpu-intel/0", "Load", "/gpu-intel/0/load/0", "D3D 3D", 39.0),
    )

    assert_reading(readings, CPU_TEMPERATURE, 52.0, "/intelcpu/0/temp/package")
    assert_reading(readings, CPU_LOAD, 28.0, "/intelcpu/0/load/total")
    assert_reading(readings, GPU_TEMPERATURE, 54.0, "/gpu-intel/0/temp/0")
    assert_reading(readings, GPU_LOAD, 39.0, "/gpu-intel/0/load/0")


def test_multiple_gpus_use_lowest_stable_device_identity_for_both_metrics() -> None:
    selected_gpu = (
        sensor(
            "GpuAmd", "/gpu/0", "Temperature", "/gpu/0/temp/core",
            "GPU Core", 59.0, hardware_name="AMD Radeon",
        ),
        sensor(
            "GpuAmd", "/gpu/0", "Load", "/gpu/0/load/core",
            "GPU Core", 41.0, hardware_name="AMD Radeon",
        ),
    )
    other_gpu = (
        sensor(
            "GpuNvidia", "/gpu/1", "Temperature", "/gpu/1/temp/core",
            "GPU Core", 76.0, hardware_name="NVIDIA GeForce",
        ),
        sensor(
            "GpuNvidia", "/gpu/1", "Load", "/gpu/1/load/core",
            "GPU Core", 97.0, hardware_name="NVIDIA GeForce",
        ),
    )

    result_a = resolve(*(other_gpu + selected_gpu))
    result_b = resolve(*(selected_gpu + other_gpu))

    assert_reading(result_a, GPU_TEMPERATURE, 59.0, "/gpu/0/temp/core")
    assert_reading(result_a, GPU_LOAD, 41.0, "/gpu/0/load/core")
    assert result_a == result_b


def test_missing_preferred_cpu_temperature_uses_next_ranked_fallback() -> None:
    readings = resolve(
        sensor("Cpu", "/cpu/0", "Temperature", "/cpu/0/temp/max", "Core Max", 74.0),
        sensor("Cpu", "/cpu/0", "Temperature", "/cpu/0/temp/average", "Core Average", 63.0),
    )

    assert_reading(readings, CPU_TEMPERATURE, 63.0, "/cpu/0/temp/average")


def test_preferred_none_value_loses_to_valid_appropriate_fallback() -> None:
    readings = resolve(
        sensor("Cpu", "/cpu/0", "Temperature", "/cpu/0/temp/package", "CPU Package", None),
        sensor("Cpu", "/cpu/0", "Temperature", "/cpu/0/temp/average", "Core Average", 58.0),
        sensor("Cpu", "/cpu/0", "Load", "/cpu/0/load/total", "CPU Total", None),
        sensor("Cpu", "/cpu/0", "Load", "/cpu/0/load/average", "Core Average", 25.0),
    )

    assert_reading(readings, CPU_TEMPERATURE, 58.0, "/cpu/0/temp/average")
    assert_reading(readings, CPU_LOAD, 25.0, "/cpu/0/load/average")


def test_all_candidates_with_none_values_emit_unavailable_metrics() -> None:
    readings = resolve(
        sensor("Cpu", "/cpu/0", "Temperature", "/cpu/0/temp/package", "CPU Package", None),
        sensor("Cpu", "/cpu/0", "Temperature", "/cpu/0/temp/average", "Core Average", None),
    )

    assert_reading(readings, CPU_TEMPERATURE, None, None)


def test_duplicate_names_are_disambiguated_by_sensor_identifier() -> None:
    readings = resolve(
        sensor("Cpu", "/cpu/0", "Temperature", "/cpu/0/temp/z", "CPU Package", 69.0),
        sensor("Cpu", "/cpu/0", "Temperature", "/cpu/0/temp/a", "CPU Package", 61.0),
        sensor("Cpu", "/cpu/0", "Load", "/cpu/0/load/z", "CPU Total", 49.0),
        sensor("Cpu", "/cpu/0", "Load", "/cpu/0/load/a", "CPU Total", 31.0),
    )

    assert_reading(readings, CPU_TEMPERATURE, 61.0, "/cpu/0/temp/a")
    assert_reading(readings, CPU_LOAD, 31.0, "/cpu/0/load/a")


def test_resolution_is_invariant_to_sensor_order() -> None:
    sensors = (
        sensor("Cpu", "/cpu/0", "Temperature", "/cpu/0/temp/max", "Core Max", 71.0),
        sensor("Cpu", "/cpu/0", "Temperature", "/cpu/0/temp/package", "CPU Package", 62.0),
        sensor("Cpu", "/cpu/0", "Load", "/cpu/0/load/core", "CPU Core #1", 78.0),
        sensor("Cpu", "/cpu/0", "Load", "/cpu/0/load/total", "CPU Total", 37.0),
        sensor("GpuNvidia", "/gpu/0", "Temperature", "/gpu/0/temp/hotspot", "GPU Hot Spot", 77.0),
        sensor("GpuNvidia", "/gpu/0", "Temperature", "/gpu/0/temp/core", "GPU Core", 66.0),
        sensor("GpuNvidia", "/gpu/0", "Load", "/gpu/0/load/3d", "D3D 3D", 73.0),
        sensor("GpuNvidia", "/gpu/0", "Load", "/gpu/0/load/core", "GPU Core", 64.0),
        sensor("Memory", "/memory", "Load", "/memory/load/0", "Memory", 55.0),
    )
    raw_a = snapshot(*sensors)
    raw_b = snapshot(*reversed(sensors))

    result_a = MetricResolver().resolve(raw_a)
    result_b = MetricResolver().resolve(raw_b)

    assert tuple(metric.key for metric in result_a.metrics) == tuple(
        metric.key for metric in result_b.metrics
    )
    assert tuple(metric.value for metric in result_a.metrics) == tuple(
        metric.value for metric in result_b.metrics
    )
    assert tuple(metric.unit for metric in result_a.metrics) == tuple(
        metric.unit for metric in result_b.metrics
    )
    assert tuple(metric.source_sensor_identifier for metric in result_a.metrics) == tuple(
        metric.source_sensor_identifier for metric in result_b.metrics
    )


def test_completely_missing_sensors_emit_all_known_metrics_as_unavailable() -> None:
    result = MetricResolver().resolve(snapshot())

    assert tuple(metric.key for metric in result.metrics) == INITIAL_METRIC_KEYS
    assert all(metric.value is None for metric in result.metrics)
    assert all(metric.source_sensor_identifier is None for metric in result.metrics)
    assert {metric.key: metric.unit for metric in result.metrics} == EXPECTED_UNITS


def test_metric_snapshot_preserves_raw_sequence_and_exact_timestamp() -> None:
    raw = snapshot(sequence=987, captured_at=CAPTURED_AT)

    result = MetricResolver().resolve(raw)

    assert result.sequence == raw.sequence
    assert result.captured_at == raw.captured_at
    assert result.captured_at is raw.captured_at


def test_resolving_is_pure_and_does_not_mutate_raw_snapshot_or_sensors() -> None:
    cpu_sensor = sensor("Cpu", "/cpu/0", "Load", "/cpu/0/load/0", "CPU Total", 42.0)
    raw = snapshot(cpu_sensor)
    original_sensors = raw.sensors
    original_sensor = raw.sensors[0]

    first = MetricResolver().resolve(raw)
    second = MetricResolver().resolve(raw)

    assert first == second
    assert raw.sensors is original_sensors
    assert raw.sensors[0] is original_sensor
    assert raw == snapshot(cpu_sensor)


def test_memory_load_uses_system_memory_and_never_gpu_memory() -> None:
    readings = resolve(
        sensor("Memory", "/memory", "Load", "/memory/load/physical", "Memory", 64.0),
        sensor("GpuNvidia", "/gpu/0", "Load", "/gpu/0/load/memory", "GPU Memory", 91.0),
        sensor("GpuNvidia", "/gpu/0", "Data", "/gpu/0/data/memory-used", "GPU Memory Used", 8192.0),
        sensor(
            "GpuNvidia", "/gpu/0", "SmallData",
            "/gpu/0/data/memory-total", "GPU Memory Total", 12288.0,
        ),
    )

    assert_reading(readings, MEMORY_LOAD, 64.0, "/memory/load/physical")
    assert readings[MEMORY_LOAD].source_sensor_identifier != "/gpu/0/load/memory"


def test_resolves_used_system_memory_and_dedicated_gpu_memory() -> None:
    readings = resolve(
        sensor("Memory", "/ram", "Data", "/ram/data/0", "Memory Used", 14.9),
        sensor("Memory", "/vram", "Data", "/vram/data/2", "Memory Used", 18.1),
        sensor(
            "GpuNvidia", "/gpu/0", "SmallData",
            "/gpu/0/smalldata/1", "GPU Memory Used", 2186.0,
        ),
        sensor(
            "GpuNvidia", "/gpu/0", "SmallData",
            "/gpu/0/smalldata/3", "D3D Dedicated Memory Used", 2027.875,
        ),
    )

    assert_reading(readings, MEMORY_USED, 15257.6, "/ram/data/0")
    assert_reading(readings, GPU_MEMORY_USED, 2186.0, "/gpu/0/smalldata/1")


def test_resolves_complete_product_hardware_contract() -> None:
    raw = snapshot(
        sensor(
            "Cpu", "/cpu/0", "Temperature", "/cpu/0/temp/package",
            "CPU Package", 42.0, hardware_name="Intel Core i5-14600KF", max_value=57.0,
        ),
        sensor("Cpu", "/cpu/0", "Load", "/cpu/0/load/total", "CPU Total", 23.0, hardware_name="Intel Core i5-14600KF"),
        sensor("Cpu", "/cpu/0", "Clock", "/cpu/0/clock/1", "P-Core #1", 5291.5, hardware_name="Intel Core i5-14600KF"),
        sensor("Cpu", "/cpu/0", "Power", "/cpu/0/power/package", "CPU Package", 24.0, hardware_name="Intel Core i5-14600KF"),
        sensor(
            "GpuNvidia", "/gpu/0", "Temperature", "/gpu/0/temp/core",
            "GPU Core", 37.0, hardware_name="NVIDIA GeForce RTX 3060 Ti",
        ),
        sensor("GpuNvidia", "/gpu/0", "Temperature", "/gpu/0/temp/hotspot", "GPU Hot Spot", 48.5, hardware_name="NVIDIA GeForce RTX 3060 Ti"),
        sensor("GpuNvidia", "/gpu/0", "Load", "/gpu/0/load/core", "GPU Core", 22.0, hardware_name="NVIDIA GeForce RTX 3060 Ti"),
        sensor("GpuNvidia", "/gpu/0", "Clock", "/gpu/0/clock/core", "GPU Core", 210.0, hardware_name="NVIDIA GeForce RTX 3060 Ti"),
        sensor("GpuNvidia", "/gpu/0", "SmallData", "/gpu/0/memory/used", "GPU Memory Used", 1040.0, hardware_name="NVIDIA GeForce RTX 3060 Ti"),
        sensor("GpuNvidia", "/gpu/0", "SmallData", "/gpu/0/memory/total", "GPU Memory Total", 8192.0, hardware_name="NVIDIA GeForce RTX 3060 Ti"),
        sensor("Memory", "/ram", "Load", "/ram/load", "Memory", 36.9, hardware_name="Total Memory"),
        sensor("Memory", "/ram", "Data", "/ram/used", "Memory Used", 11.75, hardware_name="Total Memory"),
        sensor("Memory", "/ram", "Data", "/ram/available", "Memory Available", 20.25, hardware_name="Total Memory"),
        sensor("Memory", "/memory/0", "Data", "/memory/0/capacity", "Capacity", 16.0, hardware_name="DIMM #1"),
        sensor("Memory", "/memory/1", "Data", "/memory/1/capacity", "Capacity", 16.0, hardware_name="DIMM #2"),
        sensor("Memory", "/vram", "Data", "/vram/used", "Memory Used", 99.0, hardware_name="Virtual Memory"),
    )
    result = MetricResolver().resolve(raw)
    readings = readings_by_key(result)

    assert dict(result.hardware_models) == {
        "cpu": "Intel Core i5-14600KF",
        "gpu": "NVIDIA GeForce RTX 3060 Ti",
    }
    assert_reading(readings, CPU_CLOCK, 5291.5, "/cpu/0/clock/1")
    assert_reading(readings, CPU_POWER, 24.0, "/cpu/0/power/package")
    assert_reading(readings, CPU_PEAK_TEMPERATURE, 57.0, "/cpu/0/temp/package")
    assert_reading(readings, GPU_CLOCK, 210.0, "/gpu/0/clock/core")
    assert_reading(readings, GPU_HOTSPOT_TEMPERATURE, 48.5, "/gpu/0/temp/hotspot")
    assert_reading(readings, GPU_MEMORY_TOTAL, 8192.0, "/gpu/0/memory/total")
    assert_reading(readings, MEMORY_USED, 12032.0, "/ram/used")
    assert_reading(readings, MEMORY_TOTAL, 32768.0, None)
