import {
  getStoredToken,
  invalidateAuthentication,
  setAuthOffline,
} from "../state/auth.js";

export async function authenticatedFetch(url, options = {}, dependencies = {}) {
  const storage = dependencies.storage ?? window.localStorage;
  const fetchImplementation = dependencies.fetch ?? window.fetch.bind(window);
  const token = getStoredToken(storage);
  const headers = new Headers(options.headers);

  if (token) headers.set("Authorization", `Bearer ${token}`);

  try {
    const response = await fetchImplementation(url, { ...options, headers });
    if (response.status === 401) invalidateAuthentication(storage);
    return response;
  } catch (error) {
    if (token) setAuthOffline();
    throw error;
  }
}
