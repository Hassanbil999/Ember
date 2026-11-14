/* Find data view (prototype "DATA FINDER"), wired to /api/resources, /api/resources/{id}, /api/ai/summary
   and /api/export. Filtering, facets and sorting run on the server. */
import { Fragment, useEffect, useRef, useState } from 'react';
import { api } from '../api';
import { ExportDialog } from '../components/ExportDialog';
import { useSim } from '../sim/store';
import type { Filters, Investigation, Resource, ResourceDetail, ResourceList, Summary, TestPoint } from '../types';

export const TYPES: Record<string, { label: string; icon: string }> = {
  data: { label: 'Experiment data', icon: 'M4 5h16v14H4zM4 10h16M4 15h16M10 5v14' },
  paper: { label: 'Research paper', icon: 'M7 3h7l5 5v13H7zM14 3v5h5M10 13h6M10 17h6' },
  report: { label: 'Report', icon: 'M9 4h6v3H9zM6 6h3M15 6h3v15H6V6M9 12h6M9 16h4' },
  slides: { label: 'Presentation', icon: 'M3 4h18v12H3zM12 16v4M8 20h8M7 12l3-3 3 2 4-4' },
  video: { label: 'Video', icon: 'M3 6h13v12H3zM16 10l5-3v10l-5-3' },
  image: { label: 'Image', icon: 'M3 5h18v14H3zM3 16l5-5 4 4 3-3 6 6' },
  news: { label: 'News & articles', icon: 'M4 5h13v14H6a2 2 0 0 1-2-2zM17 9h3v8a2 2 0 0 1-2 2M7 9h7M7 13h7M7 16h4' },
};
export const PURPOSE: Record<string, string> = { prevent: 'Prevent fires', detect: 'Detect smoke', suppress: 'Put out fires', basics: 'Combustion basics' };
export const FUEL: Record<string, string> = { solid: 'Solid', liquid: 'Liquid droplet', gas: 'Gas' };
export const ENV: Record<string, string> = { space: 'Spacecraft (0 g)', partial: 'Moon or Mars', earth: 'Earth' };
const CRED: Record<string, string> = { any: 'Any, including unverified', verified: 'Verified sources only', medium: 'Medium and higher', high: 'High only' };
const CHEV = <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true"><path d="M6 9l6 6 6-6" /></svg>;

export const emptyFilters = (sort = 'fit:moon'): Filters => ({ q: '', types: [], inv: [], purpose: [], fuel: [], env: [], credMin: 'any', sort });

function Icon({ type }: { type: string }) {
  const T = TYPES[type] ?? TYPES.data;
  return <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinejoin="round" aria-hidden="true"><path d={T.icon} />{type === 'image' && <circle cx="16" cy="9" r="1.5" />}</svg>;
}

interface Props {
  active: boolean;
  filters: Filters; setFilters: (f: Filters) => void;
  investigations: Investigation[];
  onSimulate: (code: string) => void;
}

export function FindDataView({ active, filters: F, setFilters, investigations, onSimulate }: Props) {
  const s = useSim();
  const [data, setData] = useState<ResourceList | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [summary, setSummary] = useState<Summary | null>(null);
  const [open, setOpen] = useState<Set<string>>(new Set());
  const [details, setDetails] = useState<Record<string, ResourceDetail>>({});
  const [basket, setBasket] = useState<Set<string>>(new Set());
  const [menu, setMenu] = useState<string | null>(null);
  const [exporting, setExporting] = useState(false);
  const [flash, setFlash] = useState<string | null>(null);
  const titles = useRef<Record<string, string>>({});
  const st = s.params;
  const simQ = { g: st.g, o2: st.o2, p: st.p, u: st.u, mat: st.mat };
  const simKey = F.sort === 'near' ? JSON.stringify(simQ) : '';

  // results: debounce typing, fetch immediately otherwise
  useEffect(() => {
    if (!active) return;
    let stale = false;
    const t = setTimeout(() => {
      api.resources(F, simQ).then(d => { if (!stale) { setData(d); setErr(null); d.items.forEach(r => { titles.current[r.id] = r.title; }); } })
        .catch(e => { if (!stale) setErr(String(e.message || e)); });
      setSummary(null);
      api.summary(F, simQ).then(x => { if (!stale) setSummary(x); }).catch(() => { if (!stale) setSummary(null); });
    }, F.q ? 160 : 0);
    return () => { stale = true; clearTimeout(t); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [active, JSON.stringify(F), simKey]);

  useEffect(() => {
    const close = (e: MouseEvent) => { if (!(e.target as Element).closest('.dd')) setMenu(null); };
    const esc = (e: KeyboardEvent) => { if (e.key === 'Escape') setMenu(null); };
    document.addEventListener('click', close); document.addEventListener('keydown', esc);
    return () => { document.removeEventListener('click', close); document.removeEventListener('keydown', esc); };
  }, []);

  const set = (patch: Partial<Filters>) => setFilters({ ...F, ...patch });
  const toggle = (key: 'types' | 'inv' | 'purpose' | 'fuel' | 'env', v: string) =>
    set({ [key]: F[key].includes(v) ? F[key].filter(x => x !== v) : [...F[key], v] } as Partial<Filters>);

  async function toggleOpen(id: string) {
    const n = new Set(open);
    if (n.has(id)) n.delete(id); else {
      n.add(id);
      if (!details[id]) api.resource(id).then(d => setDetails(x => ({ ...x, [id]: d }))).catch(() => undefined);
    }
    setOpen(n);
  }
  function cite(id: string) {
    if (!open.has(id)) toggleOpen(id);
    setFlash(id);
    setTimeout(() => document.getElementById('res-' + id)?.scrollIntoView({ block: 'center', behavior: 'smooth' }), 50);
    setTimeout(() => setFlash(null), 1300);
  }

  const DD = [
    { key: 'inv' as const, label: 'Investigation', opts: Object.fromEntries(investigations.map(i => [i.slug, i.name])) },
    { key: 'purpose' as const, label: 'Purpose', opts: PURPOSE },
    { key: 'fuel' as const, label: 'Fuel', opts: FUEL },
    { key: 'env' as const, label: 'Environment', opts: ENV },
  ];
  const anyF = F.types.length || F.inv.length || F.purpose.length || F.fuel.length || F.env.length || F.credMin !== 'any' || F.q;
  const list = data?.items ?? [];
  const invName = (slug: string | null) => investigations.find(i => i.slug === slug)?.name ?? slug ?? '';

  return (
    <section id="view-data" className="view" role="tabpanel" aria-labelledby="tab-data" hidden={!active}>
      <div className="dwrap">
        <div className="dtop">
          <div className="r1">
            <label className="sr" htmlFor="q">Search</label>
            <input className="search" id="q" type="search" placeholder="Search titles, investigations, materials" autoComplete="off" value={F.q} onChange={e => set({ q: e.target.value })} />
            <label className="sr" htmlFor="sort">Sort</label>
            <select id="sort" className="sel" value={F.sort} onChange={e => set({ sort: e.target.value })}>
              {s.presets.map(p => <option key={p.key} value={'fit:' + p.key}>Best fit for {p.label}</option>)}
              <option value="cred">Most credible</option>
              <option value="near">Closest to simulator settings</option>
              <option value="new">Newest first</option>
            </select>
          </div>
          <div className="chips" id="types" role="group" aria-label="Type of data">
            <button className="chip" data-k="" aria-pressed={F.types.length === 0} onClick={() => set({ types: [] })}>All types</button>
            {Object.entries(TYPES).map(([k, t]) => (
              <button key={k} className="chip" data-k={k} aria-pressed={F.types.includes(k)} onClick={() => toggle('types', k)}>
                {t.label}<span className="c">{data?.facets.types[k] ?? ''}</span>
              </button>
            ))}
          </div>
          <div className="dds" id="dds">
            {DD.map(d => {
              const n = F[d.key].length;
              return (
                <div className="dd" key={d.key}>
                  <button className="dd-btn" aria-expanded={menu === d.key} aria-controls={'dd-' + d.key} data-dd={d.key} data-n={n}
                    onClick={e => { e.stopPropagation(); setMenu(menu === d.key ? null : d.key); }}>
                    {d.label} <span className="cnt">{n ? '· ' + n : ''}</span>{CHEV}
                  </button>
                  <div className="dd-menu" id={'dd-' + d.key} hidden={menu !== d.key} role="group" aria-label={d.label}>
                    {Object.entries(d.opts).map(([k, v]) => (
                      <label key={k}><input type="checkbox" name={d.key} value={k} checked={F[d.key].includes(k)} onChange={() => toggle(d.key, k)} /> {v}</label>
                    ))}
                  </div>
                </div>
              );
            })}
            <div className="dd">
              <button className="dd-btn" aria-expanded={menu === 'credMin'} aria-controls="dd-credMin" data-dd="credMin" data-n={F.credMin === 'any' ? 0 : 1}
                onClick={e => { e.stopPropagation(); setMenu(menu === 'credMin' ? null : 'credMin'); }}>
                Credibility <span className="cnt">{F.credMin === 'any' ? '' : '· ' + { verified: 'verified', medium: 'medium+', high: 'high' }[F.credMin]}</span>{CHEV}
              </button>
              <div className="dd-menu" id="dd-credMin" hidden={menu !== 'credMin'} role="group" aria-label="Credibility">
                {Object.entries(CRED).map(([k, v]) => (
                  <label key={k}><input type="radio" name="credMin" value={k} checked={F.credMin === k} onChange={() => set({ credMin: k as Filters['credMin'] })} /> {v}</label>
                ))}
              </div>
            </div>
            <button className="link" id="clearAll" hidden={!anyF} onClick={() => setFilters(emptyFilters(F.sort))}>Clear filters</button>
          </div>
        </div>

        <div className="sumline" aria-live="polite">
          <div className="count" id="count">{data ? <>{data.total} result{data.total === 1 ? '' : 's'}<span>{data.counts.high} high credibility · {data.counts.unverified} unverified</span></> : ' '}</div>
          <p id="aiText"><span className="ai">AI</span>{summary ? <Cited text={summary.text} ids={summary.citations} titles={titles.current} onCite={cite} /> : <span className="muted">Summarizing…</span>}
            {summary?.source === 'template' && <span className="muted"> (Template: AI summaries need an API key.)</span>}</p>
        </div>

        {err && <p className="err">Could not load results: {err}</p>}
        <ul className="res-list" id="list">
          {data && !list.length && <li className="empty">Nothing matches. Remove a filter to see more.</li>}
          {!data && !err && <li className="loading">Loading NASA sources…</li>}
          {list.map(r => (
            <Row key={r.id} r={r} invName={invName(r.investigation)} isOpen={open.has(r.id)} detail={details[r.id]} picked={basket.has(r.id)} flash={flash === r.id}
              onOpen={() => toggleOpen(r.id)} onPick={() => { const b = new Set(basket); if (b.has(r.id)) b.delete(r.id); else b.add(r.id); setBasket(b); }}
              onSimulate={onSimulate} />
          ))}
        </ul>
      </div>
      <div className="basket" id="basket" hidden={!basket.size}>
        <div className="in">
          <span id="basketText">{basket.size} item{basket.size === 1 ? '' : 's'} selected</span>
          <button className="btn" id="clearSel" onClick={() => setBasket(new Set())}>Clear</button>
          <button className="btn primary" id="exportBtn" onClick={() => setExporting(true)}>Preview and export</button>
        </div>
      </div>
      {exporting && <ExportDialog ids={[...basket]} onClose={() => setExporting(false)} />}
    </section>
  );
}

/* Text with [resource_id] citations → numbered, clickable citation buttons. Unknown ids were already dropped server-side. */
export function Cited({ text, ids, titles, onCite }: { text: string; ids: string[]; titles: Record<string, string>; onCite: (id: string) => void }) {
  const parts = text.split(/(\[[^\]\s]+\])/g);
  return <>{parts.map((p, i) => {
    const m = /^\[([^\]\s]+)\]$/.exec(p);
    if (m && ids.includes(m[1])) {
      const n = ids.indexOf(m[1]) + 1;
      return <button key={i} className="cite" title={titles[m[1]] ?? m[1]} aria-label={`Source ${n}: ${titles[m[1]] ?? m[1]}`} onClick={() => onCite(m[1])}>{n}</button>;
    }
    return <Fragment key={i}>{p}</Fragment>;
  })}</>;
}

function Meter({ level, unverified }: { level: number; unverified: boolean }) {
  return <span className={'meter' + (unverified ? ' unv' : '')} aria-hidden="true">{[1, 2, 3, 4, 5].map(i => <i key={i} className={i <= level ? 'on' : ''} />)}</span>;
}

function Row({ r, invName, isOpen, detail, picked, flash, onOpen, onPick, onSimulate }: {
  r: Resource; invName: string; isOpen: boolean; detail?: ResourceDetail; picked: boolean; flash: boolean;
  onOpen: () => void; onPick: () => void; onSimulate: (code: string) => void;
}) {
  const c = r.credibility, T = TYPES[r.type] ?? TYPES.data;
  return (
    <li className={'res' + (flash ? ' flash' : '')} id={'res-' + r.id}>
      <div className="ic" title={T.label}><Icon type={r.type} /></div>
      <div>
        {r.url ? <a className="title" href={r.url} target="_blank" rel="noopener noreferrer">{r.title}</a> : <span className="title">{r.title}</span>}
        {r.placeholder && <span className="badge">placeholder</span>}
        <div className="sub">{T.label} · {invName}{r.investigation_detail && r.origin === 'psi' ? ` (${r.investigation_detail})` : ''}{r.year ? ' · ' + r.year : ''} · {r.format} · {r.publisher}</div>
      </div>
      <div className="cred" title={c.score == null ? 'No source link yet' : c.explanation}>
        <Meter level={c.level} unverified={c.score == null} />
        <span>{c.label}{c.score != null && <> <span className="muted num">{c.score}</span></>}</span>
      </div>
      <div className="acts">
        {r.sim_point && <button className="tog" data-sim={r.sim_point} title="Open a test from this source in the simulator" onClick={() => onSimulate(r.sim_point!)}>▶ Try</button>}
        <button className="tog" data-pick={r.id} aria-pressed={picked} aria-label={`Add “${r.title}” to export`} onClick={onPick}>{picked ? 'Added' : 'Add'}</button>
        <button className="tog" data-open={r.id} aria-expanded={isOpen} aria-label={`Details for “${r.title}”`} onClick={onOpen}>{CHEV}</button>
      </div>
      {isOpen && (
        <div className="more" id={'more-' + r.id}>
          <p>{r.description}</p>
          {c.score == null
            ? <div className="factors">Credibility can’t be scored until the source link is added.</div>
            : <div className="factors"><span>Publisher <b>{c.factors!.publisher}</b></span><span>Review <b>{c.factors!.review}</b></span><span>Traceability <b>{c.factors!.trace}</b></span><span>Score = 0.4 × publisher + 0.3 × review + 0.3 × traceability</span></div>}
          {r.doi && <p className="moremsg">Dataset DOI: <a className="link" href={`https://doi.org/${r.doi}`} target="_blank" rel="noopener noreferrer">{r.doi}</a></p>}
          {r.points_count > 0 && !detail && <p className="moremsg">Loading test points…</p>}
          {detail && detail.test_points.length > 0 && <PointTable points={detail.test_points} total={detail.points_total} onSimulate={onSimulate} />}
        </div>
      )}
    </li>
  );
}

function PointTable({ points, total, onSimulate }: { points: TestPoint[]; total: number; onSimulate: (code: string) => void }) {
  return (
    <>
      <div className="tablebox"><table><thead><tr><th>Test</th><th>Sample</th><th className="n">g</th><th className="n">O₂ %</th><th className="n">kPa</th><th className="n">Flow cm/s</th><th>Outcome</th><th className="n">mm/s</th><th>Source</th><th><span className="sr">Simulate</span></th></tr></thead>
        <tbody>{points.map(p => (
          <tr key={p.code}>
            <td className="num">{p.code}{!p.verified && <span className="badge" title={p.unverified_reason ?? undefined}>{p.placeholder ? 'starter · unverified' : 'unverified'}</span>}</td>
            <td>{p.sample_desc}</td>
            <td className="n">{p.gravity_g ?? '—'}</td>
            <td className="n">{p.o2_pct != null ? +p.o2_pct.toFixed(2) : '—'}</td>
            <td className="n">{p.pressure_kpa != null ? +p.pressure_kpa.toFixed(1) : '—'}</td>
            <td className="n">{p.flow_cm_s ?? '—'}</td>
            <td className={p.outcome === 'burned' ? 'oc-b' : p.outcome === 'went_out' ? 'oc-o' : ''} title={p.notes ?? undefined}>{p.outcome_text}{p.notes ? ' ·' : ''}</td>
            <td className="n">{p.spread_mm_s ?? '—'}</td>
            <td title={p.source_quote ?? undefined}>{p.source_page ? <a className="link" href={`/api/source/${p.dataset}/row/${p.source_page.replace('row ', '')}`} target="_blank" rel="noopener noreferrer">{p.source_page}</a> : p.placeholder ? 'placeholder' : '—'}</td>
            <td>{p.simulatable && <button className="btn small" data-sim={p.code} onClick={() => onSimulate(p.code)}>▶ Simulate</button>}</td>
          </tr>
        ))}</tbody></table></div>
      {total > points.length && <p className="moremsg">Showing {points.length} of {total} tests. Add this source to the export to get every row with its source.</p>}
    </>
  );
}

