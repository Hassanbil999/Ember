// Number + unit formatting from the canonical variable registry (served by /api/meta).
export type VarMeta = { label: string; short?: string; unit?: string; display_unit?: string; display_scale?: number; kind: string; description?: string };

let VARS: Record<string, VarMeta> = {};
export function setVars(v: Record<string, VarMeta>) { VARS = v || {}; }
export function vmeta(name: string): VarMeta { return VARS[name] || { label: name, kind: "number" }; }

export function unitOf(name: string) {
  const m = vmeta(name);
  return m.display_unit ?? m.unit ?? "";
}

export function scaled(name: string, v: number | null | undefined) {
  if (v == null || Number.isNaN(v)) return null;
  return v * (vmeta(name).display_scale ?? 1);
}

export function fmt(v: number | null | undefined, digits = 3) {
  if (v == null || Number.isNaN(v)) return "no value";
  const a = Math.abs(v);
  if (a !== 0 && (a < 0.001 || a >= 1e5)) return v.toExponential(2);
  return Number(v.toPrecision(digits)).toString();
}

/** Gravity is a regime, never a bare number: microgravity is not zero g. Mirrors backend/record.py. */
export function gravityLabel(g: number | null | undefined) {
  if (g == null || Number.isNaN(g)) return "no value";
  if (g < 0.02) return "Microgravity (ISS)";
  if (Math.abs(g - 1) < 0.05) return "Earth 1g";
  if (Math.abs(g - 0.165) < 0.01) return "Moon gravity (1/6 g)";
  if (Math.abs(g - 0.38) < 0.01) return "Mars gravity (0.38 g)";
  return `Partial gravity (${fmt(g, 2)} g)`;
}

export function outcomeLabel(b: number | boolean | null | undefined) {
  if (b == null || (typeof b === "number" && Number.isNaN(b))) return "Outcome not recorded";
  return b ? "Burned" : "Extinguished";
}

export function fmtVar(name: string, v: number | null | undefined, digits = 3) {
  if (name === "gravity_g") return gravityLabel(v);
  if (name === "burned") return outcomeLabel(v);
  const s = scaled(name, v);
  if (s == null) return "no value";
  const u = unitOf(name);
  return `${fmt(s, digits)}${u === "%" ? "%" : u ? " " + u : ""}`;
}

export const PSI = 6.894757;
export const pct = (x: number) => `${Math.round(x * 100)}%`;
