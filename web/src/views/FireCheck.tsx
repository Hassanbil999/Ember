/* Fire check page (/engine/check): an engineer enters fuel and conditions; the server answers from NASA's own
   outcome-labelled tests. Tested → the real tests answer; estimated → the validated model; untested → no number.
   The inputs live in the URL, so a check can be shared as a link. */
import { useEffect, useMemo, useState } from 'react';
import { api, type FireCheckReq, type FireCheckRes } from '../api';
import { EXAMPLE, useSiteData } from '../siteData';

const pct = (p: number) => `${Math.round(p * 100)} %`;
/* Tested ranges as the domain check sees them: enough decimals that a value shown inside is inside. */
const rng = (v: number) => String(Math.abs(v) >= 10 ? +v.toFixed(1) : +v.toFixed(2));
const ZONE: Record<string, string> = { tested: 'Tested', estimated: 'Estimated', untested: 'Untested' };
const GRAVITY: [string, string][] = [['0', 'Microgravity'], ['0.166', 'Moon'], ['0.38', 'Mars'], ['1', 'Earth']];
const DEFAULT_FUEL = { gas: 'propane', droplet: 'n-heptane' } as const;

interface Form { problem: 'gas' | 'droplet'; fuel: string; o2: string; psi: string; flow: string; d0: string; dil: 'N2' | 'CO2' | 'He'; g: string }

function readForm(): Form {
  const q = new URLSearchParams(location.search);
  const problem = q.get('problem') === 'droplet' ? 'droplet' : 'gas';
  const dil = q.get('dil');
  // With no inputs in the link, open on the landing page's worked example (Moon-base air, a small diluted ethane leak).
  const blank = !q.has('fuel') && !q.has('problem');
  return {
    problem, fuel: q.get('fuel') || (blank ? EXAMPLE.fuel : DEFAULT_FUEL[problem]),
    o2: q.get('o2') ?? String(EXAMPLE.o2_pct), psi: q.get('psi') ?? String(EXAMPLE.psi),
    flow: q.get('flow') ?? (blank ? String(EXAMPLE.fuel_flow) : '1'), d0: q.get('d0') ?? '3',
    dil: dil === 'CO2' || dil === 'He' ? dil : 'N2', g: GRAVITY.some(([v]) => v === q.get('g')) ? q.get('g')! : '0',
  };
}

function writeForm(f: Form) {
  if (!location.pathname.startsWith('/engine/check')) return;
  const q = new URLSearchParams({ problem: f.problem, fuel: f.fuel, o2: f.o2, psi: f.psi });
  if (f.problem === 'gas') q.set('flow', f.flow); else { q.set('d0', f.d0); q.set('dil', f.dil); }
  q.set('g', f.g);
  const url = '/engine/check?' + q.toString();
  if (location.pathname + location.search !== url) { try { history.replaceState(null, '', url); } catch { /* sandboxed */ } }
}

/* The request, or the names of the fields that still need a number. */
function toRequest(f: Form): { req: FireCheckReq | null; missing: string[] } {
  const n = (s: string) => (s.trim() === '' || !isFinite(+s) ? null : +s);
  const fields: [string, number | null][] = [['Oxygen', n(f.o2)], ['Pressure', n(f.psi)], f.problem === 'gas' ? ['Fuel flow', n(f.flow)] : ['Drop size', n(f.d0)]];
  const missing = fields.filter(([, v]) => v == null).map(([k]) => k);
  if (missing.length) return { req: null, missing };
  return {
    req: { problem: f.problem, fuel: f.fuel, o2_pct: n(f.o2)!, psi: n(f.psi)!, gravity_g: +f.g, diluent: f.dil,
           fuel_flow: f.problem === 'gas' ? n(f.flow)! : 1, d0_mm: f.problem === 'droplet' ? n(f.d0)! : 3 },
    missing,
  };
}

export function FireCheckPage({ onOpenTest }: { onOpenTest: (code: string, resourceId: string | null) => void }) {
  const { data, err: metaErr } = useSiteData();
  const meta = data?.meta;
  const [f, setF] = useState<Form>(readForm);
  const [res, setRes] = useState<FireCheckRes | null>(null);
  const [err, setErr] = useState('');
  const [msg, setMsg] = useState('');
  const { req, missing } = useMemo(() => toRequest(f), [f]);
  const key = JSON.stringify(req);

  useEffect(() => { writeForm(f); }, [f]);
  useEffect(() => {
    if (!req) { setRes(null); setErr(`Enter a value for ${missing.join(' and ')}.`); return; }
    let stale = false;
    const t = setTimeout(() => {
      api.fireCheck(req).then(r => { if (!stale) { setRes(r); setErr(''); } })
        .catch(e => { if (!stale) { setRes(null); setErr(String(e.message || e)); } });
    }, 200);
    return () => { stale = true; clearTimeout(t); };
  }, [key]); // eslint-disable-line react-hooks/exhaustive-deps

  const set = (p: Partial<Form>) => { setMsg(''); setF(x => ({ ...x, ...p })); };
  const m = meta?.[f.problem];
  const fuelRange = (k: string) => m?.ranges_by_fuel[f.fuel]?.[k];
  const hint = (k: string) => { const r = fuelRange(k); return r ? `NASA tested ${rng(r[0])}–${rng(r[1])} for ${f.fuel}` : ''; };
  const pick = (problem: 'gas' | 'droplet') => set({ problem, fuel: DEFAULT_FUEL[problem] });

  async function download() {
    if (!req) return;
    setMsg('Preparing…');
    try {
      const file = await api.fireCheckReport(req);
      const url = URL.createObjectURL(new Blob([file.text], { type: 'text/html' }));
      const a = document.createElement('a'); a.href = url; a.download = file.filename;
      document.body.appendChild(a); a.click(); a.remove();
      setTimeout(() => URL.revokeObjectURL(url), 2000);
      setMsg(`Saved ${file.filename}. Open it and choose Print to save a PDF.`);
    } catch (e) { setMsg('Report failed: ' + (e as Error).message); }
  }

  const num = (id: string, label: string, k: 'o2' | 'psi' | 'flow' | 'd0', unit: string, range: string, step: number) => (
    <div className="ctl fc-in">
      <div className="row"><label htmlFor={id}>{label}</label></div>
      <div className="fc-num"><input id={id} type="number" inputMode="decimal" step={step} value={f[k]} aria-invalid={f[k].trim() === '' || undefined}
        aria-describedby={id + 'H'} onChange={e => set({ [k]: e.target.value } as Partial<Form>)} /><span className="muted">{unit}</span></div>
      <span className="hint" id={id + 'H'}>{hint(range)}</span>
    </div>
  );

  return (
    <section id="view-check" className="view page" aria-labelledby="checkTitle">
      <div className="wrap">
        <div className="pagehead">
          <h2 id="checkTitle">Fire check</h2>
          <p className="muted">Will a small fire keep burning? Answered from NASA's microgravity tests that recorded the outcome. Near a test, the test answers. Between tests, a validated model estimates. Outside them, no number.</p>
        </div>
        <div className="check-grid" id="fireCheck">
          <aside className="card inputs" aria-label="Conditions">
            <span className="sec">Conditions</span>
            <div className="seg" role="group" aria-label="Fire type">
              <button id="fcGas" aria-pressed={f.problem === 'gas'} onClick={() => pick('gas')}>Gas leak flame<small>CFI-G · {meta?.gas.psi_id ?? 'PSI-159'}</small></button>
              <button id="fcDrop" aria-pressed={f.problem === 'droplet'} onClick={() => pick('droplet')}>Liquid fuel drop<small>FLEX · {meta?.droplet.psi_id ?? 'PSI-69'}</small></button>
            </div>
            <div className="ctl fc-in">
              <div className="row"><label htmlFor="fcFuel">Fuel</label></div>
              <select id="fcFuel" className="sel" value={f.fuel} onChange={e => set({ fuel: e.target.value })}>
                {(m?.fuels ?? [f.fuel]).map(x => <option key={x} value={x}>{x}</option>)}
              </select>
            </div>
            {num('fcO2', 'Oxygen', 'o2', '%', 'o2_pct', 0.5)}
            {num('fcP', 'Pressure', 'psi', 'psi', 'psi', 0.1)}
            {f.problem === 'gas'
              ? num('fcFlow', 'Fuel flow (leak size)', 'flow', 'mg/s', 'fuel_flow', 0.05)
              : num('fcD0', 'Drop size', 'd0', 'mm', 'd0_mm', 0.1)}
            {f.problem === 'droplet' && (
              <div className="ctl fc-in">
                <div className="row"><label htmlFor="fcDil">Rest of the air</label></div>
                <select id="fcDil" className="sel" value={f.dil} onChange={e => set({ dil: e.target.value as Form['dil'] })}>
                  <option value="N2">Nitrogen</option><option value="CO2">Carbon dioxide</option><option value="He">Helium</option>
                </select>
              </div>
            )}
            <div className="ctl">
              <div className="row"><span id="fcGLabel">Gravity</span></div>
              <div className="chips" role="group" aria-labelledby="fcGLabel">
                {GRAVITY.map(([v, label]) => <button key={v} className="chip" id={'fcG' + label} aria-pressed={f.g === v} onClick={() => set({ g: v })}>{label}</button>)}
              </div>
              <span className="hint">Every NASA test here ran in microgravity. Other gravity gives no number.</span>
            </div>
            {metaErr && <p className="err">Could not load the tested ranges ({metaErr}).</p>}
          </aside>

          <div className="card results" aria-live="polite">
            {err && <p className="err" id="fcErr" role="alert">{err}</p>}
            {!res && !err && <p className="loading">Checking…</p>}
            {res && <Result res={res} onOpenTest={onOpenTest} />}
            <div className="fc-foot">
              <span className="muted" style={{ fontSize: 12.5 }} id="fcMsg">{msg}</span>
              <button className="btn primary" id="fcReport" disabled={!res} onClick={download}>Download report</button>
            </div>
          </div>
        </div>
        <Limits />
      </div>
    </section>
  );
}

function Result({ res, onOpenTest }: { res: FireCheckRes; onOpenTest: (code: string, resourceId: string | null) => void }) {
  const ref = res.reference;
  return (
    <div className="fc-res" data-zone={res.zone}>
      <div className="verdict">
        <span className={'pill zone-' + res.zone} id="fcZone">{ZONE[res.zone]}</span>
        <p id="fcVerdict">{res.verdict}</p>
        {res.reasons.length > 0 && <ul className="fc-reasons">{res.reasons.map(r => <li key={r}>{r}</li>)}</ul>}
      </div>
      {(res.estimate || res.quantities.length > 0) && (
        <div className="stats">
          {res.estimate && <div><b id="fcProb">{pct(res.estimate.probability)}</b><span>chance it {res.estimate.will}</span><span>range {pct(res.estimate.low)}–{pct(res.estimate.high)} <span className="tag est">model estimate</span></span></div>}
          {res.quantities.map(q => <div key={q.label} title={q.meaning}><b>{q.value.toFixed(2)}</b><span>{q.label}, {q.unit}</span><span>90 % range {q.low.toFixed(2)}–{q.high.toFixed(2)} <span className="tag est">model estimate</span></span></div>)}
        </div>
      )}
      {res.drivers.length > 0 && (
        <p className="muted fc-small">Moves it most: {res.drivers.slice(0, 3).map(d => `${d.label.toLowerCase()} +${d.step} ${d.unit} → ${d.change_pts > 0 ? '+' : ''}${d.change_pts} pts`).join(' · ')}</p>
      )}
      {ref && (
        <p className="fc-small muted" id="fcRef"><span className="tag pub">published value · not a NASA test</span>{' '}
          {ref.values ? <>Earth limiting oxygen for {ref.fuel}: {ref.values.N2} % O₂ with nitrogen, {ref.values.CO2} % with CO₂.</> : ref.missing}{' '}
          <a className="link" href={ref.source.url} target="_blank" rel="noreferrer">{ref.source.label.split(',')[0]}</a></p>
      )}
      <span className="sec">Nearest NASA tests, same fuel <span className="tag nasa">NASA test</span></span>
      <div className="tablebox"><table id="fcNear"><thead><tr><th>Test</th><th>Fuel</th><th className="n">O₂ %</th><th className="n">psi</th>
        <th className="n">{res.problem === 'gas' ? 'Flow mg/s' : 'Drop mm'}</th><th>Measured</th><th className="n">Distance</th><th><span className="sr">Open</span></th></tr></thead>
        <tbody>{res.nearest.map(r => (
          <tr key={r.code} data-code={r.code}>
            <td className="num">{r.code}{r.close && <span className="badge">close</span>}</td><td>{r.fuel}</td>
            <td className="n">{r.o2_pct}</td><td className="n">{r.psi}</td><td className="n">{r.fuel_flow ?? r.d0_mm}</td>
            <td className={r.burned ? 'oc-b' : 'oc-o'}>{r.outcome}</td><td className="n">{r.distance.toFixed(2)}</td>
            <td><button className="btn small" data-open-test={r.code} onClick={() => onOpenTest(r.code, r.resource_id)}>Open in table</button></td>
          </tr>))}</tbody></table></div>
      <p className="muted fc-small" id="fcModel">
        {res.model.chosen
          ? <>Model: {res.model.chosen}, trained on {res.model.n_tests} {res.model.investigation} tests ({res.model.psi_id}). On {res.model.n_campaigns} NASA campaigns it never saw: AUC {res.model.auc?.toFixed(2)} (chance 0.50), Brier {res.model.brier?.toFixed(3)} vs {res.model.baseline_brier.toFixed(3)} for always guessing the average.</>
          : <>No model beat the always-the-average baseline on unseen campaigns, so only real tests are shown.</>}
      </p>
    </div>
  );
}

export function Limits() {
  return (
    <details className="card limits" open>
      <summary><span className="sec">Limits</span></summary>
      <ul>
        <li>Microgravity only: no NASA test here burned anything at Moon, Mars or Earth gravity, so those give no number.</li>
        <li>Gas jets and liquid drops only. Solid materials are not covered: their NASA tables record no burned/went-out outcome.</li>
        <li>Test fuels stand in for cabin fluids: heptane for kerosene-type liquids, methanol for alcohols, ethane/propane/butane for gas leaks.</li>
        <li>"Kept burning" in the gas-jet tests means still burning when the run ended, at a time the researchers chose.</li>
        <li>Few tests sit near Moon-base air (34 % O₂, 8.2 psi), so many checks there are untested. A screening tool, not a certification.</li>
      </ul>
    </details>
  );
}
