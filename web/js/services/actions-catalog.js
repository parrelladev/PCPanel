import { authenticatedFetch } from "./authenticated-fetch.js?v=m9a10-1";

export const ACTIONS_ERROR = Object.freeze({
  UNAUTHORIZED: "unauthorized",
  UNAVAILABLE: "unavailable",
  OFFLINE: "offline",
  SERVER: "server",
});

export class ActionsCatalogError extends Error {
  constructor(kind) {
    super(kind);
    this.name = "ActionsCatalogError";
    this.kind = kind;
  }
}

export async function loadActions(dependencies = {}) {
  let response;
  try {
    response = await authenticatedFetch(
      "/api/v1/actions",
      {},
      {
        storage: dependencies.storage,
        fetch: dependencies.fetch,
        timeoutMs: dependencies.timeoutMs,
        AbortController: dependencies.AbortController,
      },
    );
  } catch {
    throw new ActionsCatalogError(ACTIONS_ERROR.OFFLINE);
  }

  if (response.status === 401) throw new ActionsCatalogError(ACTIONS_ERROR.UNAUTHORIZED);
  if (response.status === 404) throw new ActionsCatalogError(ACTIONS_ERROR.UNAVAILABLE);
  if (!response.ok) throw new ActionsCatalogError(ACTIONS_ERROR.SERVER);
  return publicActions((await response.json()).actions);
}

export function publicActions(actions) {
  if (!Array.isArray(actions)) return [];
  return actions
    .filter((action) => typeof action?.id === "string" && typeof action?.label === "string")
    .map((action) => Object.freeze({ id: action.id, label: action.label }));
}
