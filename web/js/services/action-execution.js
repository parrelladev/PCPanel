import { authenticatedFetch } from "./authenticated-fetch.js?v=m9a10-1";

export const EXECUTION_ERROR = Object.freeze({
  UNAUTHORIZED: "unauthorized",
  NOT_FOUND: "not-found",
  UNAVAILABLE: "unavailable",
  OFFLINE: "offline",
  FAILED: "failed",
});

export class ActionExecutionError extends Error {
  constructor(kind) {
    super(kind);
    this.name = "ActionExecutionError";
    this.kind = kind;
  }
}

export async function executeAction(actionId, dependencies = {}) {
  const path = `/api/v1/actions/${encodeURIComponent(actionId)}/execute`;
  let response;
  try {
    response = await authenticatedFetch(
      path,
      { method: "POST" },
      {
        storage: dependencies.storage,
        fetch: dependencies.fetch,
        timeoutMs: dependencies.timeoutMs,
        AbortController: dependencies.AbortController,
      },
    );
  } catch {
    throw new ActionExecutionError(EXECUTION_ERROR.OFFLINE);
  }

  if (response.status === 401) throw new ActionExecutionError(EXECUTION_ERROR.UNAUTHORIZED);
  if (response.status === 404) throw new ActionExecutionError(EXECUTION_ERROR.NOT_FOUND);
  if (response.status === 409) throw new ActionExecutionError(EXECUTION_ERROR.UNAVAILABLE);
  if (!response.ok) throw new ActionExecutionError(EXECUTION_ERROR.FAILED);

  const result = await response.json();
  return Object.freeze({ actionId: result.action_id, started: result.started === true });
}
