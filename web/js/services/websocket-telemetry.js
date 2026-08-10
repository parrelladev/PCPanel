const RECONNECT_DELAY_MS = 3000;

export function startWebSocketTelemetry({ onSnapshot, onConnection }) {
  let socket = null;
  let reconnectTimer = null;
  let stopped = false;

  function connect() {
    if (stopped) return;
    onConnection("connecting");
    socket = new WebSocket(websocketUrl());

    socket.addEventListener("open", () => onConnection("connected"));
    socket.addEventListener("message", (event) => {
      try {
        const snapshot = JSON.parse(event.data);
        if (snapshot && typeof snapshot.metrics === "object") {
          onSnapshot(snapshot);
        }
      } catch (error) {
        console.warn("PCPanel ignorou uma mensagem canônica inválida.", error);
      }
    });
    socket.addEventListener("close", () => {
      socket = null;
      if (stopped) return;
      onConnection("disconnected");
      scheduleReconnect();
    });
    socket.addEventListener("error", () => socket?.close());
  }

  function scheduleReconnect() {
    if (reconnectTimer !== null || stopped) return;
    reconnectTimer = window.setTimeout(() => {
      reconnectTimer = null;
      connect();
    }, RECONNECT_DELAY_MS);
  }

  connect();

  return {
    stop() {
      stopped = true;
      if (reconnectTimer !== null) window.clearTimeout(reconnectTimer);
      reconnectTimer = null;
      socket?.close();
    },
  };
}

function websocketUrl() {
  const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
  return `${protocol}//${window.location.host}/ws/v1/metrics`;
}
