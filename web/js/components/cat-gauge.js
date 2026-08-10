export function createCatGauge({ kind, label }) {
  const element = document.createElement("div");
  element.className = "cat-gauge cat--sleep";
  element.innerHTML = `
    <div class="cat-gauge__inner">
      <svg viewBox="0 0 124 92" role="img" aria-label="Gatinho da ${label} dormindo">
        <path class="cat-fill cat-body" d="M32 82c0-21 12-33 30-33s30 12 30 33H32Z"/>
        <path class="cat-fill cat-ear" d="M34 39 39 9l23 18L85 9l5 30Z"/>
        <path class="cat-fill cat-face" d="M31 42c0-17 14-27 31-27s31 10 31 27c0 22-13 35-31 35S31 64 31 42Z"/>
        <path class="cat-detail cat-patch" d="${kind === "cpu" ? "M39 26c9-8 20-10 31-7-10 5-12 13-12 22-8-2-14-7-19-15Z" : "M70 18c9 2 16 7 20 15-8 4-15 5-23 2 1-7 2-12 3-17Z"}" opacity=".35"/>
        <path class="cat-mark cat-eye" d="M42 54q6 5 12 0m16 0q6 5 12 0"/>
        <path class="cat-mark cat-brow" d="m41 44 13 4m29-4-13 4"/>
        <path class="cat-mark cat-mouth" d="M57 64q5 5 10 0"/>
        <path class="cat-mark cat-whisker" d="m33 60-15-3m16 9-14 3m70-9 15-3m-16 9 14 3" opacity=".65"/>
        <text class="cat-zzz" x="93" y="24">Z</text><text class="cat-zzz" x="106" y="12" font-size="9">z</text>
      </svg>
      <div class="cat-gauge__usage"><strong>0%</strong><small>USO DA ${label}</small></div>
    </div>`;

  const svg = element.querySelector("svg");
  const usageLabel = element.querySelector(".cat-gauge__usage strong");

  return {
    element,
    update({ usage, mood, color }) {
      const available = typeof usage === "number" && Number.isFinite(usage);
      const safeUsage = available
        ? Math.min(100, Math.max(0, usage))
        : 0;
      element.style.setProperty("--usage", safeUsage.toFixed(1));
      element.style.setProperty("--thermal-color", color);
      usageLabel.textContent = available ? `${Math.round(safeUsage)} %` : "--";
      element.className = `cat-gauge cat--${mood}`;
      const usageDescription = available
        ? `uso ${Math.round(safeUsage)}%`
        : "uso indisponível";
      svg.setAttribute(
        "aria-label",
        `Gatinho da ${label}: ${moodLabel(mood)}, ${usageDescription}`,
      );
    },
  };
}

function moodLabel(mood) {
  return { sleep: "dormindo", awake: "acordado", alert: "atento", angry: "irritado", critical: "bravo e crítico" }[mood] ?? mood;
}
