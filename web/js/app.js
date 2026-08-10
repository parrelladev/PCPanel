"use strict";

const RECONNECT_DELAY_MS = 3000;

const elements = {
  connection: document.querySelector(".connection"),
  connectionStatus: document.querySelector("#connection-status"),
  cpuTemperature: document.querySelector("#cpu-temperature"),
  cpuLoad: document.querySelector("#cpu-load"),
  gpuTemperature: document.querySelector("#gpu-temperature"),
  gpuLoad: document.querySelector("#gpu-load"),
  ramLoad: document.querySelector("#ram-load"),
};

let socket = null;
let reconnectTimer = null;

function normalized(value) {
  return String(value ?? "").trim().toLowerCase();
}

function isUsable(sensor) {
  return typeof sensor.value === "number" && Number.isFinite(sensor.value);
}

function nameRank(sensorName, preferredNames) {
  const name = normalized(sensorName);
  const exactIndex = preferredNames.findIndex((candidate) => name === candidate);
  if (exactIndex !== -1) {
    return exactIndex;
  }

  const partialIndex = preferredNames.findIndex((candidate) => name.includes(candidate));
  return partialIndex === -1 ? preferredNames.length + 10 : preferredNames.length + partialIndex;
}

function selectMetric(sensors, hardwareMatch, sensorType, preferredNames, extraRank = () => 0) {
  return sensors
    .filter((sensor) => hardwareMatch(normalized(sensor.hardware_type)))
    .filter((sensor) => normalized(sensor.sensor_type) === sensorType)
    .filter(isUsable)
    .sort((left, right) => {
      const leftRank = extraRank(left) + nameRank(left.sensor_name, preferredNames);
      const rightRank = extraRank(right) + nameRank(right.sensor_name, preferredNames);
      return leftRank - rightRank;
    })[0] ?? null;
}

// Temporary raw-sensor resolver. Hardware and sensor types are authoritative;
// human-readable names only rank multiple valid candidates.
function resolveMetrics(sensors) {
  const cpu = (type) => type.includes("cpu");
  const gpu = (type) => type.includes("gpu");
  const memory = (type) => type === "memory";
  const physicalMemoryRank = (sensor) => normalized(sensor.hardware_name).includes("virtual") ? 100 : 0;

  return {
    cpuTemperature: selectMetric(sensors, cpu, "temperature", ["cpu package", "package", "core max"]),
    cpuLoad: selectMetric(sensors, cpu, "load", ["cpu total", "total"]),
    gpuTemperature: selectMetric(sensors, gpu, "temperature", ["gpu core", "core"]),
    gpuLoad: selectMetric(sensors, gpu, "load", ["gpu core", "core", "d3d 3d"]),
    ramLoad: selectMetric(sensors, memory, "load", ["memory"], physicalMemoryRank),
  };
}

function formatMetric(sensor, suffix) {
  return sensor ? `${sensor.value.toFixed(1)}${suffix}` : "--";
}

function renderSnapshot(snapshot) {
  const metrics = resolveMetrics(Array.isArray(snapshot.sensors) ? snapshot.sensors : []);
  elements.cpuTemperature.textContent = formatMetric(metrics.cpuTemperature, " °C");
  elements.cpuLoad.textContent = formatMetric(metrics.cpuLoad, "%");
  elements.gpuTemperature.textContent = formatMetric(metrics.gpuTemperature, " °C");
  elements.gpuLoad.textContent = formatMetric(metrics.gpuLoad, "%");
  elements.ramLoad.textContent = formatMetric(metrics.ramLoad, "%");
}

function setConnectionState(state) {
  elements.connectionStatus.textContent = state;
  elements.connection.classList.toggle("connection--connected", state === "Connected");
  elements.connection.classList.toggle("connection--disconnected", state === "Disconnected");
}

function websocketUrl() {
  const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
  return `${protocol}//${window.location.host}/ws/v1/telemetry`;
}

function scheduleReconnect() {
  if (reconnectTimer !== null) {
    return;
  }

  reconnectTimer = window.setTimeout(() => {
    reconnectTimer = null;
    connect();
  }, RECONNECT_DELAY_MS);
}

function connect() {
  setConnectionState("Connecting");
  socket = new WebSocket(websocketUrl());

  socket.addEventListener("open", () => setConnectionState("Connected"));
  socket.addEventListener("message", (event) => {
    try {
      renderSnapshot(JSON.parse(event.data));
    } catch (error) {
      console.warn("PCPanel ignored an invalid telemetry message.", error);
    }
  });
  socket.addEventListener("close", () => {
    setConnectionState("Disconnected");
    scheduleReconnect();
  });
  socket.addEventListener("error", () => socket.close());
}

connect();
