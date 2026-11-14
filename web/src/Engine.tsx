/* The engine (/engine/*): one shell with five sections. The simulator's settings and the data filters live in
   the URL query on their own pages so a view can be shared: /engine/simulator?g=0.166&o2=34&p=8.2&u=10&mat=fabric
   and /engine/data?types=paper. The fire check keeps its own inputs in its URL. */
import { useCallback, useEffect, useRef, useState } from 'react';
import { api } from './api';
import { Link, navigate, title, usePath } from './router';
import { sim, useSim } from './sim/store';
import { isWide } from './sim/stage';
import type { Filters, Investigation, Material } from './types';
import { emptyFilters, FindDataView } from './views/FindData';
import { FireCheckPage } from './views/FireCheck';
import { Models } from './views/Models';
import { Overview } from './views/Overview';
import { SimulateView } from './views/Simulate';

type Section = 'overview' | 'check' | 'sim' | 'data' | 'models';
const SECTIONS: { key: Section; path: string; label: string }[] = [
  { key: 'overview', path: '/engine', label: 'Overview' },
  { key: 'check', path: '/engine/check', label: 'Fire check' },
  { key: 'sim', path: '/engine/simulator', label: 'Simulator' },
  { key: 'data', path: '/engine/data', label: 'Find data' },
  { key: 'models', path: '/engine/models', label: 'Models' },
];
const sectionOf = (path: string): Section => SECTIONS.find(s => s.key !== 'overview' && path.startsWith(s.path))?.key ?? 'overview';
const LIST_KEYS = ['types', 'inv', 'purpose', 'fuel', 'env'] as const;

function readUrl(section: Section): Filters {
  const q = new URLSearchParams(location.search);
  const f = emptyFilters(q.get('sort') || 'fit:moon');
  if (section !== 'sim' && section !== 'data') return f;            // other pages use the query for their own inputs
  const num = (k: string) => { const v = q.get(k); return v != null && v !== '' && isFinite(+v) ? +v : undefined; };
  const patch: Record<string, unknown> = {};
  for (const [k, lo, hi] of [['g', 0, 1], ['o2', 15, 45], ['p', 4, 15], ['u', 0, 50]] as const) {
    const v = num(k); if (v !== undefined) patch[k] = Math.min(hi, Math.max(lo, v));
  }
  const mat = q.get('mat'); if (mat === 'fabric' || mat === 'pmma') patch.mat = mat as Material;
  if (Object.keys(patch).length) sim.set({ ...patch, preset: q.get('preset') || 'custom' }, true);
  f.q = q.get('q') || '';
  for (const k of LIST_KEYS) f[k] = (q.get(k) || '').split(',').filter(Boolean);
  const c = q.get('cred'); if (c === 'verified' || c === 'medium' || c === 'high') f.credMin = c;
  return f;
}

function writeUrl(f: Filters, section: Section) {
  const path = section === 'sim' ? '/engine/simulator' : '/engine/data';
  if (location.pathname !== path) return;
  const st = sim.params, q = new URLSearchParams();
  q.set('g', String(+st.g.toFixed(3))); q.set('o2', String(st.o2)); q.set('p', String(st.p)); q.set('u', String(+st.u.toFixed(2)));
  q.set('mat', st.mat); q.set('preset', st.preset);
  if (f.q) q.set('q', f.q);
  for (const k of LIST_KEYS) if (f[k].length) q.set(k, f[k].join(','));
  if (f.credMin !== 'any') q.set('cred', f.credMin);
  if (f.sort !== 'fit:moon') q.set('sort', f.sort);
  const url = path + '?' + q.toString();
  if (location.pathname + location.search !== url) { try { history.replaceState(null, '', url); } catch { /* sandboxed */ } }
}

export function Engine() {
  const s = useSim();
  const path = usePath();
  const section = sectionOf(path);
  const [filters, setFilters] = useState<Filters>(() => readUrl(section));
  const [investigations, setInvestigations] = useState<Investigation[]>([]);
  const [panels, setPanelsState] = useState({ l: true, r: true });
  const [api_, setApi] = useState<'pending' | 'ok' | 'down'>('pending');
  const [focus, setFocus] = useState<{ code: string; rid: string; n: number } | null>(null);
  const [, setWide] = useState(isWide());

  useEffect(() => {
    Promise.all([api.presets(), api.investigations(), api.modelParams(), api.simPoints()])
      .then(([presets, invs, params, points]) => {
        sim.setPresets(presets); setInvestigations(invs); sim.setModelParams(params); sim.setPoints(points); setApi('ok');
      })
      .catch(() => setApi('down'));
  }, []);

  useEffect(() => { title(SECTIONS.find(x => x.key === section)!.label); }, [section]);
  useEffect(() => {
    const onResize = () => setWide(isWide());
    window.addEventListener('resize', onResize);
    return () => window.removeEventListener('resize', onResize);
  }, []);

  // keep the URL in step with the simulator and the filters (debounced while a slider moves)
  const timer = useRef<number>();
  useEffect(() => {
    if (section !== 'sim' && section !== 'data') return;
    window.clearTimeout(timer.current);
    timer.current = window.setTimeout(() => writeUrl(filters, section), 200);
  }, [filters, section, s.version]);

  function toData() {
    const f = emptyFilters('near');
    f.fuel = ['solid'];
    f.env = [s.params.g < 0.02 ? 'space' : s.params.g > 0.9 ? 'earth' : 'partial'];
    setFilters(f); navigate('/engine/data');
  }
  function openTest(code: string, rid: string | null) {
    setFilters(emptyFilters(filters.sort === 'near' ? 'cred' : filters.sort));
    if (rid) setFocus({ code, rid, n: Date.now() });
    navigate('/engine/data');
  }
  const simulate = useCallback((code: string) => { if (sim.load(code)) navigate('/engine/simulator'); }, []);

  return (
    <>
      <header className="top">
        <div className="brand"><h1><Link to="/" title="The Oxygen Edge home">The Oxygen Edge</Link></h1><span>Engine</span></div>
        <nav className="tabs" aria-label="Engine">
          {SECTIONS.map(x => <Link key={x.key} to={x.path} id={'nav-' + x.key} aria-current={section === x.key ? 'page' : undefined}>{x.label}</Link>)}
        </nav>
        <nav className="sitelinks" aria-label="Site">
          <Link to="/research">Research</Link><Link to="/presentation">Presentation</Link>
          <span className={'apidot ' + api_} title={api_ === 'ok' ? 'API online' : api_ === 'down' ? 'API not reachable' : 'Connecting'}>
            <i aria-hidden="true" />{api_ === 'ok' ? 'API online' : api_ === 'down' ? 'API offline' : '…'}</span>
        </nav>
        {api_ === 'down' && <span className="err" role="alert">Could not reach the API. The simulator still runs on built-in defaults.</span>}
      </header>
      <main>
        {section === 'overview' && <Overview />}
        {section === 'check' && <FireCheckPage onOpenTest={openTest} />}
        {section === 'models' && <Models />}
        <SimulateView active={section === 'sim'} panelL={panels.l} panelR={panels.r} setPanels={(l, r) => setPanelsState({ l, r })} onFindData={toData} />
        <FindDataView active={section === 'data'} filters={filters} setFilters={setFilters} investigations={investigations} onSimulate={simulate} focus={focus} />
      </main>
    </>
  );
}
