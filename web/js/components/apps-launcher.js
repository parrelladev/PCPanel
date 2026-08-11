import { ACTIONS_ERROR, ActionsCatalogError, loadActions } from "../services/actions-catalog.js?v=m9a10-1";
import {
  EXECUTION_ERROR,
  ActionExecutionError,
  executeAction,
} from "../services/action-execution.js?v=m9a10-1";

const FEEDBACK_DURATION_MS = 1800;
const EXECUTION_MESSAGES = Object.freeze({
  [EXECUTION_ERROR.NOT_FOUND]: "Aplicativo não encontrado.",
  [EXECUTION_ERROR.UNAVAILABLE]: "Aplicativo indisponível neste PC.",
  [EXECUTION_ERROR.OFFLINE]: "PCPanel está offline ou não foi possível alcançar o servidor.",
  [EXECUTION_ERROR.FAILED]: "Não foi possível iniciar o aplicativo.",
});

export function createAppsLauncher(root, dependencies = {}) {
  const status = root.querySelector("#apps-status");
  const grid = root.querySelector("#apps-grid");
  const refresh = root.querySelector("#apps-refresh");
  let loaded = false;
  let loading = false;
  const actionViews = new Map();
  const executions = createExecutionState();
  const listeners = new Set();
  let catalogState = Object.freeze({ status: "not-loaded", count: null });

  refresh.addEventListener("click", () => load(true));
  return {
    load: () => load(false),
    subscribe(listener) {
      listeners.add(listener);
      listener(catalogState);
      return () => listeners.delete(listener);
    },
    reset() {
      loaded = false;
      loading = false;
      clearActionViews();
      executions.clear();
      grid.replaceChildren();
      updateCatalogState("not-loaded", null);
    },
  };

  async function load(force) {
    if (loading || (loaded && !force)) return;
    loading = true;
    updateCatalogState("loading", null);
    showStatus("Carregando aplicativos…", false);
    refresh.disabled = true;
    try {
      renderActions(await loadActions(dependencies));
      loaded = true;
    } catch (error) {
      renderError(error);
    } finally {
      loading = false;
      refresh.disabled = false;
    }
  }

  function renderActions(actions) {
    clearActionViews();
    grid.replaceChildren();
    if (actions.length === 0) {
      updateCatalogState("empty", 0);
      showStatus("Nenhum aplicativo configurado.", true);
      return;
    }
    status.hidden = true;
    updateCatalogState("available", actions.length);
    refresh.hidden = false;
    grid.hidden = false;
    actions.forEach((action) => {
      const view = createActionButton(action);
      actionViews.set(action.id, view);
      grid.append(view.button);
    });
  }

  function createActionButton(action) {
    const button = document.createElement("button");
    button.className = "app-card";
    button.type = "button";
    button.dataset.actionId = action.id;
    button.setAttribute("aria-label", `Abrir ${action.label}`);
    const icon = document.createElement("span");
    icon.className = "app-card__icon";
    icon.setAttribute("aria-hidden", "true");
    icon.textContent = "▶";
    const label = document.createElement("strong");
    label.textContent = action.label;
    const feedback = document.createElement("span");
    feedback.className = "app-card__feedback";
    feedback.textContent = "Toque para abrir";
    button.append(icon, label, feedback);
    const view = { action, button, icon, feedback, timer: null };
    button.dataset.executionState = "idle";
    button.addEventListener("click", () => runAction(view));
    return view;
  }

  async function runAction(view) {
    if (!executions.begin(view.action.id)) return;
    setExecutionState(view, "executing", "Abrindo…", "…");
    try {
      const result = await executeAction(view.action.id, dependencies);
      if (!result.started) throw new ActionExecutionError(EXECUTION_ERROR.FAILED);
      setExecutionState(view, "success", `${view.action.label} iniciado`, "✓");
      scheduleIdle(view);
    } catch (error) {
      const kind = error instanceof ActionExecutionError ? error.kind : EXECUTION_ERROR.FAILED;
      if (kind === EXECUTION_ERROR.UNAUTHORIZED) return;
      setExecutionState(view, "error", EXECUTION_MESSAGES[kind], "!");
      scheduleIdle(view);
      if (kind === EXECUTION_ERROR.NOT_FOUND) {
        window.setTimeout(() => load(true), FEEDBACK_DURATION_MS);
      }
    }
  }

  function setExecutionState(view, state, message, icon) {
    if (view.timer !== null) window.clearTimeout(view.timer);
    view.timer = null;
    executions.set(view.action.id, state);
    view.button.dataset.executionState = state;
    view.button.disabled = state !== "idle";
    view.button.setAttribute("aria-label", `${view.action.label}: ${message}`);
    view.icon.textContent = icon;
    view.feedback.textContent = message;
  }

  function scheduleIdle(view) {
    view.timer = window.setTimeout(() => {
      setExecutionState(view, "idle", "Toque para abrir", "▶");
    }, FEEDBACK_DURATION_MS);
  }

  function clearActionViews() {
    actionViews.forEach((view) => {
      if (view.timer !== null) window.clearTimeout(view.timer);
    });
    actionViews.clear();
  }

  function renderError(error) {
    grid.replaceChildren();
    grid.hidden = true;
    const kind = error instanceof ActionsCatalogError ? error.kind : ACTIONS_ERROR.SERVER;
    if (kind === ACTIONS_ERROR.UNAUTHORIZED) return;
    const states = {
      [ACTIONS_ERROR.UNAVAILABLE]: "unavailable",
      [ACTIONS_ERROR.OFFLINE]: "offline",
      [ACTIONS_ERROR.SERVER]: "error",
    };
    updateCatalogState(states[kind], null);
    const messages = {
      [ACTIONS_ERROR.UNAVAILABLE]: "Launcher não está habilitado neste PCPanel.",
      [ACTIONS_ERROR.OFFLINE]: "Não foi possível conectar ao PCPanel.",
      [ACTIONS_ERROR.SERVER]: "Não foi possível carregar os aplicativos.",
    };
    showStatus(messages[kind], true);
  }

  function showStatus(message, showRefresh) {
    status.textContent = message;
    status.hidden = false;
    grid.hidden = true;
    refresh.hidden = !showRefresh;
  }

  function updateCatalogState(nextStatus, count) {
    catalogState = Object.freeze({ status: nextStatus, count });
    listeners.forEach((listener) => listener(catalogState));
  }
}

export function createExecutionState() {
  const states = new Map();
  return Object.freeze({
    get: (actionId) => states.get(actionId) ?? "idle",
    begin(actionId) {
      if ((states.get(actionId) ?? "idle") !== "idle") return false;
      states.set(actionId, "executing");
      return true;
    },
    set(actionId, state) {
      states.set(actionId, state);
    },
    clear() {
      states.clear();
    },
  });
}
