from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from types import MappingProxyType
from typing import Final, Mapping

from .models import SensorReading, TelemetrySnapshot


CPU_TEMPERATURE: Final = "cpu.temperature"
CPU_LOAD: Final = "cpu.load"
CPU_CLOCK: Final = "cpu.clock"
CPU_POWER: Final = "cpu.power"
CPU_PEAK_TEMPERATURE: Final = "cpu.temperature.peak"

GPU_TEMPERATURE: Final = "gpu.temperature"
GPU_LOAD: Final = "gpu.load"
GPU_CLOCK: Final = "gpu.clock"
GPU_HOTSPOT_TEMPERATURE: Final = "gpu.temperature.hotspot"
GPU_MEMORY_USED: Final = "gpu.memory.used"
GPU_MEMORY_TOTAL: Final = "gpu.memory.total"

MEMORY_LOAD: Final = "memory.load"
MEMORY_USED: Final = "memory.used"
MEMORY_TOTAL: Final = "memory.total"

STORAGE_TEMPERATURE: Final = "storage.temperature"

CELSIUS: Final = "celsius"
PERCENT: Final = "percent"
MEGAHERTZ: Final = "megahertz"
WATT: Final = "watt"
BYTE: Final = "byte"
MEGABYTE: Final = "megabyte"


# Metrics currently guaranteed by the canonical snapshot contract. A resolver
# must emit one reading for every key, including when its value is unavailable.
INITIAL_METRIC_KEYS: Final[tuple[str, ...]] = (
    CPU_TEMPERATURE,
    CPU_LOAD,
    CPU_CLOCK,
    CPU_POWER,
    CPU_PEAK_TEMPERATURE,
    GPU_TEMPERATURE,
    GPU_LOAD,
    GPU_CLOCK,
    GPU_HOTSPOT_TEMPERATURE,
    GPU_MEMORY_USED,
    GPU_MEMORY_TOTAL,
    MEMORY_LOAD,
    MEMORY_USED,
    MEMORY_TOTAL,
)


# Complete PCPanel metric vocabulary known at this milestone. Keeping the unit
# beside each key provides one source of truth for current and future resolvers.
METRIC_UNITS: Final[Mapping[str, str]] = MappingProxyType(
    {
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
        STORAGE_TEMPERATURE: CELSIUS,
    }
)


@dataclass(slots=True, frozen=True)
class MetricReading:
    """A provider-independent reading for one canonical PCPanel metric.

    An unavailable metric has ``value`` and ``source_sensor_identifier`` set
    to ``None`` while retaining its canonical key and unit.
    """

    key: str
    value: float | None
    unit: str
    source_sensor_identifier: str | None


@dataclass(slots=True, frozen=True)
class MetricSnapshot:
    """Immutable canonical view preserving its raw snapshot identity."""

    sequence: int
    captured_at: datetime
    metrics: tuple[MetricReading, ...]
    hardware_models: tuple[tuple[str, str], ...]


_CPU_HARDWARE_TYPES: Final = frozenset({"cpu"})
_GPU_HARDWARE_TYPES: Final = frozenset(
    {"gpuamd", "gpuintel", "gpunvidia"}
)
_MEMORY_HARDWARE_TYPES: Final = frozenset({"memory"})


@dataclass(slots=True, frozen=True)
class _MetricRule:
    key: str
    hardware_types: frozenset[str]
    sensor_type: str
    name_preferences: tuple[tuple[str, ...], ...]
    excluded_names: tuple[str, ...] = ()
    value_scale: float = 1.0
    use_max_value: bool = False
    require_preferred_name: bool = False


_METRIC_RULES: Final[tuple[_MetricRule, ...]] = (
    _MetricRule(
        key=CPU_TEMPERATURE,
        hardware_types=_CPU_HARDWARE_TYPES,
        sensor_type="temperature",
        name_preferences=(
            ("cpu package", "package"),
            ("tctl tdie", "tdie"),
            ("core average", "core avg"),
            ("core max",),
        ),
    ),
    _MetricRule(
        key=CPU_LOAD,
        hardware_types=_CPU_HARDWARE_TYPES,
        sensor_type="load",
        name_preferences=(
            ("cpu total", "total cpu"),
            ("cpu overall", "overall cpu"),
            ("cpu package", "package"),
            ("core average", "core avg"),
            ("core max",),
        ),
    ),
    _MetricRule(
        key=CPU_CLOCK,
        hardware_types=_CPU_HARDWARE_TYPES,
        sensor_type="clock",
        name_preferences=(("p core", "cpu core", "core"),),
        excluded_names=("bus",),
    ),
    _MetricRule(
        key=CPU_POWER,
        hardware_types=_CPU_HARDWARE_TYPES,
        sensor_type="power",
        name_preferences=(("cpu package", "package"), ("cpu cores", "cores")),
        excluded_names=("memory", "platform"),
    ),
    _MetricRule(
        key=CPU_PEAK_TEMPERATURE,
        hardware_types=_CPU_HARDWARE_TYPES,
        sensor_type="temperature",
        name_preferences=(("cpu package", "package"), ("core max",)),
        excluded_names=("distance to tjmax",),
        use_max_value=True,
    ),
    _MetricRule(
        key=GPU_TEMPERATURE,
        hardware_types=_GPU_HARDWARE_TYPES,
        sensor_type="temperature",
        name_preferences=(
            ("gpu core", "core"),
            ("gpu edge", "edge"),
            ("gpu hot spot", "hot spot", "hotspot"),
        ),
        excluded_names=("memory", "vram"),
    ),
    _MetricRule(
        key=GPU_LOAD,
        hardware_types=_GPU_HARDWARE_TYPES,
        sensor_type="load",
        name_preferences=(
            ("gpu core", "gpu total", "total gpu"),
            ("d3d 3d", "3d"),
        ),
        excluded_names=(
            "memory",
            "vram",
            "video engine",
            "bus interface",
        ),
    ),
    _MetricRule(
        key=GPU_CLOCK,
        hardware_types=_GPU_HARDWARE_TYPES,
        sensor_type="clock",
        name_preferences=(("gpu core", "core"),),
        excluded_names=("memory",),
    ),
    _MetricRule(
        key=GPU_HOTSPOT_TEMPERATURE,
        hardware_types=_GPU_HARDWARE_TYPES,
        sensor_type="temperature",
        name_preferences=(("gpu hot spot", "hot spot", "hotspot"),),
        excluded_names=("memory",),
        require_preferred_name=True,
    ),
    _MetricRule(
        key=GPU_MEMORY_USED,
        hardware_types=_GPU_HARDWARE_TYPES,
        sensor_type="smalldata",
        name_preferences=(
            ("gpu memory used",),
            ("dedicated memory used",),
        ),
        excluded_names=("shared", "free", "total"),
        require_preferred_name=True,
    ),
    _MetricRule(
        key=GPU_MEMORY_TOTAL,
        hardware_types=_GPU_HARDWARE_TYPES,
        sensor_type="smalldata",
        name_preferences=(("gpu memory total", "memory total"),),
        excluded_names=("free", "used", "shared"),
        require_preferred_name=True,
    ),
    _MetricRule(
        key=MEMORY_LOAD,
        hardware_types=_MEMORY_HARDWARE_TYPES,
        sensor_type="load",
        name_preferences=(
            ("memory", "physical memory", "memory load"),
            ("ram", "ram load"),
        ),
        excluded_names=("virtual", "swap", "page file", "pagefile"),
    ),
    _MetricRule(
        key=MEMORY_USED,
        hardware_types=_MEMORY_HARDWARE_TYPES,
        sensor_type="data",
        name_preferences=(("memory used", "ram used"),),
        excluded_names=("virtual", "swap", "page file", "pagefile"),
        value_scale=1024.0,
        require_preferred_name=True,
    ),
)


class MetricResolver:
    """Transform raw telemetry into deterministic, provider-neutral metrics.

    One GPU is selected for the whole snapshot by sorting GPU devices by their
    stable raw identity (identifier, type, then name). Both GPU metrics are
    resolved only from that device, so a snapshot never combines different
    GPUs implicitly.
    """

    def resolve(self, snapshot: TelemetrySnapshot) -> MetricSnapshot:
        selected_gpu = self._select_gpu(snapshot.sensors)
        readings = list(
            self._resolve_rule(rule, snapshot.sensors, selected_gpu)
            for rule in _METRIC_RULES
        )
        readings.append(self._resolve_memory_total(snapshot.sensors))
        selected_cpu = self._select_device(snapshot.sensors, _CPU_HARDWARE_TYPES)
        hardware_models = tuple(
            (key, device[2])
            for key, device in (("cpu", selected_cpu), ("gpu", selected_gpu))
            if device is not None
        )
        return MetricSnapshot(
            sequence=snapshot.sequence,
            captured_at=snapshot.captured_at,
            metrics=tuple(readings),
            hardware_models=hardware_models,
        )

    @staticmethod
    def _select_gpu(
        sensors: tuple[SensorReading, ...],
    ) -> tuple[str, str, str] | None:
        return MetricResolver._select_device(sensors, _GPU_HARDWARE_TYPES)

    @staticmethod
    def _select_device(
        sensors: tuple[SensorReading, ...],
        hardware_types: frozenset[str],
    ) -> tuple[str, str, str] | None:
        devices = {
            (
                sensor.hardware_identifier,
                sensor.hardware_type,
                sensor.hardware_name,
            )
            for sensor in sensors
            if sensor.hardware_type.casefold() in hardware_types
        }
        if not devices:
            return None
        return min(devices, key=_normalized_text_tuple)

    @staticmethod
    def _resolve_memory_total(sensors: tuple[SensorReading, ...]) -> MetricReading:
        capacities = tuple(
            sensor
            for sensor in sensors
            if sensor.hardware_type.casefold() in _MEMORY_HARDWARE_TYPES
            and sensor.sensor_type.casefold() == "data"
            and _normalize_text(sensor.sensor_name) == "capacity"
            and sensor.value is not None
        )
        if capacities:
            return MetricReading(
                key=MEMORY_TOTAL,
                value=sum(sensor.value for sensor in capacities) * 1024.0,
                unit=MEGABYTE,
                source_sensor_identifier=None,
            )

        used_rule = next(rule for rule in _METRIC_RULES if rule.key == MEMORY_USED)
        available_rule = _MetricRule(
            key=MEMORY_TOTAL,
            hardware_types=_MEMORY_HARDWARE_TYPES,
            sensor_type="data",
            name_preferences=(("memory available", "ram available"),),
            excluded_names=("virtual", "swap", "page file", "pagefile"),
            value_scale=1024.0,
            require_preferred_name=True,
        )
        used = MetricResolver._resolve_rule(used_rule, sensors, None)
        available = MetricResolver._resolve_rule(available_rule, sensors, None)
        return MetricReading(
            key=MEMORY_TOTAL,
            value=(
                None
                if used.value is None or available.value is None
                else used.value + available.value
            ),
            unit=MEGABYTE,
            source_sensor_identifier=available.source_sensor_identifier,
        )

    @staticmethod
    def _resolve_rule(
        rule: _MetricRule,
        sensors: tuple[SensorReading, ...],
        selected_gpu: tuple[str, str, str] | None,
    ) -> MetricReading:
        candidates = (
            sensor
            for sensor in sensors
            if _matches_rule(sensor, rule, selected_gpu)
            and (sensor.max_value if rule.use_max_value else sensor.value) is not None
        )
        selected = min(
            candidates,
            key=lambda sensor: _sensor_rank(sensor, rule),
            default=None,
        )

        return MetricReading(
            key=rule.key,
            value=(
                None
                if selected is None
                else (
                    selected.max_value if rule.use_max_value else selected.value
                ) * rule.value_scale
            ),
            unit=METRIC_UNITS[rule.key],
            source_sensor_identifier=(
                None if selected is None else selected.sensor_identifier
            ),
        )


def _matches_rule(
    sensor: SensorReading,
    rule: _MetricRule,
    selected_gpu: tuple[str, str, str] | None,
) -> bool:
    if sensor.hardware_type.casefold() not in rule.hardware_types:
        return False
    if sensor.sensor_type.casefold() != rule.sensor_type:
        return False

    if rule.hardware_types is _MEMORY_HARDWARE_TYPES:
        memory_identity = _normalize_text(
            f"{sensor.hardware_identifier} {sensor.hardware_name}"
        )
        if any(name in memory_identity for name in ("virtual", "swap", "page file")):
            return False

    if rule.hardware_types is _GPU_HARDWARE_TYPES:
        device = (
            sensor.hardware_identifier,
            sensor.hardware_type,
            sensor.hardware_name,
        )
        if device != selected_gpu:
            return False

    normalized_name = _normalize_text(sensor.sensor_name)
    if rule.require_preferred_name and not any(
        name in normalized_name
        for alternatives in rule.name_preferences
        for name in alternatives
    ):
        return False
    return not any(name in normalized_name for name in rule.excluded_names)


def _sensor_rank(sensor: SensorReading, rule: _MetricRule) -> tuple[object, ...]:
    normalized_name = _normalize_text(sensor.sensor_name)
    name_rank = next(
        (
            rank
            for rank, alternatives in enumerate(rule.name_preferences)
            if any(name in normalized_name for name in alternatives)
        ),
        len(rule.name_preferences),
    )
    return (
        name_rank,
        sensor.hardware_identifier.casefold(),
        sensor.sensor_identifier.casefold(),
        normalized_name,
        sensor.hardware_name.casefold(),
        sensor.hardware_identifier,
        sensor.sensor_identifier,
        sensor.sensor_name,
        sensor.hardware_name,
        repr(sensor.value),
        repr(sensor.min_value),
        repr(sensor.max_value),
    )


def _normalize_text(value: str) -> str:
    return " ".join(
        "".join(character if character.isalnum() else " " for character in value)
        .casefold()
        .split()
    )


def _normalized_text_tuple(values: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(value.casefold() for value in values) + values
