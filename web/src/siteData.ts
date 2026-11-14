/* The live facts every page quotes (test counts, tables, model scores), fetched once and shared. Nothing here is
   hard-coded: if the API is down the pages show no number rather than a stale one. */
import { useEffect, useState } from 'react';
import { api, type FireCheckMeta, type FireCheckReq, type FireCheckRes, type ModelRow } from './api';
import type { Preset, Resource } from './types';

export interface SiteData { meta: FireCheckMeta; tables: Resource[]; presets: Preset[] }

let cache: Promise<SiteData> | null = null;
const load = () => (cache ??= Promise.all([api.fireCheckMeta(), api.dataTables(), api.presets()])
  .then(([meta, tables, presets]) => ({ meta, tables, presets }))
  .catch(e => { cache = null; throw e; }));

export function useSiteData(): { data: SiteData | null; err: string | null } {
  const [data, setData] = useState<SiteData | null>(null);
  const [err, setErr] = useState<string | null>(null);
  useEffect(() => {
    let live = true;
    load().then(d => { if (live) setData(d); }).catch(e => { if (live) setErr(String(e.message || e)); });
    return () => { live = false; };
  }, []);
  return { data, err };
}

export const best = (rows: ModelRow[], chosen: string | null) => rows.find(r => r.model === chosen) ?? null;
export const fmt = (n: number) => n.toLocaleString('en-US');

export function facts(d: SiteData) {
  const withTests = d.tables.filter(t => t.points_count > 0);
  const gas = d.meta.gas.card, drop = d.meta.droplet.card;
  return {
    tests: d.tables.reduce((s, t) => s + t.points_count, 0),
    tables: d.tables.length,
    experiments: new Set(d.tables.map(t => t.psi_id).filter(Boolean)).size,   // CFI-G normal and inverse are one experiment
    tablesWithTests: withTests.length,
    outcome: gas.n_tests + drop.n_tests,
    gas, drop,
    gasBest: best(gas.comparison, gas.chosen), dropBest: best(drop.comparison, drop.chosen),
  };
}

/* The landing page's worked example: Moon-base air in microgravity, a small diluted ethane leak. The answer is
   whatever the engine says today (zone, estimate, the NASA tests behind it); nothing about it is stored here. */
export const EXAMPLE: FireCheckReq = { problem: 'gas', fuel: '30% ethane', o2_pct: 34, psi: 8.2, fuel_flow: 0.5, d0_mm: 3, diluent: 'N2', gravity_g: 0 };
export const exampleLink = '/engine/check?problem=gas&fuel=30%25+ethane&o2=34&psi=8.2&flow=0.5&g=0';

let exCache: Promise<FireCheckRes> | null = null;
export function useExample() {
  const [res, setRes] = useState<FireCheckRes | null>(null);
  useEffect(() => {
    let live = true;
    (exCache ??= api.fireCheck(EXAMPLE).catch(e => { exCache = null; throw e; })).then(r => { if (live) setRes(r); }).catch(() => { /* shown without it */ });
    return () => { live = false; };
  }, []);
  return res;
}

/* An optional PDF the team can drop into web/public. Unknown paths return the app's index.html, so check the type. */
export function usePdf(path: string) {
  const [ok, setOk] = useState(false);
  useEffect(() => {
    const stop = new AbortController();
    fetch(path, { signal: stop.signal })
      .then(r => { setOk(r.ok && (r.headers.get('content-type') || '').includes('pdf')); stop.abort(); })   // headers are enough
      .catch(() => { /* aborted or missing */ });
    return () => stop.abort();
  }, [path]);
  return ok;
}
