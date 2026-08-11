import {
  getStoredToken,
  invalidateAuthentication,
  setAuthOffline,
} from "../state/auth.js";

const DEFAULT_TIMEOUT_MS = 5000;

export async function authenticatedFetch(url, options = {}, dependencies = {}) {
  const storage = dependencies.storage ?? window.localStorage;
  const fetchImplementation = dependencies.fetch ?? window.fetch.bind(window);
  const AbortControllerImplementation = dependencies.AbortController ?? globalThis.AbortController;
  const timeoutMs = dependencies.timeoutMs ?? DEFAULT_TIMEOUT_MS;
  const token = getStoredToken(storage);
  const headers = new Headers(options.headers);
  const controller = new AbortControllerImplementation();
  const upstreamSignal = options.signal;

  if (upstreamSignal?.aborted) controller.abort(upstreamSignal.reason);
  const forwardAbort = () => controller.abort(upstreamSignal.reason);
  upstreamSignal?.addEventListener("abort", forwardAbort, { once: true });
  const timeout = setTimeout(() => controller.abort(), timeoutMs);

  if (token) headers.set("Authorization", `Bearer ${token}`);

  try {
    const response = await fetchImplementation(url, {
      ...options,
      headers,
      signal: controller.signal,
    });
    if (response.status === 401) invalidateAuthentication(storage);
    return response;
  } catch (error) {
    if (token) setAuthOffline();
    throw error;
  } finally {
    clearTimeout(timeout);
    upstreamSignal?.removeEventListener("abort", forwardAbort);
  }
}
