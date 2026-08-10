import { createCatGauge } from "./components/cat-gauge.js";
import {
  MOOD_LABELS,
  MoodTracker,
  POLICIES,
  thermalPresentation,
} from "./components/thermal-state.js";
import { startWebSocketTelemetry } from "./services/websocket-telemetry.js";
import {
  setConnection,
  setMetricSnapshot,
  subscribe,
} from "./state/telemetry.js";

const METRIC_KEYS = Object.freeze({
  cpuTemperature: "cpu.temperature",
  cpuLoad: "cpu.load",
  gpuTemperature: "gpu.temperature",
  gpuLoad: "gpu.load",
  memoryLoad: "memory.load",
});

const COLORS = Object.freeze({
  cpu: "#3b82f6",
  gpu: "#84cc16",
  memory: "#8b5cf6",
});

const hardwareGrid = document.querySelector("#hardware-grid");
const memoryGrid = document.querySelector("#memory-grid");
const shell = document.querySelector("#app-shell");
const connection = document.querySelector("#connection");
const connectionLabel = document.querySelector("#connection-label");

const cardViews = {
  cpu: createHardwareCard("cpu", "CPU", COLORS.cpu),
  gpu: createHardwareCard("gpu", "GPU", COLORS.gpu),
};
hardwareGrid.append(cardViews.cpu.element, cardViews.gpu.element);

const memoryView = createMemoryCard();
memoryGrid.append(memoryView.element);

subscribe(render);
setupNavigation();
startWebSocketTelemetry({
  onSnapshot: setMetricSnapshot,
  onConnection: setConnection,
});

function createHardwareCard(kind, label, color) {
  const article = document.createElement("article");
  article.className = `hardware-card hardware-card--${kind}`;
  article.style.setProperty("--brand-color", color);
  article.innerHTML = `
    <header class="hardware-card__header">
      <div class="hardware-card__title"><span>${label}</span><h2>${label}</h2></div>
      <span class="metric-status">Métricas canônicas</span>
    </header>
    <div class="hardware-card__content">
      <div data-cat></div>
      <div>
        <div class="primary-reading"><strong>--</strong><span>Indisponível</span></div>
        <div class="mood">Aguardando</div>
        <div class="metric-caption">Temperatura</div>
      </div>
    </div>`;

  const cat = createCatGauge({ kind, label });
  article.querySelector("[data-cat]").replaceWith(cat.element);
  return {
    element: article,
    temperature: article.querySelector(".primary-reading strong"),
    thermalLabel: article.querySelector(".primary-reading span"),
    mood: article.querySelector(".mood"),
    cat,
    color,
    moodTracker: new MoodTracker(),
  };
}

function createMemoryCard() {
  const article = document.createElement("article");
  article.className = "memory-card";
  article.style.setProperty("--meter-color", COLORS.memory);
  article.innerHTML = `
    <h3>RAM</h3>
    <span class="memory-card__numbers">Uso da memória</span>
    <div class="meter" role="meter" aria-label="Uso da RAM" aria-valuemin="0" aria-valuemax="100"><i></i></div>
    <strong class="memory-card__percent">--</strong>`;
  return {
    element: article,
    meter: article.querySelector(".meter"),
    fill: article.querySelector(".meter i"),
    percent: article.querySelector(".memory-card__percent"),
  };
}

function render(state) {
  renderConnection(state.connection);
  if (!state.metricSnapshot) return;

  const metrics = state.metricSnapshot.metrics ?? {};
  renderHardware(
    cardViews.cpu,
    metricReading(metrics, METRIC_KEYS.cpuTemperature),
    metricReading(metrics, METRIC_KEYS.cpuLoad),
    POLICIES.cpu,
  );
  renderHardware(
    cardViews.gpu,
    metricReading(metrics, METRIC_KEYS.gpuTemperature),
    metricReading(metrics, METRIC_KEYS.gpuLoad),
    POLICIES.gpu,
  );
  renderMemory(metricReading(metrics, METRIC_KEYS.memoryLoad));
}

function renderHardware(view, temperatureReading, loadReading, policy) {
  const temperature = temperatureReading?.value ?? null;
  const load = loadReading?.value ?? null;
  const heat = temperature === null
    ? { stress: 0, label: "Indisponível", color: view.color }
    : thermalPresentation(temperature, policy, view.color);
  const score = Math.max(heat.stress, (load ?? 0) * 0.45);
  const moodKey = view.moodTracker.update(score);

  view.element.style.setProperty("--thermal-color", heat.color);
  view.temperature.textContent = formatMetric(temperatureReading);
  view.thermalLabel.textContent = heat.label;
  view.mood.textContent = temperature === null && load === null
    ? "Sem dados"
    : MOOD_LABELS[moodKey];
  view.cat.update({ usage: load, mood: moodKey, color: heat.color });
}

function renderMemory(reading) {
  const load = reading?.value ?? null;
  const width = load === null ? 0 : clamp(load);
  memoryView.percent.textContent = formatMetric(reading);
  memoryView.fill.style.width = `${width}%`;
  if (load === null) {
    memoryView.meter.removeAttribute("aria-valuenow");
    memoryView.meter.setAttribute("aria-valuetext", "Indisponível");
  } else {
    memoryView.meter.setAttribute("aria-valuenow", String(Math.round(width)));
    memoryView.meter.removeAttribute("aria-valuetext");
  }
}

function metricReading(metrics, key) {
  const reading = metrics[key];
  return typeof reading?.value === "number" && Number.isFinite(reading.value)
    ? reading
    : null;
}

function formatMetric(reading) {
  if (reading === null) return "--";
  if (reading.unit === "celsius") return `${Math.round(reading.value)}°`;
  if (reading.unit === "percent") return `${Math.round(reading.value)}%`;
  return String(reading.value);
}

function renderConnection(status) {
  const labels = {
    connected: "Connected",
    connecting: "Connecting",
    disconnected: "Disconnected · stale",
  };
  connectionLabel.textContent = labels[status] ?? labels.connecting;
  connection.className = `connection connection--${status}`;
  connection.setAttribute("aria-label", `Estado da conexão: ${labels[status]}`);
  shell.classList.toggle("is-stale", status === "disconnected");
}

function setupNavigation() {
  document.querySelectorAll(".bottom-nav__item").forEach((button) => {
    button.addEventListener("click", () => {
      document.querySelectorAll(".bottom-nav__item").forEach((item) => {
        const active = item === button;
        item.classList.toggle("is-active", active);
        if (active) item.setAttribute("aria-current", "page");
        else item.removeAttribute("aria-current");
      });
      document.querySelectorAll(".view").forEach((view) => {
        view.hidden = view.dataset.view !== button.dataset.target;
      });
    });
  });
}

function clamp(value) {
  return Math.min(100, Math.max(0, Number(value) || 0));
}
