let state = Object.freeze({
  metricSnapshot: null,
  connection: "connecting",
});

const listeners = new Set();

export function subscribe(listener) {
  listeners.add(listener);
  listener(state);
  return () => listeners.delete(listener);
}

export function setMetricSnapshot(snapshot) {
  state = Object.freeze({ ...state, metricSnapshot: snapshot });
  notify();
}

export function setConnection(connection) {
  if (!["connected", "connecting", "reconnecting", "offline"].includes(connection)) return;
  state = Object.freeze({ ...state, connection });
  notify();
}

export function getState() {
  return state;
}

function notify() {
  listeners.forEach((listener) => listener(state));
}
