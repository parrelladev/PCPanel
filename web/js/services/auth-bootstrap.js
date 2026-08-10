import { authenticatedFetch } from "./authenticated-fetch.js";
import {
  getStoredToken,
  setAuthenticated,
  setAuthChecking,
  setAuthOffline,
  setUnpaired,
} from "../state/auth.js";

export async function bootstrapAuthentication(dependencies = {}) {
  const storage = dependencies.storage ?? window.localStorage;
  if (!getStoredToken(storage)) {
    setUnpaired();
    return;
  }

  setAuthChecking();
  try {
    const response = await authenticatedFetch(
      "/api/v1/auth/status",
      {},
      { storage, fetch: dependencies.fetch },
    );
    if (response.status === 401) return;
    if (!response.ok) {
      setAuthOffline();
      return;
    }

    const body = await response.json();
    setAuthenticated(body.device);
  } catch {
    setAuthOffline();
  }
}
