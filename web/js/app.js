import {
  POLICIES,
  thermalPresentation,
} from "./components/thermal-state.js";
import { startWebSocketTelemetry } from "./services/websocket-telemetry.js";
import { bootstrapAuthentication } from "./services/auth-bootstrap.js?v=m9a10-1";
import { AUTH_STATUS, subscribeAuth } from "./state/auth.js";
import { createPairingView } from "./components/pairing-view.js";
import { createAppsLauncher } from "./components/apps-launcher.js?v=m9a10-1";
import { createSystemStatus } from "./components/system-status.js";
import { setupFullscreen } from "./services/fullscreen.js";
import { setupThemePreference } from "./services/theme-preference.js";
import { hardwareVendor } from "./components/hardware-vendor.js";
import { clampPercent, formatMetric, metricReading } from "./components/dashboard-metrics.js";
import {
  setConnection,
  setMetricSnapshot,
  subscribe,
} from "./state/telemetry.js";

const METRIC_KEYS = Object.freeze({
  cpuTemperature: "cpu.temperature",
  cpuLoad: "cpu.load",
  cpuClock: "cpu.clock",
  cpuPower: "cpu.power",
  cpuPeakTemperature: "cpu.temperature.peak",
  gpuTemperature: "gpu.temperature",
  gpuLoad: "gpu.load",
  gpuClock: "gpu.clock",
  gpuHotspotTemperature: "gpu.temperature.hotspot",
  gpuMemoryUsed: "gpu.memory.used",
  gpuMemoryTotal: "gpu.memory.total",
  memoryLoad: "memory.load",
  memoryUsed: "memory.used",
  memoryTotal: "memory.total",
});

const COLORS = Object.freeze({
  cpu: "#84e35b",
  gpu: "#84e35b",
  memory: "#b7ff4a",
});

const hardwareGrid = document.querySelector("#hardware-grid");
const memoryGrid = document.querySelector("#memory-grid");
const shell = document.querySelector("#app-shell");
const connection = document.querySelector("#connection");
const connectionLabel = document.querySelector("#connection-label");
const authView = document.querySelector("#auth-view");
const authTitle = document.querySelector("#auth-title");
const authMessage = document.querySelector("#auth-message");
const authStatus = document.querySelector("#auth-status");
const authRetry = document.querySelector("#auth-retry");
const pairingRoot = document.querySelector("#pairing-view");
const appsRoot = document.querySelector("#apps-view");
const systemRoot = document.querySelector("#system-view");
const fullscreenToggle = document.querySelector("#fullscreen-toggle");
let telemetryStarted = false;
let previousAuthStatus = null;

const cardViews = {
  cpu: createHardwareCard("cpu", "CPU", COLORS.cpu),
  gpu: createHardwareCard("gpu", "GPU", COLORS.gpu),
};
hardwareGrid.append(cardViews.cpu.element, cardViews.gpu.element);

const memoryView = createMemoryCard();
memoryGrid.append(memoryView.element);
const pairingView = createPairingView(pairingRoot);
const appsLauncher = createAppsLauncher(appsRoot);
const systemStatus = createSystemStatus(systemRoot, appsLauncher);

setupNavigation();
setupThemePreference();
setupFullscreen(fullscreenToggle);
authRetry.addEventListener("click", bootstrapAuthentication);
subscribe(render);
subscribeAuth(renderAuth);
bootstrapAuthentication();

function renderAuth(auth) {
  const content = {
    checking: ["Verificando acesso…", "Validando este dispositivo com o PCPanel."],
    offline: ["PCPanel indisponível", "Sua credencial foi mantida. Tente novamente quando o PC estiver online."],
  };
  const authenticated = auth.status === AUTH_STATUS.AUTHENTICATED;
  const unpaired = auth.status === AUTH_STATUS.UNPAIRED;
  if (!authenticated && previousAuthStatus === AUTH_STATUS.AUTHENTICATED) appsLauncher.reset();
  shell.hidden = !authenticated;
  authView.hidden = authenticated;
  authStatus.hidden = unpaired;
  pairingRoot.hidden = !unpaired;
  authRetry.hidden = auth.status !== AUTH_STATUS.OFFLINE;

  if (authenticated) {
    if (!telemetryStarted) {
      telemetryStarted = true;
      startWebSocketTelemetry({ onSnapshot: setMetricSnapshot, onConnection: setConnection });
    }
    if (previousAuthStatus !== AUTH_STATUS.AUTHENTICATED) appsLauncher.reset();
    previousAuthStatus = auth.status;
    return;
  }

  if (unpaired) {
    if (previousAuthStatus !== AUTH_STATUS.UNPAIRED) pairingView.reset();
    pairingView.show();
    previousAuthStatus = auth.status;
    return;
  }

  const [title, message] = content[auth.status] ?? content.checking;
  authTitle.textContent = title;
  authMessage.textContent = message;
  previousAuthStatus = auth.status;
}

function createHardwareCard(kind, label, color) {
  const article = document.createElement("article");
  article.className = `hardware-card hardware-card--${kind}`;
  article.style.setProperty("--brand-color", color);
  article.innerHTML = `
    <header class="hardware-card__header">
      <div class="hardware-card__title"><h2>${label}<span class="vendor-badge">Hardware</span></h2><span class="hardware-model">Modelo indisponível</span></div>
      <div class="temp-wrap"><strong class="primary-reading">--</strong><span class="temp-state">Indisponível</span></div>
    </header>
    <div class="hardware-card__content">
      <div class="load-row"><div class="meter"><i></i></div><strong class="load-value">--</strong></div>
      <div class="metrics">
        <div class="metric"><span>${kind === "cpu" ? "Clock" : "Clock"}</span><strong data-metric="clock">--</strong></div>
        <div class="metric"><span>${kind === "cpu" ? "Power" : "Hotspot"}</span><strong data-metric="detail">--</strong></div>
        <div class="metric"><span>${kind === "cpu" ? "Peak" : "VRAM"}</span><strong data-metric="last">--</strong></div>
      </div>
    </div>`;

  return {
    element: article,
    temperature: article.querySelector(".primary-reading"),
    thermalLabel: article.querySelector(".temp-state"),
    loadFill: article.querySelector(".meter i"),
    loadValue: article.querySelector(".load-value"),
    model: article.querySelector(".hardware-model"),
    vendor: article.querySelector(".vendor-badge"),
    clock: article.querySelector('[data-metric="clock"]'),
    detail: article.querySelector('[data-metric="detail"]'),
    last: article.querySelector('[data-metric="last"]'),
    color,
  };
}

function createMemoryCard() {
  const article = document.createElement("article");
  article.className = "memory-card";
  article.style.setProperty("--meter-color", COLORS.memory);
  article.innerHTML = `
    <div><h3>RAM</h3><span class="memory-card__numbers">Memória utilizada</span></div>
    <strong class="memory-card__percent">--</strong>
    <div class="meter" role="meter" aria-label="Uso da RAM" aria-valuemin="0" aria-valuemax="100"><i></i></div>`;
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
    {
      model: state.metricSnapshot.hardware_models?.cpu,
      clock: metricReading(metrics, METRIC_KEYS.cpuClock),
      detail: metricReading(metrics, METRIC_KEYS.cpuPower),
      last: metricReading(metrics, METRIC_KEYS.cpuPeakTemperature),
    },
  );
  renderHardware(
    cardViews.gpu,
    metricReading(metrics, METRIC_KEYS.gpuTemperature),
    metricReading(metrics, METRIC_KEYS.gpuLoad),
    POLICIES.gpu,
    {
      model: state.metricSnapshot.hardware_models?.gpu,
      clock: metricReading(metrics, METRIC_KEYS.gpuClock),
      detail: metricReading(metrics, METRIC_KEYS.gpuHotspotTemperature),
      memoryUsed: metricReading(metrics, METRIC_KEYS.gpuMemoryUsed),
      memoryTotal: metricReading(metrics, METRIC_KEYS.gpuMemoryTotal),
    },
  );
  renderMemory(
    metricReading(metrics, METRIC_KEYS.memoryLoad),
    metricReading(metrics, METRIC_KEYS.memoryUsed),
    metricReading(metrics, METRIC_KEYS.memoryTotal),
  );
}

function renderHardware(view, temperatureReading, loadReading, policy, details) {
  const temperature = temperatureReading?.value ?? null;
  const load = loadReading?.value ?? null;
  const heat = temperature === null
    ? { stress: 0, label: "Indisponível", color: view.color }
    : thermalPresentation(temperature, policy, view.color);
  view.element.style.setProperty("--thermal-color", heat.color);
  view.temperature.textContent = formatMetric(temperatureReading);
  view.thermalLabel.textContent = heat.label;
  view.loadValue.textContent = formatMetric(loadReading);
  view.loadFill.style.width = `${load === null ? 0 : clampPercent(load)}%`;
  view.model.textContent = details.model ?? "Modelo indisponível";
  const vendor = hardwareVendor(details.model);
  view.vendor.textContent = vendor.name;
  view.element.style.setProperty("--vendor-color", vendor.color);
  view.clock.textContent = formatMetric(details.clock);
  view.detail.textContent = formatMetric(details.detail);
  view.last.textContent = details.memoryUsed
    ? formatMemoryPair(details.memoryUsed, details.memoryTotal)
    : formatMetric(details.last);
}

function renderMemory(loadReading, usedReading, totalReading) {
  const load = loadReading?.value ?? null;
  const width = load === null ? 0 : clampPercent(load);
  memoryView.percent.textContent = formatMemoryPair(usedReading, totalReading);
  memoryView.fill.style.width = `${width}%`;
  if (load === null) {
    memoryView.meter.removeAttribute("aria-valuenow");
    memoryView.meter.setAttribute("aria-valuetext", "Indisponível");
  } else {
    memoryView.meter.setAttribute("aria-valuenow", String(Math.round(width)));
    memoryView.meter.removeAttribute("aria-valuetext");
  }
}

function formatMemoryPair(used, total) {
  if (used === null) return "--";
  const usedValue = Math.round(used.value);
  if (total === null) return `${usedValue} MB`;
  return `${usedValue} / ${Math.round(total.value)} MB`;
}

function renderConnection(status) {
  const labels = {
    connected: "Conectado · ao vivo",
    connecting: "Conectando",
    reconnecting: "Reconectando · dados anteriores",
    offline: "Offline · dados anteriores",
  };
  connectionLabel.textContent = labels[status] ?? labels.connecting;
  connection.className = `connection connection--${status}`;
  connection.setAttribute("aria-label", `Estado da conexão: ${labels[status]}`);
  const stale = ["reconnecting", "offline"].includes(status);
  shell.classList.toggle("is-stale", stale);
  document.querySelectorAll(".metric-status").forEach((indicator) => {
    indicator.textContent = stale ? "Dados anteriores" : (status === "connected" ? "Ao vivo" : "Aguardando");
  });
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
      if (button.dataset.target === "apps") appsLauncher.load();
      if (button.dataset.target === "system") systemStatus.refresh();
    });
  });
}
