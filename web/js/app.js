import { createCatGauge } from "./components/cat-gauge.js";
import {
  MOOD_LABELS,
  MoodTracker,
  POLICIES,
  thermalPresentation,
} from "./components/thermal-state.js";
import { startWebSocketTelemetry } from "./services/websocket-telemetry.js";
import { bootstrapAuthentication } from "./services/auth-bootstrap.js";
import { AUTH_STATUS, subscribeAuth } from "./state/auth.js";
import { createPairingView } from "./components/pairing-view.js";
import { createAppsLauncher } from "./components/apps-launcher.js";
import { createSystemStatus } from "./components/system-status.js";
import { clampPercent, formatMetric, metricReading } from "./components/dashboard-metrics.js";
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
const authView = document.querySelector("#auth-view");
const authTitle = document.querySelector("#auth-title");
const authMessage = document.querySelector("#auth-message");
const authStatus = document.querySelector("#auth-status");
const authRetry = document.querySelector("#auth-retry");
const pairingRoot = document.querySelector("#pairing-view");
const appsRoot = document.querySelector("#apps-view");
const systemRoot = document.querySelector("#system-view");
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
  const width = load === null ? 0 : clampPercent(load);
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
