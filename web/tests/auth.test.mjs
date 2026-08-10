import test from "node:test";
import assert from "node:assert/strict";

import { bootstrapAuthentication } from "../js/services/auth-bootstrap.js";
import { authenticatedFetch } from "../js/services/authenticated-fetch.js";
import {
  PAIRING_ERROR,
  PairingRequestError,
  completePairing,
  startPairing,
} from "../js/services/pairing.js";
import {
  ACTIONS_ERROR,
  ActionsCatalogError,
  loadActions,
  publicActions,
} from "../js/services/actions-catalog.js";
import {
  EXECUTION_ERROR,
  ActionExecutionError,
  executeAction,
} from "../js/services/action-execution.js";
import { createExecutionState } from "../js/components/apps-launcher.js";
import {
  actionsLabel,
  serverLabel,
  telemetryLabel,
} from "../js/components/system-status.js";
import { formatMetric, metricReading } from "../js/components/dashboard-metrics.js";
import { startWebSocketTelemetry } from "../js/services/websocket-telemetry.js";
import {
  AUTH_STATUS,
  TOKEN_STORAGE_KEY,
  clearStoredToken,
  getAuthState,
  getStoredToken,
  invalidateAuthentication,
  storeToken,
} from "../js/state/auth.js";

class MemoryStorage {
  items = new Map();
  getItem(key) { return this.items.get(key) ?? null; }
  setItem(key, value) { this.items.set(key, String(value)); }
  removeItem(key) { this.items.delete(key); }
}

function response(status, body = {}) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

test("token storage is persistent, namespaced, retrievable, and clearable", () => {
  const storage = new MemoryStorage();
  storeToken("secret", storage);
  assert.equal(storage.getItem(TOKEN_STORAGE_KEY), "secret");
  assert.equal(getStoredToken(storage), "secret");
  clearStoredToken(storage);
  assert.equal(getStoredToken(storage), null);
});

test("bootstrap without a token becomes unpaired", async () => {
  await bootstrapAuthentication({ storage: new MemoryStorage(), fetch: () => assert.fail() });
  assert.equal(getAuthState().status, AUTH_STATUS.UNPAIRED);
});

test("auth status 200 keeps the authorized device in memory", async () => {
  const storage = new MemoryStorage();
  storeToken("secret", storage);
  await bootstrapAuthentication({
    storage,
    fetch: async () => response(200, { authenticated: true, device: { id: "device-1", name: "Phone" } }),
  });
  assert.deepEqual(getAuthState(), {
    status: AUTH_STATUS.AUTHENTICATED,
    device: { id: "device-1", name: "Phone" },
  });
});

test("401 clears the credential and becomes unpaired", async () => {
  const storage = new MemoryStorage();
  storeToken("secret", storage);
  await bootstrapAuthentication({ storage, fetch: async () => response(401) });
  assert.equal(getStoredToken(storage), null);
  assert.equal(getAuthState().status, AUTH_STATUS.UNPAIRED);
});

test("network failure preserves the credential and becomes offline", async () => {
  const storage = new MemoryStorage();
  storeToken("secret", storage);
  await bootstrapAuthentication({
    storage,
    fetch: async () => { throw new TypeError("Failed to fetch"); },
  });
  assert.equal(getStoredToken(storage), "secret");
  assert.equal(getAuthState().status, AUTH_STATUS.OFFLINE);
});

test("authenticated fetch adds authorization without changing URL or existing headers", async () => {
  const storage = new MemoryStorage();
  storeToken("secret", storage);
  let request;
  await authenticatedFetch("/api/v1/actions", { headers: { Accept: "application/json" } }, {
    storage,
    fetch: async (url, options) => {
      request = { url, options };
      return response(200);
    },
  });
  assert.equal(request.url, "/api/v1/actions");
  assert.equal(request.options.headers.get("Accept"), "application/json");
  assert.equal(request.options.headers.get("Authorization"), "Bearer secret");
  assert.equal(request.url.includes("secret"), false);
});

test("pairing start sends the trimmed device name and does not depend on a returned code", async () => {
  let request;
  const result = await startPairing("  Galaxy S24  ", async (url, options) => {
    request = { url, options };
    return response(201, {
      pairing_id: "pairing-1",
      expires_at: "2026-08-10T20:05:00Z",
      code: "must-be-ignored",
    });
  });
  assert.equal(request.url, "/api/v1/pairing/start");
  assert.deepEqual(JSON.parse(request.options.body), { device_name: "Galaxy S24" });
  assert.deepEqual(result, {
    pairingId: "pairing-1",
    expiresAt: "2026-08-10T20:05:00Z",
  });
  assert.equal("code" in result, false);
});

test("pairing complete preserves a leading zero and the temporary pairing id", async () => {
  let request;
  const result = await completePairing("pairing-1", "004271", async (url, options) => {
    request = { url, options };
    return response(200, { device_id: "device-1", token: "issued-secret" });
  });
  assert.equal(request.url, "/api/v1/pairing/complete");
  assert.deepEqual(JSON.parse(request.options.body), {
    pairing_id: "pairing-1",
    code: "004271",
  });
  assert.equal(result.token, "issued-secret");
});

test("pairing failures are classified without exposing server details", async () => {
  await assert.rejects(
    completePairing("pairing-1", "000000", async () => response(410)),
    (error) => error instanceof PairingRequestError && error.kind === PAIRING_ERROR.EXPIRED,
  );
  await assert.rejects(
    startPairing("Phone", async () => { throw new TypeError("network secret"); }),
    (error) => error instanceof PairingRequestError && error.kind === PAIRING_ERROR.OFFLINE,
  );
});

test("actions catalog uses authenticated GET and keeps only id and label", async () => {
  const storage = new MemoryStorage();
  storeToken("secret", storage);
  let request;
  const actions = await loadActions({
    storage,
    fetch: async (url, options) => {
      request = { url, options };
      return response(200, {
        actions: [
          { id: "editor", label: "Editor", executable: "private.exe", arguments: ["private"] },
          { id: "player", label: "Player", working_directory: "C:/private" },
        ],
      });
    },
  });
  assert.equal(request.url, "/api/v1/actions");
  assert.equal(request.options.headers.get("Authorization"), "Bearer secret");
  assert.deepEqual(actions, [
    { id: "editor", label: "Editor" },
    { id: "player", label: "Player" },
  ]);
});

test("empty catalog is valid and malformed entries are ignored", () => {
  assert.deepEqual(publicActions([]), []);
  assert.deepEqual(publicActions([{ id: "valid", label: "Valid" }, { id: 42, label: "Bad" }]), [
    { id: "valid", label: "Valid" },
  ]);
});

test("actions catalog distinguishes disabled API, server failure, offline, and 401", async () => {
  const cases = [
    [404, ACTIONS_ERROR.UNAVAILABLE],
    [503, ACTIONS_ERROR.SERVER],
    [401, ACTIONS_ERROR.UNAUTHORIZED],
  ];
  for (const [status, kind] of cases) {
    await assert.rejects(
      loadActions({ storage: new MemoryStorage(), fetch: async () => response(status) }),
      (error) => error instanceof ActionsCatalogError && error.kind === kind,
    );
  }
  await assert.rejects(
    loadActions({ storage: new MemoryStorage(), fetch: async () => { throw new TypeError("offline"); } }),
    (error) => error instanceof ActionsCatalogError && error.kind === ACTIONS_ERROR.OFFLINE,
  );
});

test("action execution posts encoded id with bearer and no request body", async () => {
  const storage = new MemoryStorage();
  storeToken("secret", storage);
  let request;
  const result = await executeAction("media/player 1", {
    storage,
    fetch: async (url, options) => {
      request = { url, options };
      return response(200, { action_id: "media/player 1", started: true, process_id: 999 });
    },
  });
  assert.equal(request.url, "/api/v1/actions/media%2Fplayer%201/execute");
  assert.equal(request.options.method, "POST");
  assert.equal("body" in request.options, false);
  assert.equal(request.options.headers.get("Authorization"), "Bearer secret");
  assert.deepEqual(result, { actionId: "media/player 1", started: true });
});

test("action execution maps public failures and 401 clears authentication", async () => {
  const cases = [
    [404, EXECUTION_ERROR.NOT_FOUND],
    [409, EXECUTION_ERROR.UNAVAILABLE],
    [500, EXECUTION_ERROR.FAILED],
  ];
  for (const [status, kind] of cases) {
    await assert.rejects(
      executeAction("app", { storage: new MemoryStorage(), fetch: async () => response(status) }),
      (error) => error instanceof ActionExecutionError && error.kind === kind,
    );
  }

  const storage = new MemoryStorage();
  storeToken("revoked", storage);
  await assert.rejects(
    executeAction("app", { storage, fetch: async () => response(401) }),
    (error) => error instanceof ActionExecutionError && error.kind === EXECUTION_ERROR.UNAUTHORIZED,
  );
  assert.equal(getStoredToken(storage), null);
  assert.equal(getAuthState().status, AUTH_STATUS.UNPAIRED);
});

test("action execution maps network failures without leaking their details", async () => {
  await assert.rejects(
    executeAction("app", {
      storage: new MemoryStorage(),
      fetch: async () => { throw new TypeError("private network detail"); },
    }),
    (error) => error instanceof ActionExecutionError && error.kind === EXECUTION_ERROR.OFFLINE,
  );
});

test("execution state is independent per action and blocks only the same double tap", () => {
  const states = createExecutionState();
  assert.equal(states.get("one"), "idle");
  assert.equal(states.get("two"), "idle");
  assert.equal(states.begin("one"), true);
  assert.equal(states.begin("one"), false);
  assert.equal(states.begin("two"), true);
  assert.equal(states.get("one"), "executing");
  assert.equal(states.get("two"), "executing");
  states.set("one", "success");
  states.set("two", "error");
  assert.equal(states.get("one"), "success");
  assert.equal(states.get("two"), "error");
  states.set("one", "idle");
  assert.equal(states.get("one"), "idle");
  assert.equal(states.get("two"), "error");
});

test("system status maps server and telemetry connection states", () => {
  assert.equal(serverLabel("connected"), "Online");
  assert.equal(serverLabel("offline"), "Offline");
  assert.equal(serverLabel("connecting"), "Offline");
  assert.equal(telemetryLabel("connected"), "Online");
  assert.equal(telemetryLabel("connecting"), "Conectando");
  assert.equal(telemetryLabel("reconnecting"), "Reconectando");
  assert.equal(telemetryLabel("offline"), "Offline");
});

test("dashboard formats canonical values and never renders invalid numbers", () => {
  const metrics = {
    "cpu.temperature": { value: 54.0293123, unit: "celsius" },
    "cpu.load": { value: null, unit: "percent" },
    "gpu.load": { value: Number.NaN, unit: "percent" },
  };
  assert.equal(formatMetric(metricReading(metrics, "cpu.temperature")), "54 °C");
  assert.equal(formatMetric(metricReading(metrics, "cpu.load")), "--");
  assert.equal(formatMetric(metricReading(metrics, "gpu.load")), "--");
  assert.equal(formatMetric(metricReading(metrics, "memory.load")), "--");
});

test("websocket updates snapshots, avoids duplicate sockets, and reconnects on visibility", () => {
  class FakeSocket {
    static CONNECTING = 0;
    static OPEN = 1;
    static CLOSED = 3;
    static instances = [];
    constructor(url) {
      this.url = url;
      this.readyState = FakeSocket.CONNECTING;
      this.listeners = new Map();
      FakeSocket.instances.push(this);
    }
    addEventListener(type, listener) { this.listeners.set(type, listener); }
    emit(type, payload = {}) { this.listeners.get(type)?.(payload); }
    open() { this.readyState = FakeSocket.OPEN; this.emit("open"); }
    close() {
      if (this.readyState === FakeSocket.CLOSED) return;
      this.readyState = FakeSocket.CLOSED;
      this.emit("close");
    }
  }
  const timers = new Map();
  let timerId = 0;
  const fakeWindow = {
    location: { protocol: "http:", host: "pcpanel.local" },
    setTimeout(callback, delay) {
      timerId += 1;
      timers.set(timerId, { callback, delay });
      return timerId;
    },
    clearTimeout(id) { timers.delete(id); },
  };
  const documentListeners = new Map();
  const fakeDocument = {
    visibilityState: "visible",
    addEventListener(type, listener) { documentListeners.set(type, listener); },
    removeEventListener(type) { documentListeners.delete(type); },
  };
  const connections = [];
  const snapshots = [];
  const storage = new MemoryStorage();
  storeToken("preserved", storage);
  const telemetry = startWebSocketTelemetry({
    onSnapshot: (snapshot) => snapshots.push(snapshot),
    onConnection: (connection) => connections.push(connection),
  }, { window: fakeWindow, document: fakeDocument, WebSocket: FakeSocket });

  assert.equal(FakeSocket.instances.length, 1);
  const first = FakeSocket.instances[0];
  first.open();
  first.emit("message", { data: JSON.stringify({ metrics: { "cpu.load": { value: 17 } } }) });
  assert.equal(snapshots.length, 1);
  first.close();
  assert.equal(connections.at(-1), "reconnecting");

  const reconnect = [...timers.entries()].find(([, timer]) => timer.delay === 1000);
  timers.delete(reconnect[0]);
  reconnect[1].callback();
  assert.equal(FakeSocket.instances.length, 2);
  documentListeners.get("visibilitychange")();
  assert.equal(FakeSocket.instances.length, 2);

  FakeSocket.instances[1].close();
  documentListeners.get("visibilitychange")();
  assert.equal(FakeSocket.instances.length, 3);
  const offline = [...timers.entries()].find(([, timer]) => timer.delay === 15000);
  timers.delete(offline[0]);
  offline[1].callback();
  assert.equal(connections.at(-1), "offline");
  assert.equal(getStoredToken(storage), "preserved");
  telemetry.stop();
});

test("system actions status distinguishes counts, disabled API, and offline", () => {
  assert.equal(actionsLabel({ status: "available", count: 4 }), "4 disponíveis");
  assert.equal(actionsLabel({ status: "available", count: 1 }), "1 disponível");
  assert.equal(actionsLabel({ status: "empty", count: 0 }), "0 disponíveis");
  assert.equal(actionsLabel({ status: "unavailable", count: null }), "Launcher desabilitado");
  assert.equal(actionsLabel({ status: "offline", count: null }), "Indisponível");
});

test.afterEach(() => {
  invalidateAuthentication(new MemoryStorage());
});
