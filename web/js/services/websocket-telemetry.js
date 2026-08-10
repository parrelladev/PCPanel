const RECONNECT_DELAYS_MS = Object.freeze([1000, 2000, 4000, 8000]);
const OFFLINE_AFTER_MS = 15000;

export function startWebSocketTelemetry({ onSnapshot, onConnection }, dependencies = {}) {
  const browserWindow = dependencies.window ?? window;
  const browserDocument = dependencies.document ?? document;
  const WebSocketImplementation = dependencies.WebSocket ?? WebSocket;
  let socket = null;
  let reconnectTimer = null;
  let offlineTimer = null;
  let reconnectAttempt = 0;
  let offlineAnnounced = false;
  let stopped = false;

  function connect() {
    if (stopped || socketIsActive(socket, WebSocketImplementation)) return;
    clearReconnectTimer();
    onConnection(reconnectAttempt === 0 ? "connecting" : (offlineAnnounced ? "offline" : "reconnecting"));
    const current = new WebSocketImplementation(websocketUrl(browserWindow));
    socket = current;

    current.addEventListener("open", () => {
      if (socket !== current || stopped) return;
      reconnectAttempt = 0;
      offlineAnnounced = false;
      clearOfflineTimer();
      onConnection("connected");
    });
    current.addEventListener("message", (event) => {
      try {
        const snapshot = JSON.parse(event.data);
        if (snapshot && typeof snapshot.metrics === "object") onSnapshot(snapshot);
      } catch {
        console.warn("PCPanel ignorou uma mensagem canônica inválida.");
      }
    });
    current.addEventListener("close", () => {
      if (socket === current) socket = null;
      if (stopped) return;
      if (!offlineAnnounced) onConnection("reconnecting");
      startOfflineTimer();
      scheduleReconnect();
    });
    current.addEventListener("error", () => current.close());
  }

  function scheduleReconnect() {
    if (reconnectTimer !== null || stopped) return;
    const delay = RECONNECT_DELAYS_MS[Math.min(reconnectAttempt, RECONNECT_DELAYS_MS.length - 1)];
    reconnectAttempt += 1;
    reconnectTimer = browserWindow.setTimeout(() => {
      reconnectTimer = null;
      connect();
    }, delay);
  }

  function startOfflineTimer() {
    if (offlineTimer !== null) return;
    offlineTimer = browserWindow.setTimeout(() => {
      offlineTimer = null;
      if (!stopped && !socketIsOpen(socket, WebSocketImplementation)) {
        offlineAnnounced = true;
        onConnection("offline");
      }
    }, OFFLINE_AFTER_MS);
  }

  function handleVisibilityChange() {
    if (browserDocument.visibilityState !== "visible" || stopped) return;
    if (!socketIsActive(socket, WebSocketImplementation)) connect();
  }

  function clearReconnectTimer() {
    if (reconnectTimer !== null) browserWindow.clearTimeout(reconnectTimer);
    reconnectTimer = null;
  }

  function clearOfflineTimer() {
    if (offlineTimer !== null) browserWindow.clearTimeout(offlineTimer);
    offlineTimer = null;
  }

  browserDocument.addEventListener("visibilitychange", handleVisibilityChange);
  connect();

  return {
    stop() {
      stopped = true;
      clearReconnectTimer();
      clearOfflineTimer();
      browserDocument.removeEventListener("visibilitychange", handleVisibilityChange);
      socket?.close();
      socket = null;
    },
  };
}

function socketIsActive(socket, WebSocketImplementation) {
  return socket !== null && [WebSocketImplementation.CONNECTING, WebSocketImplementation.OPEN].includes(socket.readyState);
}

function socketIsOpen(socket, WebSocketImplementation) {
  return socket?.readyState === WebSocketImplementation.OPEN;
}

function websocketUrl(browserWindow) {
  const protocol = browserWindow.location.protocol === "https:" ? "wss:" : "ws:";
  return `${protocol}//${browserWindow.location.host}/ws/v1/metrics`;
}
