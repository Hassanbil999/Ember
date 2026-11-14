/* Fire check (/engine/check): pick a fire, a fuel and the cabin air; the answer comes from NASA's own microgravity
   tests. Tested → the real tests answer; estimated → the validated model; untested → no number, and the nearest
   tested conditions one click away. Sliders show the range NASA tested for the chosen fuel as a lit band. Drops take
   CO₂ and helium shares as NASA mixed them (nitrogen is the rest). Inputs live in the URL, so a check is a link. */
import { useEffect, useMemo, useState } from 'react';
import { api, type FireCheckReq, type FireCheckRes } from '../api';
import { Gauge } from '../components/Gauge';
import { OxygenLine } from '../components/OxygenLine';
import { EXAMPLE, useSiteData } from '../siteData';

const ZONE: Record<string, string> = { tested: 'Tested', estimated: 'Estimated', untested: 'Untested' };
const GRAVITY: [string, string][] = [['0', 'Microgravity'], ['0.166', 'Moon'], ['0.38', 'Mars'], ['1', 'Earth']];
const AIR: [string, number, number][] = [['ISS air', 21, 14.7], ['Moon-base air', 34, 8.2]];
const DEFAULT_FUEL = { gas: 'propane', droplet: 'n-heptane' } as const;
const SCALE = { o2: [10, 45, 0.5], psi: [4, 45, 0.1], flow: [0.1, 3.5, 0.05], d0: [0.5, 5, 0.05], co2: [0, 80, 1], he: [0, 50, 1] } as const;
type Num = keyof typeof SCALE;

interface Form { problem: 'gas' | 'droplet'; fuel: string; o2: number; psi: number; flow: number; d0: number; co2: number; he: number; g: string }

function readForm(): Form {
  const q = new URLSearchParams(location.search);
  const num = (k: string, d: number) => { const v = q.get(k); return v != null && v !== '' && isFinite(+v) ? +v : d; };
  const problem = q.get('problem') === 'droplet' ? 'droplet' : 'gas';
  const blank = !q.has('fuel') && !q.has('problem');          // no inputs: open on the landing page's worked example
  return {
    problem, fuel: q.get('fuel') || (blank ? EXAMPLE.fuel : DEFAULT_FUEL[problem]),
    o2: num('o2', EXAMPLE.o2_pct), psi: num('psi', EXAMPLE.psi), flow: num('flow', blank ? EXAMPLE.fuel_flow : 1), d0: num('d0', 3),
    co2: num('co2', 0), he: num('he', 0),
    g: GRAVITY.some(([v]) => v === q.get('g')) ? q.get('g')! : '0',
  };
}

function writeForm(f: Form) {
  if (!location.pathname.startsWith('/engine/check')) return;
  const q = new URLSearchParams({ problem: f.problem, fuel: f.fuel, o2: String(f.o2), psi: String(f.psi) });
  if (f.problem === 'gas') q.set('flow', String(f.flow));
  else { q.set('d0', String(f.d0)); if (f.co2) q.set('co2', String(f.co2)); if (f.he) q.set('he', String(f.he)); }
  q.set('g', f.g);
  const url = '/engine/check?' + q.toString();
  if (location.pathname + location.search !== url) { try { history.replaceState(null, '', url); } catch { /* sandboxed */ } }
}

const toReq = (f: Form): FireCheckReq => ({ problem: f.problem, fuel: f.fuel, o2_pct: f.o2, psi: f.psi, gravity_g: +f.g, fuel_flow: f.flow, d0_mm: f.d0,
  co2_pct: f.problem === 'droplet' ? f.co2 : 0, he_pct: f.problem === 'droplet' ? f.he : 0 });
const nice = (v: number) => String(Math.abs(v) >= 10 ? +v.toFixed(1) : +v.toFixed(2));

export function FireCheckPage({ onOpenTest }: { onOpenTest: (code: string, resourceId: string | null) => void }) {
  const { data } = useSiteData();
  const meta = data?.meta;
  const [f, setF] = useState<Form>(readForm);
  const [res, setRes] = useState<FireCheckRes | null>(null);
  const [err, setErr] = useState('');
  const [msg, setMsg] = useState('');
  const req = useMemo(() => toReq(f), [f]);
  const over = f.problem === 'droplet' && f.o2 + f.co2 + f.he > 100;          // NASA's mixes: oxygen + CO₂ + helium ≤ 100 %
  const key = over ? '' : JSON.stringify(req);

  useEffect(() => { writeForm(f); }, [f]);
  useEffect(() => {
    if (over) { setRes(null); setErr('Oxygen, CO₂ and helium add up to more than 100 %.'); return; }
    let stale = false;
    const t = setTimeout(() => {
      api.fireCheck(req).then(r => { if (!stale) { setRes(r); setErr(''); } })
        .catch(e => { if (!stale) { setRes(null); setErr(String(e.message || e)); } });
    }, 150);
    return () => { stale = true; clearTimeout(t); };
  }, [key]); // eslint-disable-line react-hooks/exhaustive-deps

  const set = (p: Partial<Form>) => { setMsg(''); setF(x => ({ ...x, ...p })); };
  const m = meta?.[f.problem];
  const band = (k: string) => m?.ranges_by_fuel[f.fuel]?.[k];
  const useSuggestion = () => {
    const s = res?.suggestion; if (!s) return;
    set({ fuel: s.fuel, o2: s.o2_pct, psi: s.psi, ...(s.fuel_flow != null ? { flow: s.fuel_flow } : {}), ...(s.d0_mm != null ? { d0: s.d0_mm } : {}),
          ...(s.co2_pct != null ? { co2: s.co2_pct } : {}), ...(s.he_pct != null ? { he: s.he_pct } : {}) });
  };

  async function download() {
    setMsg('Preparing…');
    try {
      const file = await api.fireCheckReport(req);
      const url = URL.createObjectURL(new Blob([file.text], { type: 'text/html' }));
      const a = document.createElement('a'); a.href = url; a.download = file.filename;
      document.body.appendChild(a); a.click(); a.remove();
      setTimeout(() => URL.revokeObjectURL(url), 2000);
      setMsg('Saved. Open it and print to PDF.');
    } catch (e) { setMsg('Report failed: ' + (e as Error).message); }
  }

  const slider = (id: string, label: string, k: Num, unit: string, rk: string) => {
    const [lo, hi, step] = SCALE[k], r = band(rk), pos = (v: number) => `${((Math.min(hi, Math.max(lo, v)) - lo) / (hi - lo)) * 100}%`;
    return (
      <div className="fc-slider">
        <div className="row"><label htmlFor={id}>{label}</label><output htmlFor={id}>{nice(f[k])} <small>{unit}</small></output></div>
        <input id={id} type="range" className="rng" min={lo} max={hi} step={step} value={f[k]}
          style={{ ['--a' as string]: r ? pos(r[0]) : '0%', ['--b' as string]: r ? pos(r[1]) : '0%' }}
          aria-valuetext={`${nice(f[k])} ${unit}${r ? `, NASA tested ${nice(r[0])} to ${nice(r[1])}` : ''}`}
          onChange={e => set({ [k]: +e.target.value } as Partial<Form>)} />
      </div>
    );
  };

  return (
    <section id="view-check" className="view page" aria-labelledby="checkTitle">
      <div className="wrap">
        <h2 id="checkTitle" className="page-title">Fire check</h2>
        <div className="check-grid" id="fireCheck">
          <div className="card inputs" aria-label="Conditions">
            <div className="kind" role="group" aria-label="Fire type">
              <button id="fcGas" aria-pressed={f.problem === 'gas'} onClick={() => set({ problem: 'gas', fuel: DEFAULT_FUEL.gas })}>
                <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 3c1 3 5 5.5 5 10a5 5 0 0 1-10 0c0-2.5 1.5-4 2.5-5 .3 1.8 1.2 2.6 2 3 .3-3-1-5.5.5-8z" /></svg>Gas leak</button>
              <button id="fcDrop" aria-pressed={f.problem === 'droplet'} onClick={() => set({ problem: 'droplet', fuel: DEFAULT_FUEL.droplet })}>
                <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 3s6 6.5 6 11a6 6 0 0 1-12 0c0-4.5 6-11 6-11z" /></svg>Fuel drop</button>
            </div>
            <div className="chips" id="fcFuel" role="group" aria-label="Fuel">
              {(m?.fuels ?? [f.fuel]).map(x => <button key={x} className="chip" aria-pressed={f.fuel === x} onClick={() => set({ fuel: x })}>{x}</button>)}
            </div>
            <div className="chips air" role="group" aria-label="Cabin air">
              {AIR.map(([label, o2, psi]) => <button key={label} className="chip" aria-pressed={f.o2 === o2 && f.psi === psi && !f.co2 && !f.he}
                onClick={() => set({ o2, psi, co2: 0, he: 0 })}>{label}</button>)}
            </div>
            {slider('fcO2', 'Oxygen', 'o2', '%', 'o2_pct')}
            {slider('fcP', 'Pressure', 'psi', 'psi', 'psi')}
            {f.problem === 'gas' ? slider('fcFlow', 'Leak size', 'flow', 'mg/s', 'fuel_flow') : <>
              {slider('fcD0', 'Drop size', 'd0', 'mm', 'd0_mm')}
              {slider('fcCo2', 'CO₂ in the air', 'co2', '%', 'co2_pct')}
              {slider('fcHe', 'Helium in the air', 'he', '%', 'he_pct')}
            </>}
            <div className="chips" role="group" aria-label="Gravity">
              {GRAVITY.map(([v, label]) => <button key={v} className="chip" id={'fcG' + label} aria-pressed={f.g === v} onClick={() => set({ g: v })}>{label}</button>)}
            </div>
            <p className="key"><i /> range NASA tested for {f.fuel}{f.problem === 'droplet' ? ' · the rest of the air is nitrogen' : ''}</p>
          </div>

          <div className={'card result zone-' + (res?.zone ?? 'none')} aria-live="polite">
            {err && <p className="err" id="fcErr" role="alert">{err}</p>}
            {!res && !err && <p className="loading">Checking…</p>}
            {res && <Result res={res} entered={f.o2} onOpenTest={onOpenTest} onSuggest={useSuggestion} />}
            <div className="fc-foot">
              <button className="btn primary" id="fcReport" disabled={!res} onClick={download}>Download report</button>
              <span id="fcMsg">{msg}</span>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}

function Result({ res, entered, onOpenTest, onSuggest }: { res: FireCheckRes; entered: number; onOpenTest: (code: string, resourceId: string | null) => void; onSuggest: () => void }) {
  const [all, setAll] = useState(false);
  const t = res.tested, e = res.estimate;
  const yes = res.problem === 'gas' ? 'stayed lit' : 'burned to the end', no = res.problem === 'gas' ? 'went out on its own' : 'flame died with fuel left';
  const line = res.zone === 'untested' ? (res.reasons[0] ?? 'Outside what NASA tested.')
    : t ? (t.n === 1 ? `The NASA test at nearly these conditions ${t.yes ? t.outcome_yes : t.outcome_no}.` : `${t.yes} of ${t.n} NASA tests here ${t.outcome_yes}.`)
    : 'Estimated from the NASA tests around these conditions.';
  const top = res.drivers[0];
  return (
    <div className="fc-res">
      <span className={'zone-pill ' + res.zone} id="fcZone">{ZONE[res.zone]}</span>
      <div className="fc-main">
        <Gauge id={e ? 'fcProb' : undefined} p={e ? e.probability : null} low={e?.low} high={e?.high} label={e ? `chance it ${e.will}` : 'no estimate'} />
        <div className="fc-say">
          <p id="fcVerdict">{line}</p>
          {e && <p className="range">Range {Math.round(e.low * 100)}–{Math.round(e.high * 100)}%</p>}
          {top && <p className="lever">Biggest lever: <b>{top.label.toLowerCase()}</b> ({top.change_pts > 0 ? '+' : ''}{top.change_pts} pts per +{top.step} {top.unit})</p>}
          {res.suggestion && <button className="btn ember small" id="fcSuggest" onClick={onSuggest}>Try the nearest NASA test ({res.suggestion.code})</button>}
        </div>
      </div>
      {res.quantities.length > 0 && (
        <div className="qty">
          {res.quantities.map(q => <div key={q.label} title={q.meaning}><b>{nice(q.value)}</b><span>{q.label} ({q.unit}) · {nice(q.low)}–{nice(q.high)}</span></div>)}
        </div>
      )}
      {res.oxygen_line && (<>
        <h3 className="sub-h">Where is the line?</h3>
        <OxygenLine data={res.oxygen_line} entered={entered} yes={e?.outcome_yes ?? yes} no={e?.outcome_no ?? no} />
      </>)}
      {res.next_tests.length > 0 && (<>
        <h3 className="sub-h">Which test next?</h3>
        <ol className="next" id="fcNext">{res.next_tests.map((n, i) => (
          <li key={i} data-next={i}>
            <span>{Object.keys(n.inputs).map(k => `${n.labels[k]} ${nice(n.inputs[k])}${n.units[k] ? ' ' + n.units[k] : ''}`).join(' · ')}</span>
            <em>models disagree: {Math.round(n.committee_low * 100)}–{Math.round(n.committee_high * 100)}%</em>
          </li>))}</ol>
      </>)}
      <h3 className="sub-h">Closest NASA tests</h3>
      <div className="tablebox"><table id="fcNear"><thead><tr><th>Test</th><th className="n">O₂ %</th><th className="n">psi</th>
        <th className="n">{res.problem === 'gas' ? 'mg/s' : 'mm'}</th><th>Result</th><th><span className="sr">Open</span></th></tr></thead>
        <tbody>{res.nearest.slice(0, all ? undefined : 3).map(r => (
          <tr key={r.code} data-code={r.code}>
            <td className="num">{r.code}</td><td className="n">{r.o2_pct}</td><td className="n">{r.psi}</td><td className="n">{r.fuel_flow ?? r.d0_mm}</td>
            <td><span className={'out ' + (r.burned ? 'b' : 'o')}>{r.outcome}</span></td>
            <td><button className="btn small" data-open-test={r.code} onClick={() => onOpenTest(r.code, r.resource_id)}>Open in table</button></td>
          </tr>))}</tbody></table></div>
      {res.nearest.length > 3 && <button className="link" onClick={() => setAll(x => !x)}>{all ? 'Show fewer' : `Show all ${res.nearest.length}`}</button>}
    </div>
  );
}
