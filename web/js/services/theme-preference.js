const THEMES = Object.freeze({ dark: "dark", light: "light" });

export function setupThemePreference(dependencies = {}) {
  const windowObject = dependencies.window ?? window;
  const documentObject = dependencies.document ?? document;
  const query = windowObject.matchMedia("(prefers-color-scheme: light)");
  const themeColor = documentObject.querySelector('meta[name="theme-color"]');

  const apply = (prefersLight) => {
    const theme = prefersLight ? THEMES.light : THEMES.dark;
    documentObject.documentElement.dataset.theme = theme;
    themeColor?.setAttribute("content", prefersLight ? "#ffffff" : "#0f0f0f");
    return theme;
  };

  const onChange = (event) => apply(event.matches);
  if (typeof query.addEventListener === "function") query.addEventListener("change", onChange);
  else query.addListener?.(onChange);

  return Object.freeze({ theme: apply(query.matches) });
}
