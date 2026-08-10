export const AUTH_STATUS = Object.freeze({
  CHECKING: "checking",
  UNPAIRED: "unpaired",
  AUTHENTICATED: "authenticated",
  OFFLINE: "offline",
});

const TOKEN_STORAGE_KEY = "pcpanel.deviceToken";

let state = Object.freeze({ status: AUTH_STATUS.CHECKING, device: null });
const listeners = new Set();

export function getStoredToken(storage = window.localStorage) {
  return storage.getItem(TOKEN_STORAGE_KEY);
}

export function storeToken(token, storage = window.localStorage) {
  if (typeof token !== "string" || token.length === 0) {
    throw new TypeError("A non-empty device token is required");
  }
  storage.setItem(TOKEN_STORAGE_KEY, token);
}

export function clearStoredToken(storage = window.localStorage) {
  storage.removeItem(TOKEN_STORAGE_KEY);
}

export function subscribeAuth(listener) {
  listeners.add(listener);
  listener(state);
  return () => listeners.delete(listener);
}

export function getAuthState() {
  return state;
}

export function setAuthChecking() {
  update(AUTH_STATUS.CHECKING, null);
}

export function setAuthenticated(device) {
  update(AUTH_STATUS.AUTHENTICATED, device);
}

export function setAuthOffline() {
  update(AUTH_STATUS.OFFLINE, null);
}

export function invalidateAuthentication(storage = window.localStorage) {
  clearStoredToken(storage);
  update(AUTH_STATUS.UNPAIRED, null);
}

export function setUnpaired() {
  update(AUTH_STATUS.UNPAIRED, null);
}

export { TOKEN_STORAGE_KEY };

function update(status, device) {
  state = Object.freeze({ status, device });
  listeners.forEach((listener) => listener(state));
}
