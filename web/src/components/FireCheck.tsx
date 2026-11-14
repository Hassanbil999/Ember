/* Fire check dialog: an engineer enters fuel and conditions; the server answers from NASA's own
   outcome-labelled tests. Tested → the real tests answer; estimated → the validated model; untested → no number.
   One dialog, opened from the Simulate controls, in the same pattern as the Export dialog.

   Number fields keep the text as typed. A request is sent only when every field holds a valid number;
   while one does not, the field says why and the last result is marked out of date instead of changing.
   Only the newest request may update the result, so a slow earlier answer never overwrites a newer one. */
import { useEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { api, type FireCheckMeta, type FireCheckReq, type FireCheckRes } from '../api';
import { OxygenLine } from './OxygenLine';

const pct = (p: number) => `${Math.round(p * 100)} %`;
const r2 = (v: number) => (Math.abs(v) >= 10 ? Math.round(v) : Math.abs(v) >= 1 ? +v.toFixed(1) : +v.toFixed(2));
const ZONE: Record<string, string> = { tested: 'Tested', estimated: 'Estimated', untested: 'Untested' };

type Field = 'o2_pct' | 'psi' | 'fuel_flow' | 'd0_mm' | 'co2_pct' | 'he_pct';
const LIMITS: Record<Field, { min: number; max: number; minOpen?: boolean; label: string }> = {
  o2_pct: { min: 0, max: 100, label: 'Oxygen' },
  psi: { min: 0, max: 100, minOpen: true, label: 'Pressure' },
  fuel_flow: { min: 0, max: 100, label: 'Fuel flow' },
  d0_mm: { min: 0, max: 20, minOpen: true, label: 'Drop size' },
  co2_pct: { min: 0, max: 100, label: 'CO₂' },
  he_pct: { min: 0, max: 100, label: 'Helium' },
};

function problemOf(v: string, k: Field): string | null {
  if (v.trim() === '') return 'Enter a number.';
  const n = Number(v);
  if (!Number.isFinite(n)) return 'Enter a number.';
  const L = LIMITS[k];
  if (L.minOpen ? n <= L.min : n < L.min) return `${L.label} must be above ${L.min}.`;
  if (n > L.max) return `${L.label} must be at most ${L.max}.`;
  return null;
}

interface Props { o2: number; psi: number; g: number; onClose: () => void; onOpenTest: (code: string, resourceId: string | null) => void }

export function FireCheck({ o2, psi, g, onClose, onOpenTest }: Props) {
  const dlg = useRef<HTMLDialogElement>(null);
  const [meta, setMeta] = useState<FireCheckMeta | null>(null);
  const [problem, setProblem] = useState<'gas' | 'droplet'>('gas');
  const [fuel, setFuel] = useState('propane');
  const [txt, setTxt] = useState<Record<Field, string>>({
    o2_pct: String(+o2.toFixed(1)), psi: String(+psi.toFixed(2)), fuel_flow: '1', d0_mm: '3', co2_pct: '0', he_pct: '0',
  });
  const [res, setRes] = useState<FireCheckRes | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState('');
  const [msg, setMsg] = useState('');
  const seq = useRef(0);

  const closeRef = useRef(onClose);
  closeRef.current = onClose;
  useEffect(() => {
    const d = dlg.current!;
    if (!d.open) { if (d.showModal) d.showModal(); else d.setAttribute('open', ''); }
    const onCancel = (e: Event) => { e.preventDefault(); closeRef.current(); };
    d.addEventListener('cancel', onCancel);
    api.fireCheckMeta().then(setMeta).catch(e => setErr(String((e as Error).message || e)));
    return () => d.removeEventListener('cancel', onCancel);
  }, []);

  const fields: Field[] = problem === 'gas' ? ['o2_pct', 'psi', 'fuel_flow'] : ['o2_pct', 'psi', 'd0_mm', 'co2_pct', 'he_pct'];
  const problems: Partial<Record<Field, string>> = {};
  for (const k of fields) { const p = problemOf(txt[k], k); if (p) problems[k] = p; }
  if (problem === 'droplet' && !problems.o2_pct && !problems.co2_pct && !problems.he_pct
      && Number(txt.o2_pct) + Number(txt.co2_pct) + Number(txt.he_pct) > 100) problems.co2_pct = 'Oxygen, CO₂ and helium add up to more than 100 %.';
  const valid = Object.keys(problems).length === 0;
  const req: FireCheckReq = {
    problem, fuel, gravity_g: g, o2_pct: Number(txt.o2_pct), psi: Number(txt.psi),
    fuel_flow: Number(txt.fuel_flow), d0_mm: Number(txt.d0_mm), co2_pct: Number(txt.co2_pct), he_pct: Number(txt.he_pct),
  };
  const key = valid ? JSON.stringify(req) : '';
  const current = !!res && valid && res.problem === problem && !busy;

  useEffect(() => {
    if (!valid) return;
    const id = ++seq.current;
    setBusy(true);
    const t = setTimeout(() => {
      api.fireCheck(req)
        .then(r => { if (id === seq.current) { setRes(r); setErr(''); } })
        .catch(e => { if (id === seq.current) setErr(String((e as Error).message || e)); })
        .finally(() => { if (id === seq.current) setBusy(false); });
    }, 250);
    return () => clearTimeout(t);
  }, [key]); // eslint-disable-line react-hooks/exhaustive-deps

  const m = meta?.[problem];
  const fr = m?.ranges_by_fuel?.[fuel] ?? m?.ranges;
  const hint = (k: string) => fr?.[k] ? `tested for ${fuel}: ${r2(fr[k][0])}–${r2(fr[k][1])}` : '';
  const pick = (p: 'gas' | 'droplet') => { if (p === problem) return; setProblem(p); setFuel(p === 'gas' ? 'propane' : 'n-heptane'); setRes(null); };
  const setField = (k: Field, v: string) => setTxt(t => ({ ...t, [k]: v }));
  function useSuggestion() {
    const s = res?.suggestion; if (!s) return;
    setFuel(s.fuel);
    setTxt(t => ({ ...t, o2_pct: String(s.o2_pct), psi: String(s.psi),
      ...(s.fuel_flow != null ? { fuel_flow: String(s.fuel_flow) } : {}), ...(s.d0_mm != null ? { d0_mm: String(s.d0_mm) } : {}),
      ...(s.co2_pct != null ? { co2_pct: String(s.co2_pct) } : {}), ...(s.he_pct != null ? { he_pct: String(s.he_pct) } : {}) }));
  }

  async function download() {
    if (!current) return;
    setMsg('Preparing…');
    try {
      const f = await api.fireCheckReport(req);
      const url = URL.createObjectURL(new Blob([f.text], { type: 'text/html' }));
      const a = document.createElement('a'); a.href = url; a.download = f.filename;
      document.body.appendChild(a); a.click(); a.remove();
      setTimeout(() => URL.revokeObjectURL(url), 2000);
      setMsg(`Saved ${f.filename} to your Downloads folder. Open it and choose Print to save a PDF.`);
    } catch (e) { setMsg('Report failed: ' + (e as Error).message); }
  }

  const num = (id: string, k: Field, label: string, unit: string, h: string, step = 0.1) => (
    <div className="ctl fc-in">
      <div className="row"><label htmlFor={id}>{label}</label><span className="scale">{h}</span></div>
      <div className="fc-num"><input id={id} type="number" inputMode="decimal" step={step} value={txt[k]} aria-invalid={!!problems[k]}
        aria-describedby={problems[k] ? id + 'Err' : undefined} onChange={e => setField(k, e.target.value)} /><span className="muted">{unit}</span></div>
      {problems[k] && <span className="fc-err" id={id + 'Err'} role="alert">{problems[k]}</span>}
    </div>
  );

  return createPortal(
    <dialog id="fireDlg" ref={dlg} aria-labelledby="fcTitle" className="fc">
      <div className="dlg">
        <div className="phead"><h2 id="fcTitle" style={{ fontFamily: 'var(--font-display)', fontSize: 22, fontWeight: 600, color: 'var(--ink)', letterSpacing: '.04em' }}>Check against NASA tests</h2></div>
        <p className="muted" style={{ margin: 0, fontSize: 13 }}>Learned from NASA's microgravity tests with a measured outcome. Near a test, the test answers. Between tests, a validated model estimates. Outside them, no number.</p>
        <div className="seg" role="group" aria-label="Fire type">
          <button id="fcGas" aria-pressed={problem === 'gas'} onClick={() => pick('gas')}>Gas leak flame · CFI-G</button>
          <button id="fcDrop" aria-pressed={problem === 'droplet'} onClick={() => pick('droplet')}>Liquid fuel drop · FLEX</button>
        </div>
        <div className="fc-grid">
          <div className="ctl fc-in">
            <div className="row"><label htmlFor="fcFuel">Fuel</label></div>
            <select id="fcFuel" className="sel" value={fuel} onChange={e => setFuel(e.target.value)}>
              {(m?.fuels ?? [fuel]).map(f => <option key={f} value={f}>{f}</option>)}
            </select>
          </div>
          {num('fcO2', 'o2_pct', 'Oxygen', '%', hint('o2_pct'), 0.5)}
          {num('fcP', 'psi', 'Pressure', 'psi', hint('psi'), 0.1)}
          {problem === 'gas'
            ? num('fcFlow', 'fuel_flow', 'Fuel flow (leak size)', 'mg/s', hint('fuel_flow'), 0.05)
            : num('fcD0', 'd0_mm', 'Drop size', 'mm', hint('d0_mm'), 0.1)}
          {problem === 'droplet' && num('fcCo2', 'co2_pct', 'CO₂ in the air', '%', hint('co2_pct'), 5)}
          {problem === 'droplet' && num('fcHe', 'he_pct', 'Helium in the air', '%', hint('he_pct'), 5)}
          <div className="ctl fc-in"><div className="row"><span>Gravity</span></div><span className="num">{g <= 0.02 ? 'microgravity' : `${g.toFixed(3)} g`}<small className="muted"> · from the simulator</small></span></div>
        </div>
        <p className="muted fc-small" id="fcNotIn">{problem === 'droplet' ? 'The rest of the air is nitrogen. ' : ''}{m?.not_in_data ?? ''}</p>

        {err && <p className="err" role="alert">{err}</p>}
        {!valid && res && <p className="fc-stale" id="fcStale">Fix the highlighted field. The result below is for the last valid inputs.</p>}
        {res && (
          <div className={'fc-res' + (current ? '' : ' stale')} aria-live="polite" aria-busy={busy} data-zone={res.zone} data-current={current}>
            <div className="verdict">
              <span className={'pill zone-' + res.zone} id="fcZone">{ZONE[res.zone]}</span>
              <p id="fcVerdict">{res.verdict}</p>
              {res.reasons.length > 0 && <ul className="fc-reasons">{res.reasons.map(r => <li key={r}>{r}</li>)}</ul>}
              {res.suggestion && <p className="fc-small"><button className="link" id="fcSuggest" onClick={useSuggestion}>Use the nearest tested conditions</button>
                <span className="muted"> ({res.suggestion.code}: {res.suggestion.o2_pct} % O₂, {res.suggestion.psi} psi)</span></p>}
            </div>
            {(res.estimate || res.quantities.length > 0) && (
              <div className="stats fc-stats">
                {res.estimate && <div><b id="fcProb">{pct(res.estimate.probability)}</b><span>chance it {res.estimate.will} · likely {pct(res.estimate.low)}–{pct(res.estimate.high)}</span></div>}
                {res.quantities.map(q => <div key={q.label}><b>{r2(q.value)}</b><span>{q.label}, {q.unit} · {r2(q.low)}–{r2(q.high)}</span></div>)}
              </div>
            )}
            {res.drivers.length > 0 && (
              <p className="muted fc-small">Moves it most: {res.drivers.slice(0, 3).map(d => `${d.label.toLowerCase()} +${d.step} ${d.unit} → ${d.change_pts > 0 ? '+' : ''}${d.change_pts} pts`).join(' · ')}</p>
            )}
            {res.oxygen_line && (<>
              <span className="sec">Where is the line? Oxygen, everything else as entered</span>
              <OxygenLine data={res.oxygen_line} entered={req.o2_pct} yes={res.estimate?.outcome_yes ?? (res.problem === 'gas' ? 'stayed lit' : 'burned to the end')}
                no={res.estimate?.outcome_no ?? (res.problem === 'gas' ? 'went out on its own' : 'flame died with fuel left')} />
            </>)}
            {res.next_tests.length > 0 && (<>
              <span className="sec">Tests that would teach the model most</span>
              <p className="muted fc-small">Where the 15 models (each refitted on resampled NASA campaigns) disagree most, inside what the {res.model.investigation} hardware has already done, and near your settings. One test there narrows the answer most.</p>
              <ol className="fc-next" id="fcNext">{res.next_tests.map((n, i) => (
                <li key={i} data-next={i}>
                  <span className="num">{Object.keys(n.inputs).map(k => `${n.labels[k]} ${r2(n.inputs[k])}${n.units[k] ? ' ' + n.units[k] : ''}`).join(' · ')}</span>
                  <span className="muted"> · models: {pct(n.committee_low)}–{pct(n.committee_high)} · nearest test {n.nearest_test} ({n.nearest_burned ? 'kept going' : 'went out'})</span>
                </li>))}</ol>
            </>)}
            <span className="sec">Nearest NASA tests, same fuel</span>
            <div className="tablebox"><table id="fcNear"><thead><tr><th>Test</th><th>Fuel</th><th className="n">O₂ %</th><th className="n">psi</th>
              <th className="n">{res.problem === 'gas' ? 'Flow mg/s' : 'Drop mm'}</th><th>Measured</th><th className="n">Distance</th><th><span className="sr">Open</span></th></tr></thead>
              <tbody>{res.nearest.map(r => (
                <tr key={r.code} data-code={r.code}>
                  <td className="num">{r.code}{r.close && <span className="badge">close</span>}</td><td>{r.fuel}</td>
                  <td className="n">{r.o2_pct}</td><td className="n">{r.psi}</td><td className="n">{r.fuel_flow ?? r.d0_mm}</td>
                  <td className={r.burned ? 'oc-b' : 'oc-o'}>{r.outcome}</td><td className="n">{r.distance.toFixed(2)}</td>
                  <td><button className="btn small" data-open-test={r.code} onClick={() => { dlg.current?.close?.(); onOpenTest(r.code, r.resource_id); }}>Open in table</button></td>
                </tr>))}</tbody></table></div>
            <p className="muted fc-small" id="fcModel">
              {res.model.chosen
                ? <>Model: {res.model.chosen}, trained on {res.model.n_tests} {res.model.investigation} tests ({res.model.psi_id}). On {res.model.n_campaigns} NASA campaigns it never saw: AUC {res.model.auc?.toFixed(2)} (chance 0.50); {res.model.skill != null ? `${Math.round(res.model.skill * 100)} % better than always guessing the average` : ''}. Small dataset: treat it as a screening estimate.</>
                : <>No model beat the always-the-average baseline on unseen campaigns, so only real tests are shown.</>}
            </p>
          </div>
        )}
        <div className="fc-foot">
          <span className="muted" style={{ fontSize: 12.5 }} aria-live="polite" id="fcMsg">{msg}</span>
          <span style={{ display: 'flex', gap: 8 }}>
            <button className="btn primary" id="fcReport" disabled={!current} onClick={download}>Download report</button>
            <button className="btn" id="fcClose" onClick={() => { dlg.current?.close?.(); onClose(); }}>Close</button>
          </span>
        </div>
      </div>
    </dialog>,
    document.body,
  );
}
