import type { Filters, Investigation, ModelParamsResponse, Preset, ResourceDetail, ResourceList, Summary, TestPoint } from './types';

async function get<T>(path: string): Promise<T> {
  const r = await fetch(path, { headers: { Accept: 'application/json' } });
  if (!r.ok) throw new Error(`${path}: ${r.status}`);
  return r.json() as Promise<T>;
}

const FIELD: Record<string, string> = { o2_pct: 'Oxygen', psi: 'Pressure', fuel_flow: 'Fuel flow', d0_mm: 'Drop size', gravity_g: 'Gravity', fuel: 'Fuel', co2_pct: 'CO₂', he_pct: 'Helium' };

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

export interface FireCheckReq { problem: 'gas' | 'droplet'; fuel: string; o2_pct: number; psi: number; gravity_g: number; fuel_flow: number; d0_mm: number; co2_pct: number; he_pct: number }
export interface FireCheckNear { code: string; dataset: string; source_row: number | null; resource_id: string | null; fuel: string; o2_pct: number; psi: number; pressure_kpa: number; outcome: string; burned: number; distance: number; close: boolean; fuel_flow?: number; d0_mm?: number }
export interface FireCheckRes {
  problem: 'gas' | 'droplet'; label: string; zone: 'tested' | 'estimated' | 'untested'; zone_text: string; reasons: string[]; verdict: string;
  inputs: { label: string; value: string }[];
  estimate: { probability: number; low: number; high: number; outcome_yes: string; outcome_no: string; will: string; model: string } | null;
  quantities: { label: string; unit: string; meaning: string; value: number; low: number; high: number }[];
  drivers: { label: string; step: number; unit: string; change_pts: number }[];
  nearest: FireCheckNear[]; tested: { n: number; yes: number; outcome_yes: string; outcome_no: string; agrees?: boolean } | null;
  reference: { meaning: string; source: { label: string; url: string }; note: string; fuel: string; values: { N2: number; CO2: number } | null; missing: string | null } | null;
  model: { chosen: string | null; n_tests: number; n_campaigns: number; auc: number | null; brier: number | null; baseline_brier: number; investigation: string; psi_id: string; skill: number | null };
  not_in_data: string;
  suggestion: { code: string; fuel: string; o2_pct: number; psi: number; fuel_flow?: number; d0_mm?: number; co2_pct?: number; he_pct?: number } | null;
  oxygen_line: OxygenLine | null;
  next_tests: NextTest[];
}
export interface OxygenLine {
  points: { o2_pct: number; zone: 'tested' | 'estimated' | 'untested'; p: number | null; low: number | null; high: number | null }[];
  line: { o2_pct: number | null; range: [number | null, number | null] | null; max_p: number; min_p: number; falls_with_oxygen: { from_o2: number; peak_p: number } | null } | null;
  tests: { code: string; o2_pct: number; burned: number; near_settings: boolean }[];
  estimated_spans: [number, number][]; held: string[];
}
export interface NextTest {
  inputs: Record<string, number>; labels: Record<string, string>; units: Record<string, string>;
  committee_low: number; committee_high: number; nearest_test: string; nearest_burned: number; nearest_distance: number; why: string;
}
export interface ModelRow { model: string; auc?: number | null; brier?: number; log_loss?: number; accuracy?: number; mae?: number; beats_baseline?: boolean; roc?: [number, number][] | null }
export interface ModelCard {
  question: string; investigation: string; psi_id: string; n_tests: number; n_yes: number; n_campaigns: number; outcome_yes: string; outcome_no: string;
  validation: string; comparison: ModelRow[]; chosen: string | null; features: string[];
  regressions: Record<string, { label: string; unit: string; meaning: string; n_tests: number; validation: string; comparison: ModelRow[]; chosen: string | null; interval90_half_width?: number; interval90_coverage_on_unseen?: number }>;
}
export interface CheckPoint { id: string; fuel: string; o2_pct: number; psi: number; burned: number }
export interface ProblemMeta {
  label: string; question: string; fuels: string[]; investigation: string; psi_id: string; dataset: string; outcome_yes: string; outcome_no: string;
  ranges: Record<string, [number, number]>; ranges_by_fuel: Record<string, Record<string, [number, number]>>;
  points: CheckPoint[]; features: { key: string; label: string; unit: string }[]; card: ModelCard; not_in_data: string;
}
export type FireCheckMeta = Record<'gas' | 'droplet', ProblemMeta>;

export interface Zarm { label: string; material: string; doi: string; url: string; citation: string; license: string; limits: string[];
  points: { id: string; o2_frac: number; pressure_kpa: number; flow_mm_s: number; thickness_mm: number; spread_mm_s: number; spread_std: number }[] }

export interface PipelineView {
  label: string; investigation: string; psi_id: string;
  cleaning: { stage: string; n: number }[];
  clusters: {
    inputs: { key: string; label: string; unit: string }[]; k: number; bic: { k: number; bic: number }[]; ari_campaigns: number; n_campaigns: number;
    groups: { id: number; n: number; kept_burning: number; mean: Record<string, number>; fuels: Record<string, number> }[];
    points: { id: string; fuel: string; o2_pct: number; psi: number; group: number; burned: number }[];
  };
  surface: {
    fuel: string; model: string | null; held: { label: string; value: number; unit: string }[]; o2: number[]; psi: number[]; chance: (number | null)[];
    tests: { id: string; o2_pct: number; psi: number; burned: number }[]; outcome_yes: string; outcome_no: string;
  };
}
export type Pipeline = Record<'gas' | 'droplet', PipelineView>;

/* /api/fire-check/map: every NASA test with a recorded ending (oxygen × pressure × fuel lane) and where tests are needed. */
export interface MapLane { lane: number; problem: 'gas' | 'droplet'; fuel: string; kind: string; investigation: string; psi_id: string; outcome_yes: string; outcome_no: string; n: number; lit: number }
export interface MapTest { id: string; lane: number; o2: number; psi: number; lit: number; campaign: string; size: number; co2?: number; he?: number }
export interface MapNext { lane: number; o2: number; psi: number; size: number | null; low: number; high: number; nearest: string; why: string }
export interface MapCrew { key: string; label: string; o2: number; psi: number; note: string | null; needed: boolean; zone_by_lane: Record<string, 'tested' | 'estimated' | 'untested'> }
export interface FireMapAll {
  lanes: MapLane[]; tests: MapTest[]; next: MapNext[]; crew: MapCrew[];
  size_label: Record<'gas' | 'droplet', string>; size_unit: Record<'gas' | 'droplet', string>; o2_range: [number, number]; psi_range: [number, number];
}

export const api = {
  pipeline: () => get<Pipeline>('/api/fire-check/pipeline'),
  fireMap: () => get<FireMapAll>('/api/fire-check/map'),
  zarm: () => get<Zarm>('/api/outside/zarm'),
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
    const filename = /filename="?([^";]+)"?/.exec(cd)?.[1] ?? `ember.${format === 'bibtex' ? 'bib' : format}`;
    return { text: await r.text(), filename, type: r.headers.get('Content-Type') || 'text/plain' };
  },
};
