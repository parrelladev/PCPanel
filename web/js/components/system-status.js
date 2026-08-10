import { subscribeAuth } from "../state/auth.js";
import { subscribe as subscribeTelemetry } from "../state/telemetry.js";

export function createSystemStatus(root, actionsLauncher) {
  const deviceName = root.querySelector("#system-device-name");
  const deviceStatus = root.querySelector("#system-device-status");
  const serverStatus = root.querySelector("#system-server-status");
  const telemetryStatus = root.querySelector("#system-telemetry-status");
  const actionsStatus = root.querySelector("#system-actions-status");

  subscribeAuth((auth) => {
    deviceName.textContent = auth.device?.name ?? "Dispositivo não identificado";
    deviceStatus.textContent = auth.device ? "Autorizado" : "Não autorizado";
    setTone(deviceStatus, auth.device ? "online" : "offline");
  });
  subscribeTelemetry((telemetry) => {
    serverStatus.textContent = serverLabel(telemetry.connection);
    telemetryStatus.textContent = telemetryLabel(telemetry.connection);
    setTone(serverStatus, telemetry.connection === "connected" ? "online" : "offline");
    setTone(
      telemetryStatus,
      telemetry.connection === "connected"
        ? "online"
        : (telemetry.connection === "offline" ? "offline" : "pending"),
    );
  });
  actionsLauncher.subscribe((actions) => {
    actionsStatus.textContent = actionsLabel(actions);
    const tone = ["available", "empty"].includes(actions.status)
      ? "online"
      : (["not-loaded", "loading"].includes(actions.status) ? "pending" : "offline");
    setTone(actionsStatus, tone);
  });

  return Object.freeze({ refresh: actionsLauncher.load });
}

function setTone(element, tone) {
  element.closest(".system-card")?.setAttribute("data-status-tone", tone);
}

export function serverLabel(connection) {
  return connection === "connected" ? "Online" : "Offline";
}

export function telemetryLabel(connection) {
  const labels = {
    connected: "Online",
    connecting: "Conectando",
    reconnecting: "Reconectando",
    offline: "Offline",
  };
  return labels[connection] ?? "Offline";
}

export function actionsLabel(actions) {
  if (actions.status === "available") {
    return `${actions.count} ${actions.count === 1 ? "disponível" : "disponíveis"}`;
  }
  if (actions.status === "empty") return "0 disponíveis";
  if (actions.status === "unavailable") return "Launcher desabilitado";
  if (["offline", "error"].includes(actions.status)) return "Indisponível";
  return "Carregando";
}
