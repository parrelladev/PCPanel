import { bootstrapAuthentication } from "../services/auth-bootstrap.js";
import {
  PAIRING_ERROR,
  PairingRequestError,
  completePairing,
  startPairing,
} from "../services/pairing.js";
import { storeToken } from "../state/auth.js";

const ERROR_MESSAGES = Object.freeze({
  [PAIRING_ERROR.INVALID_CODE]: "Código incorreto. Confira o PC e tente novamente.",
  [PAIRING_ERROR.EXPIRED]: "O código expirou. Inicie a conexão novamente.",
  [PAIRING_ERROR.ATTEMPTS_EXHAUSTED]: "Muitas tentativas. Inicie a conexão novamente.",
  [PAIRING_ERROR.ALREADY_USED]: "Este código já foi utilizado. Inicie uma nova conexão.",
  [PAIRING_ERROR.CAPACITY]: "Há muitas conexões pendentes. Aguarde e tente novamente.",
  [PAIRING_ERROR.INVALID_NAME]: "Informe um nome válido com até 100 caracteres.",
  [PAIRING_ERROR.OFFLINE]: "Não foi possível conectar ao PCPanel. Tente novamente.",
  [PAIRING_ERROR.UNEXPECTED]: "Não foi possível concluir a conexão. Tente novamente.",
});

export function createPairingView(root, dependencies = {}) {
  const fetchImplementation = dependencies.fetch;
  const storage = dependencies.storage;
  const nameForm = root.querySelector("#pairing-name-form");
  const codeForm = root.querySelector("#pairing-code-form");
  const nameInput = root.querySelector("#device-name");
  const codeInput = root.querySelector("#pairing-code");
  const feedback = root.querySelector("#pairing-feedback");
  const countdown = root.querySelector("#pairing-countdown");
  const backButton = root.querySelector("#pairing-back");
  let pairing = null;
  let busy = false;
  let countdownTimer = null;

  nameForm.addEventListener("submit", submitName);
  codeForm.addEventListener("submit", submitCode);
  backButton.addEventListener("click", showNameStep);

  return { show, reset: showNameStep };

  function show() {
    root.hidden = false;
    queueMicrotask(() => (pairing ? codeInput : nameInput).focus());
  }

  async function submitName(event) {
    event.preventDefault();
    if (busy) return;
    const deviceName = nameInput.value.trim();
    if (!deviceName) {
      showError("Informe um nome para este dispositivo.");
      nameInput.focus();
      return;
    }

    setBusy(true, nameForm);
    clearFeedback();
    pairing = null;
    try {
      pairing = await startPairing(deviceName, fetchImplementation);
      showCodeStep();
    } catch (error) {
      showError(messageFor(error));
    } finally {
      setBusy(false, nameForm);
    }
  }

  async function submitCode(event) {
    event.preventDefault();
    if (busy || !pairing) return;
    const code = codeInput.value.trim();
    if (!/^\d{6}$/.test(code)) {
      showError("Digite os 6 números exibidos no PC.");
      codeInput.focus();
      return;
    }

    setBusy(true, codeForm);
    clearFeedback();
    try {
      const result = await completePairing(pairing.pairingId, code, fetchImplementation);
      storeToken(result.token, storage);
      clearTransientState();
      await bootstrapAuthentication({ storage, fetch: fetchImplementation });
    } catch (error) {
      const kind = error instanceof PairingRequestError ? error.kind : PAIRING_ERROR.UNEXPECTED;
      if ([PAIRING_ERROR.EXPIRED, PAIRING_ERROR.ATTEMPTS_EXHAUSTED, PAIRING_ERROR.ALREADY_USED].includes(kind)) {
        showNameStep();
      } else {
        codeInput.select();
      }
      showError(messageFor(error));
    } finally {
      setBusy(false, codeForm);
    }
  }

  function showCodeStep() {
    nameForm.hidden = true;
    codeForm.hidden = false;
    codeInput.value = "";
    clearFeedback();
    updateCountdown();
    countdownTimer = window.setInterval(updateCountdown, 1000);
    codeInput.focus();
  }

  function showNameStep() {
    clearTransientState();
    codeForm.hidden = true;
    nameForm.hidden = false;
    clearFeedback();
    queueMicrotask(() => nameInput.focus());
  }

  function clearTransientState() {
    pairing = null;
    codeInput.value = "";
    if (countdownTimer !== null) window.clearInterval(countdownTimer);
    countdownTimer = null;
    countdown.textContent = "";
  }

  function updateCountdown() {
    if (!pairing) return;
    const seconds = Math.max(0, Math.ceil((Date.parse(pairing.expiresAt) - Date.now()) / 1000));
    countdown.textContent = seconds > 0
      ? `Código válido por ${formatDuration(seconds)}.`
      : "O código pode ter expirado. Você ainda pode tentar ou iniciar novamente.";
  }

  function setBusy(value, form) {
    busy = value;
    form.querySelectorAll("button, input").forEach((control) => { control.disabled = value; });
    form.setAttribute("aria-busy", String(value));
  }

  function showError(message) {
    feedback.textContent = message;
    feedback.hidden = false;
  }

  function clearFeedback() {
    feedback.textContent = "";
    feedback.hidden = true;
  }
}

function messageFor(error) {
  const kind = error instanceof PairingRequestError ? error.kind : PAIRING_ERROR.UNEXPECTED;
  return ERROR_MESSAGES[kind];
}

function formatDuration(seconds) {
  const minutes = Math.floor(seconds / 60);
  const remainder = seconds % 60;
  return `${minutes}:${String(remainder).padStart(2, "0")}`;
}
