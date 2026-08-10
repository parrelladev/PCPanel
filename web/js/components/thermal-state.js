export const POLICIES = Object.freeze({
  cpu: Object.freeze({ ideal: 65, hot: 85, critical: 95 }),
  gpu: Object.freeze({ ideal: 65, hot: 83, critical: 90 }),
});

export const MOOD_LABELS = Object.freeze({
  sleep: "Dormindo",
  awake: "Acordado",
  alert: "Atento",
  angry: "Irritado",
  critical: "Bravo · Crítico",
});

const THERMAL_LABELS = Object.freeze(["Normal", "Normal", "Warm", "Hot", "Critical"]);
const MOODS = Object.freeze(["sleep", "awake", "alert", "angry", "critical"]);
const MOOD_THRESHOLDS = Object.freeze([25, 48, 68, 86]);
const THERMAL_COLORS = Object.freeze(["#eab83f", "#f47b20", "#ff2e3f"]);

export function thermalStress(value, policy) {
  const temperature = Number(value);
  if (!Number.isFinite(temperature)) return 0;
  if (temperature <= 30) return 0;
  if (temperature <= policy.ideal) return interpolate(temperature, 30, policy.ideal, 0, 48);
  if (temperature <= policy.hot) return interpolate(temperature, policy.ideal, policy.hot, 48, 70);
  if (temperature <= policy.critical) return interpolate(temperature, policy.hot, policy.critical, 70, 90);
  return Math.min(100, interpolate(temperature, policy.critical, policy.critical + 10, 90, 100));
}

export function thermalPresentation(value, policy, brandColor) {
  const stress = thermalStress(value, policy);
  const band = stress < 25 ? 0 : stress < 48 ? 1 : stress < 68 ? 2 : stress < 86 ? 3 : 4;
  return { stress, label: THERMAL_LABELS[band], color: thermalColor(brandColor, stress) };
}

export class MoodTracker {
  #score = 0;
  #moodIndex = 0;

  update(nextScore) {
    const alpha = nextScore > this.#score ? 0.17 : 0.07;
    this.#score += (nextScore - this.#score) * alpha;
    let candidate = MOOD_THRESHOLDS.filter((threshold) => this.#score >= threshold).length;

    if (candidate < this.#moodIndex) {
      const lowerBoundary = MOOD_THRESHOLDS[this.#moodIndex - 1] - 5;
      if (this.#score > lowerBoundary) candidate = this.#moodIndex;
    }
    this.#moodIndex = candidate;
    return MOODS[this.#moodIndex];
  }
}

function thermalColor(brandColor, stress) {
  if (stress <= 32) return brandColor;
  if (stress <= 55) return mix(brandColor, THERMAL_COLORS[0], (stress - 32) / 23);
  if (stress <= 76) return mix(THERMAL_COLORS[0], THERMAL_COLORS[1], (stress - 55) / 21);
  return mix(THERMAL_COLORS[1], THERMAL_COLORS[2], Math.min(1, (stress - 76) / 18));
}

function interpolate(value, inMin, inMax, outMin, outMax) {
  return outMin + ((value - inMin) / (inMax - inMin)) * (outMax - outMin);
}

function mix(left, right, amount) {
  const a = hexToRgb(left);
  const b = hexToRgb(right);
  const channels = a.map((channel, index) => Math.round(channel + (b[index] - channel) * amount));
  return `rgb(${channels.join(" ")})`;
}

function hexToRgb(hex) {
  const value = hex.replace("#", "");
  return [0, 2, 4].map((index) => Number.parseInt(value.slice(index, index + 2), 16));
}
