export const PAIRING_ERROR = Object.freeze({
  INVALID_CODE: "invalid-code",
  EXPIRED: "expired",
  ATTEMPTS_EXHAUSTED: "attempts-exhausted",
  ALREADY_USED: "already-used",
  CAPACITY: "capacity",
  INVALID_NAME: "invalid-name",
  OFFLINE: "offline",
  UNEXPECTED: "unexpected",
});

export class PairingRequestError extends Error {
  constructor(kind) {
    super(kind);
    this.name = "PairingRequestError";
    this.kind = kind;
  }
}

export async function startPairing(deviceName, fetchImplementation = window.fetch.bind(window)) {
  const response = await request(fetchImplementation, "/api/v1/pairing/start", {
    device_name: deviceName.trim(),
  });
  if (!response.ok) throw new PairingRequestError(startErrorKind(response.status));
  const body = await response.json();
  return { pairingId: body.pairing_id, expiresAt: body.expires_at };
}

export async function completePairing(
  pairingId,
  code,
  fetchImplementation = window.fetch.bind(window),
) {
  const response = await request(fetchImplementation, "/api/v1/pairing/complete", {
    pairing_id: pairingId,
    code,
  });
  if (!response.ok) throw new PairingRequestError(completeErrorKind(response.status));
  return response.json();
}

async function request(fetchImplementation, url, body) {
  try {
    return await fetchImplementation(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
  } catch {
    throw new PairingRequestError(PAIRING_ERROR.OFFLINE);
  }
}

function startErrorKind(status) {
  if (status === 422) return PAIRING_ERROR.INVALID_NAME;
  if (status === 429) return PAIRING_ERROR.CAPACITY;
  return PAIRING_ERROR.UNEXPECTED;
}

function completeErrorKind(status) {
  if (status === 401) return PAIRING_ERROR.INVALID_CODE;
  if (status === 410 || status === 404) return PAIRING_ERROR.EXPIRED;
  if (status === 429) return PAIRING_ERROR.ATTEMPTS_EXHAUSTED;
  if (status === 409) return PAIRING_ERROR.ALREADY_USED;
  return PAIRING_ERROR.UNEXPECTED;
}
