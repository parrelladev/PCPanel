const VENDORS = Object.freeze({
  intel: Object.freeze({ name: "Intel", color: "#0071c5" }),
  amd: Object.freeze({ name: "AMD", color: "#ed1c24" }),
  nvidia: Object.freeze({ name: "NVIDIA", color: "#76b900" }),
  unknown: Object.freeze({ name: "Hardware", color: "#68686f" }),
});

export function hardwareVendor(model) {
  const normalized = typeof model === "string" ? model.toLowerCase() : "";
  if (normalized.includes("intel")) return VENDORS.intel;
  if (normalized.includes("amd") || normalized.includes("radeon")) return VENDORS.amd;
  if (normalized.includes("nvidia") || normalized.includes("geforce")) return VENDORS.nvidia;
  return VENDORS.unknown;
}
