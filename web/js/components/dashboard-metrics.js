export function metricReading(metrics, key) {
  const reading = metrics[key];
  return typeof reading?.value === "number" && Number.isFinite(reading.value)
    ? reading
    : null;
}

export function formatMetric(reading) {
  if (reading === null) return "--";
  if (reading.unit === "celsius") return `${Math.round(reading.value)} °C`;
  if (reading.unit === "percent") return `${Math.round(reading.value)} %`;
  return String(reading.value);
}

export function clampPercent(value) {
  return Math.min(100, Math.max(0, Number(value) || 0));
}
