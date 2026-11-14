/* App shell (prototype header + tabs). Routing: #simulate and #data. Simulator settings and filters live in
   the URL query so a view can be shared: ?g=0.166&o2=34&p=8.2&u=10&mat=fabric&preset=moon&types=paper#data */
import { useCallback, useEffect, useRef, useState } from 'react';
import { api } from './api';
import { sim, useSim } from './sim/store';
import { isWide } from './sim/stage';
import type { Filters, Investigation, Material } from './types';
import { emptyFilters, FindDataView } from './views/FindData';
import { SimulateView } from './views/Simulate';

type Tab = 'sim' | 'data';
const tabFromHash = (): Tab => (location.hash.startsWith('#data') ? 'data' : 'sim');
const LIST_KEYS = ['types', 'inv', 'purpose', 'fuel', 'env'] as const;

function readUrl(): Filters {
  const q = new URLSearchParams(location.search);
  const num = (k: string) => { const v = q.get(k); return v != null && v !== '' && isFinite(+v) ? +v : undefined; };
  const patch: Record<string, unknown> = {};
  for (const [k, lo, hi] of [['g', 0, 1], ['o2', 15, 45], ['p', 4, 15], ['u', 0, 50]] as const) {
    const v = num(k); if (v !== undefined) patch[k] = Math.min(hi, Math.max(lo, v));
  }
  const mat = q.get('mat'); if (mat === 'fabric' || mat === 'pmma') patch.mat = mat as Material;
  if (Object.keys(patch).length) sim.set({ ...patch, preset: q.get('preset') || 'custom' }, true);
  const f = emptyFilters(q.get('sort') || 'fit:moon');
  f.q = q.get('q') || '';
  for (const k of LIST_KEYS) f[k] = (q.get(k) || '').split(',').filter(Boolean);
  const c = q.get('cred'); if (c === 'verified' || c === 'medium' || c === 'high') f.credMin = c;
  return f;
}

function writeUrl(f: Filters, tab: Tab) {
  const st = sim.params, q = new URLSearchParams();
  q.set('g', String(+st.g.toFixed(3))); q.set('o2', String(st.o2)); q.set('p', String(st.p)); q.set('u', String(+st.u.toFixed(2)));
  q.set('mat', st.mat); q.set('preset', st.preset);
  if (f.q) q.set('q', f.q);
  for (const k of LIST_KEYS) if (f[k].length) q.set(k, f[k].join(','));
  if (f.credMin !== 'any') q.set('cred', f.credMin);
  if (f.sort !== 'fit:moon') q.set('sort', f.sort);
  const url = '?' + q.toString() + (tab === 'sim' ? '#simulate' : '#data');
  if (location.search + location.hash !== url) { try { history.replaceState(null, '', url); } catch { /* sandboxed */ } }
}

export function App() {
  const s = useSim();
  const [tab, setTabState] = useState<Tab>(tabFromHash);
  const [filters, setFilters] = useState<Filters>(() => readUrl());
  const [investigations, setInvestigations] = useState<Investigation[]>([]);
  const [panels, setPanelsState] = useState({ l: true, r: true });
  const [loadErr, setLoadErr] = useState<string | null>(null);
  const [, setWide] = useState(isWide());

  useEffect(() => {
    Promise.all([api.presets(), api.investigations(), api.modelParams(), api.simPoints()])
      .then(([presets, invs, params, points]) => {
        sim.setPresets(presets); setInvestigations(invs); sim.setModelParams(params); sim.setPoints(points);
      })
      .catch(e => setLoadErr(String(e.message || e)));
  }, []);

  const setTab = useCallback((t: Tab) => { setTabState(t); }, []);
  useEffect(() => {
    const onHash = () => setTabState(tabFromHash());
    const onResize = () => setWide(isWide());
    window.addEventListener('hashchange', onHash); window.addEventListener('resize', onResize);
    return () => { window.removeEventListener('hashchange', onHash); window.removeEventListener('resize', onResize); };
  }, []);

  // keep the URL in step with the tab, the filters and the simulator (debounced while a slider moves)
  const timer = useRef<number>();
  useEffect(() => {
    window.clearTimeout(timer.current);
    timer.current = window.setTimeout(() => writeUrl(filters, tab), 200);
  }, [filters, tab, s.version]);

  function toData() {
    const f = emptyFilters('near');
    f.fuel = ['solid'];
    f.env = [s.params.g < 0.02 ? 'space' : s.params.g > 0.9 ? 'earth' : 'partial'];
    setFilters(f); setTab('data');
  }
  const simulate = useCallback((code: string) => { if (sim.load(code)) setTab('sim'); }, [setTab]);

  function onTabKey(e: React.KeyboardEvent) {
    if (e.key === 'ArrowRight' || e.key === 'ArrowLeft') {
      const n: Tab = tab === 'sim' ? 'data' : 'sim'; setTab(n);
      document.getElementById('tab-' + n)?.focus();
    }
  }

  return (
    <>
      <header className="top">
        <div className="brand"><h1>Freefall Atlas</h1><span>NASA Space Apps 2026</span></div>
        <div className="tabs" role="tablist" aria-label="Views" onKeyDown={onTabKey}>
          <button role="tab" id="tab-sim" aria-controls="view-sim" aria-selected={tab === 'sim'} tabIndex={tab === 'sim' ? 0 : -1} onClick={() => setTab('sim')}>Simulate</button>
          <button role="tab" id="tab-data" aria-controls="view-data" aria-selected={tab === 'data'} tabIndex={tab === 'data' ? 0 : -1} onClick={() => setTab('data')}>Find data</button>
        </div>
        {loadErr && <span className="err" role="alert">Could not reach the API ({loadErr}). The simulator still runs on built-in defaults.</span>}
      </header>
      <main>
        <SimulateView active={tab === 'sim'} panelL={panels.l} panelR={panels.r} setPanels={(l, r) => setPanelsState({ l, r })} onFindData={toData} />
        <FindDataView active={tab === 'data'} filters={filters} setFilters={setFilters} investigations={investigations} onSimulate={simulate} />
      </main>
    </>
  );
}
