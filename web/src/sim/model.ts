/* SPEC §8 model, ported line for line from prototype/index.html. The server (backend/sim/model.py) runs the
   same model and is the reference; this client copy gives instant feedback while a slider moves. */
import type { Material, ModelParams, TestPoint } from '../types';

export const DT = 0.05, SAMPLE_MM = 100, IGN = 1.5, PSI_TO_KPA = 6.89476;

export const DEFAULT_PARAMS: Record<Material, ModelParams> = {
  fabric: { xmin: 15.5, ustar: 8, kl: 1.5, kh: 0.78, c: 0.46, pexp: 0.15 },
  pmma: { xmin: 16.0, ustar: 5, kl: 1.5, kh: 0.78, c: 0.30, pexp: 0.15 },
};

export interface SimState { g: number; o2: number; p: number; u: number; mat: Material }
export interface ModelResult { ub: number; ueff: number; xlim: number; margin: number; burns: boolean; regime: 'burns' | 'quench' | 'blowoff'; spread: number }
export interface Series { r: ModelResult; D: number; n: number; I: Float32Array; X: Float32Array; tOut: number | null; tEnd: number | null }

export function model(s: SimState, P: Record<Material, ModelParams>): ModelResult {
  const m = P[s.mat];
  const ub = 30 * Math.sqrt(Math.max(s.g, 0));
  const ueff = Math.sqrt(s.u * s.u + ub * ub + 0.09);
  const L = Math.log(ueff / m.ustar);
  const xlim = (m.xmin + (L < 0 ? m.kl : m.kh) * L * L) * Math.pow(14.7 / s.p, m.pexp ?? 0.15);
  const margin = s.o2 - xlim;
  const burns = margin >= 0;
  return { ub, ueff, xlim, margin, burns, regime: burns ? 'burns' : (L < 0 ? 'quench' : 'blowoff'), spread: burns ? m.c * margin * (ueff / (ueff + 5)) : 0 };
}

export const limitAt = (u: number, s: SimState, P: Record<Material, ModelParams>) => model({ ...s, u, o2: 0 }, P).xlim;

/* Time series of one burn: igniter on for 1.5 s, 10 cm sample. */
export function simulate(s: SimState, P: Record<Material, ModelParams>): Series {
  const r = model(s, P);
  const tBurn = r.burns ? SAMPLE_MM / Math.max(r.spread, 0.01) + 1.5 : Infinity;
  const D = r.burns ? Math.min(240, Math.max(10, Math.ceil((tBurn + 4) / 5) * 5)) : 10;
  const n = Math.round(D / DT) + 1;
  const I = new Float32Array(n), X = new Float32Array(n);
  let x = 0, st: 'lit' | 'out' | 'done' = 'lit', tOut: number | null = null, tEnd: number | null = null, lv = 0;
  for (let k = 0; k < n; k++) {
    const t = k * DT, ign = t < IGN;
    if (st === 'lit') {
      const target = r.burns ? 1 : (ign ? 0.55 : 0);
      lv += (target - lv) * Math.min(1, (target > lv ? 2.2 : 1.4) * DT);
      x += r.spread * Math.min(1, lv * 1.15) * DT;
      if (!r.burns && !ign && lv < 0.03) { st = 'out'; lv = 0; tOut = t; }
      if (x >= SAMPLE_MM) { x = SAMPLE_MM; st = 'done'; tEnd = t; }
    } else if (st === 'done') { lv *= Math.max(0, 1 - 1.8 * DT); }
    I[k] = lv; X[k] = x;
  }
  return { r, D, n, I, X, tOut, tEnd };
}

/* §8.3 distance to a measured point; a missing pressure or flow is left out of the sum. */
export function recDist(rec: TestPoint, s: SimState): number {
  if (rec.o2_pct == null) return Infinity;
  let d2 = Math.pow((s.g - (rec.gravity_g ?? 0)) / 0.3, 2) + Math.pow((s.o2 - rec.o2_pct) / 8, 2);
  if (rec.pressure_kpa != null) d2 += Math.pow((s.p * PSI_TO_KPA - rec.pressure_kpa) / 30, 2);
  if (rec.flow_cm_s != null) d2 += Math.pow(Math.log((s.u + 0.3) / (rec.flow_cm_s + 0.3)) / 1.2, 2);
  if (rec.material !== s.mat) d2 += 2.25;
  return Math.sqrt(d2);
}

export const fitLabel = (d: number) => d < 1 ? 'close' : d < 2.5 ? 'partial' : 'distant';
export const fmtU = (u: number | null) => u == null ? 'flow not reported' : u === 0 ? 'off' : (u < 1 ? u.toFixed(2) : u < 10 ? u.toFixed(1) : u.toFixed(0)) + ' cm/s';
export const fmtT = (t: number) => (t < 10 ? t.toFixed(1) : t.toFixed(0)) + ' s';
export function gName(g: number) { for (const [v, n] of [[0, 'micro-g'], [0.166, 'Moon'], [0.38, 'Mars'], [1, 'Earth']] as const) if (Math.abs(g - v) < 0.012) return n; return ''; }
export const uFromS = (s: number) => s <= 0 ? 0 : 0.1 * Math.pow(500, (s - 1) / 99);
export const sFromU = (u: number) => u < 0.1 ? 0 : Math.round(1 + 99 * Math.log(u / 0.1) / Math.log(500));
export const at = (arr: Float32Array, t: number, n: number) => arr[Math.min(n - 1, Math.max(0, Math.round(t / DT)))];
export const fmtNum = (v: number | null | undefined, digits = 3) => v == null ? '—' : String(Number(v.toPrecision(digits)));
