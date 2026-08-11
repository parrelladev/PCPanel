export function setupFullscreen(button, documentObject = document) {
  const root = documentObject.documentElement;
  const supported = typeof root?.requestFullscreen === "function";
  button.hidden = !supported;
  if (!supported) return Object.freeze({ supported: false });

  const update = () => {
    const active = documentObject.fullscreenElement !== null;
    button.textContent = active ? "Sair da tela cheia" : "Tela cheia";
    button.setAttribute("aria-pressed", String(active));
  };

  button.addEventListener("click", async () => {
    if (documentObject.fullscreenElement !== null) {
      await documentObject.exitFullscreen();
    } else {
      await root.requestFullscreen({ navigationUI: "hide" });
    }
  });
  documentObject.addEventListener("fullscreenchange", update);
  update();
  return Object.freeze({ supported: true });
}
