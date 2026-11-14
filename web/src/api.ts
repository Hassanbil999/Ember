import type { Filters, Investigation, ModelParamsResponse, Preset, ResourceDetail, ResourceList, Summary, TestPoint } from './types';

async function get<T>(path: string): Promise<T> {
  const r = await fetch(path, { headers: { Accept: 'application/json' } });
  if (!r.ok) throw new Error(`${path}: ${r.status}`);
  return r.json() as Promise<T>;
}

const FIELD: Record<string, string> = { o2_pct: 'Oxygen', psi: 'Pressure', fuel_flow: 'Fuel flow', d0_mm: 'Drop size', gravity_g: 'Gravity', fuel: 'Fuel', diluent: 'Rest of the air' };

/* FastAPI sends `detail` as a string, or (for validation errors) a list of {loc, msg}: make it one sentence. */
export function errorText(detail: unknown, fallback: string): string {
  if (typeof detail === 'string') return detail;
  if (Array.isArray(detail)) {
    return detail.map(d => {
      const loc = Array.isArray(d?.loc) ? d.loc[d.loc.length - 1] : '';
      return `${FIELD[loc] ?? loc}: ${String(d?.msg ?? 'invalid value').replace(/^Value error, /, '')}`.replace(/^: /, '');
    }).join('. ');
  }
  return fallback;
}

async function post<T>(path: string, body: unknown): Promise<T> {
  const r = await fetch(path, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
  if (!r.ok) {
    let msg = `The server answered ${r.status}.`;
    try { msg = errorText((await r.json()).detail, msg); } catch { /* not JSON */ }
    throw new Error(msg);
  }
  return r.json() as Promise<T>;
}

export interface SimQuery { g: number; o2: number; p: number; u: number; mat: string }

export function filterParams(f: Filters, sim?: SimQuery): URLSearchParams {
  const p = new URLSearchParams();
  if (f.q) p.set('q', f.q);
  for (const k of ['types', 'inv', 'purpose', 'fuel', 'env'] as const) for (const v of f[k]) p.append(k, v);
  if (f.credMin !== 'any') p.set('cred_min', f.credMin);
  p.set('sort', f.sort);
  if (sim) { p.set('g', String(sim.g)); p.set('o2', String(sim.o2)); p.set('psi', String(sim.p)); p.set('u', String(sim.u)); p.set('material', sim.mat); }
  return p;
}

export interface SimResponse {
  result: { ub: number; ueff: number; xlim: number; margin: number; burns: boolean; regime: 'burns' | 'quench' | 'blowoff'; spread: number };
  D: number; n: number; t_out: number | null; t_end: number | null; I: number[]; x_mm: number[];
  coverage: { kind: string; text: string }; nearest: (TestPoint & { distance: number; match: string })[];
}

export interface AskPassage { resource_id: string; page: number | null; title: string; section: string | null; excerpt: string }
export interface AskResponse {
  question: string; answer: string; covered: boolean; source: string; model: string | null; note?: string;
  citations: { resource_id: string; page: number | null; title: string }[]; passages: AskPassage[];
}

export interface FireCheckReq { problem: 'gas' | 'droplet'; fuel: string; o2_pct: number; psi: number; gravity_g: number; fuel_flow: number; d0_mm: number; diluent: 'N2' | 'CO2' | 'He' }
export interface FireCheckNear { code: string; dataset: string; source_row: number | null; resource_id: string | null; fuel: string; o2_pct: number; psi: number; pressure_kpa: number; outcome: string; burned: number; distance: number; close: boolean; fuel_flow?: number; d0_mm?: number }
export interface FireCheckRes {
  problem: 'gas' | 'droplet'; label: string; zone: 'tested' | 'estimated' | 'untested'; zone_text: string; reasons: string[]; verdict: string;
  inputs: { label: string; value: string }[];
  estimate: { probability: number; low: number; high: number; outcome_yes: string; outcome_no: string; will: string; model: string } | null;
  quantities: { label: string; unit: string; meaning: string; value: number; low: number; high: number }[];
  drivers: { label: string; step: number; unit: string; change_pts: number }[];
  nearest: FireCheckNear[]; tested: { n: number; yes: number; agrees?: boolean } | null;
  reference: { meaning: string; source: { label: string; url: string }; note: string; fuel: string; values: { N2: number; CO2: number } | null; missing: string | null } | null;
  model: { chosen: string | null; n_tests: number; n_campaigns: number; auc: number | null; brier: number | null; baseline_brier: number; investigation: string; psi_id: string };
}
export interface ModelRow { model: string; auc?: number | null; brier?: number; log_loss?: number; accuracy?: number; mae?: number; beats_baseline?: boolean }
export interface ModelCard {
  question: string; investigation: string; psi_id: string; n_tests: number; n_yes: number; n_campaigns: number; outcome_yes: string; outcome_no: string;
  validation: string; comparison: ModelRow[]; chosen: string | null; features: string[];
  regressions: Record<string, { label: string; unit: string; meaning: string; n_tests: number; validation: string; comparison: ModelRow[]; chosen: string | null; interval90_half_width?: number; interval90_coverage_on_unseen?: number }>;
}
export interface CheckPoint { id: string; fuel: string; o2_pct: number; psi: number; burned: number }
export interface ProblemMeta {
  label: string; question: string; fuels: string[]; investigation: string; psi_id: string; dataset: string; outcome_yes: string; outcome_no: string;
  ranges: Record<string, [number, number]>; ranges_by_fuel: Record<string, Record<string, [number, number]>>;
  points: CheckPoint[]; features: { key: string; label: string; unit: string }[]; card: ModelCard;
}
export type FireCheckMeta = Record<'gas' | 'droplet', ProblemMeta>;

export const api = {
  fireCheckMeta: () => get<FireCheckMeta>('/api/fire-check/meta'),
  fireCheck: (r: FireCheckReq) => post<FireCheckRes>('/api/fire-check', r),
  dataTables: () => get<ResourceList>('/api/resources?types=data&sort=cred&page_size=200').then(r => r.items),
  async fireCheckReport(r: FireCheckReq): Promise<{ text: string; filename: string }> {
    const res = await fetch('/api/fire-check/report', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(r) });
    if (!res.ok) {
      let msg = `The server answered ${res.status}.`;
      try { msg = errorText((await res.json()).detail, msg); } catch { /* not JSON */ }
      throw new Error(msg);
    }
    const cd = res.headers.get('Content-Disposition') || '';
    return { text: await res.text(), filename: /filename="?([^";]+)"?/.exec(cd)?.[1] ?? 'fire-check-report.html' };
  },
  resourceAll: (id: string) => get<ResourceDetail>(`/api/resources/${encodeURIComponent(id)}?points_limit=2000`),
  async ask(question: string): Promise<AskResponse | { detail: string; passages: AskPassage[] }> {
    const r = await fetch('/api/ai/ask', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ question }) });
    if (r.status === 503) return r.json();
    if (!r.ok) throw new Error(`ask: ${r.status}`);
    return r.json();
  },
  simulate: (s: SimQuery) => post<SimResponse>('/api/simulate', { g: s.g, o2: s.o2, psi: s.p, u: s.u, material: s.mat }),
  presets: () => get<Preset[]>('/api/presets'),
  investigations: () => get<Investigation[]>('/api/investigations'),
  modelParams: () => get<ModelParamsResponse>('/api/model-params'),
  simPoints: () => get<{ items: TestPoint[] }>('/api/test-points?simulatable=true').then(r => r.items),
  resources: (f: Filters, sim: SimQuery) => get<ResourceList>('/api/resources?' + filterParams(f, sim).toString() + '&page_size=200'),
  resource: (id: string) => get<ResourceDetail>(`/api/resources/${encodeURIComponent(id)}`),
  summary: (f: Filters, sim: SimQuery) => post<Summary>('/api/ai/summary', {
    q: f.q, types: f.types, inv: f.inv, purpose: f.purpose, fuel: f.fuel, env: f.env, cred_min: f.credMin, sort: f.sort,
    g: sim.g, o2: sim.o2, psi: sim.p, u: sim.u, material: sim.mat,
  }),
  async exportFile(ids: string[], format: 'csv' | 'json' | 'bibtex'): Promise<{ text: string; filename: string; type: string }> {
    const r = await fetch('/api/export', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ resource_ids: ids, format }) });
    if (!r.ok) throw new Error(`export: ${r.status}`);
    const cd = r.headers.get('Content-Disposition') || '';
    const filename = /filename="?([^";]+)"?/.exec(cd)?.[1] ?? `freefall-atlas.${format === 'bibtex' ? 'bib' : format}`;
    return { text: await r.text(), filename, type: r.headers.get('Content-Type') || 'text/plain' };
  },
};
