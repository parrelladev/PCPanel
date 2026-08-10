from __future__ import annotations

from ..telemetry.metrics import MetricResolver
from ..telemetry.models import TelemetrySnapshot
from .schemas import MetricsResponse


def metrics_response_from_raw(snapshot: TelemetrySnapshot) -> MetricsResponse:
    """Resolve and serialize one raw snapshot with the shared API contract."""

    return MetricsResponse.from_snapshot(MetricResolver().resolve(snapshot))
