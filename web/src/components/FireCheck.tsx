/* Fire check dialog: an engineer enters fuel and conditions; the server answers from NASA's own
   outcome-labelled tests. Tested → the real tests answer; estimated → the validated model; untested → no number.
   One dialog, opened from the Simulate controls, in the same pattern as the Export dialog. */
import { useEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { api, type FireCheckMeta, type FireCheckReq, type FireCheckRes } from '../api';

const pct = (p: number) => `${Math.round(p * 100)} %`;
const r2 = (v: number) => (Math.abs(v) >= 10 ? Math.round(v) : Math.abs(v) >= 1 ? +v.toFixed(1) : +v.toFixed(2));
const ZONE: Record<string, string> = { tested: 'Tested', estimated: 'Estimated', untested: 'Untested' };

interface Props { o2: number; psi: number; g: number; onClose: () => void; onOpenTest: (code: string, resourceId: string | null) => void }

export function FireCheck({ o2, psi, g, onClose, onOpenTest }: Props) {
  const dlg = useRef<HTMLDialogElement>(null);
  const [meta, setMeta] = useState<FireCheckMeta | null>(null);
  const [req, setReq] = useState<FireCheckReq>({ problem: 'gas', fuel: 'propane', o2_pct: +o2.toFixed(1), psi: +psi.toFixed(2), gravity_g: g, fuel_flow: 1, d0_mm: 3, diluent: 'N2' });
  const [res, setRes] = useState<FireCheckRes | null>(null);
  const [err, setErr] = useState('');
  const [msg, setMsg] = useState('');

  const closeRef = useRef(onClose);
  closeRef.current = onClose;
  useEffect(() => {
    const d = dlg.current!;
    if (!d.open) { if (d.showModal) d.showModal(); else d.setAttribute('open', ''); }
    const onCancel = (e: Event) => { e.preventDefault(); closeRef.current(); };
    d.addEventListener('cancel', onCancel);
    api.fireCheckMeta().then(setMeta).catch(e => setErr(String(e.message || e)));
    return () => d.removeEventListener('cancel', onCancel);
  }, []);

  useEffect(() => {
    let stale = false;
    const t = setTimeout(() => {
      api.fireCheck(req).then(r => { if (!stale) { setRes(r); setErr(''); } }).catch(e => { if (!stale) setErr(String(e.message || e)); });
    }, 200);
    return () => { stale = true; clearTimeout(t); };
  }, [JSON.stringify(req)]); // eslint-disable-line react-hooks/exhaustive-deps

  const set = (p: Partial<FireCheckReq>) => setReq(r => ({ ...r, ...p }));
  const m = meta?.[req.problem];
  const range = (k: string) => m?.ranges[k] ? `tested ${r2(m.ranges[k][0])}–${r2(m.ranges[k][1])}` : '';
  const pick = (problem: 'gas' | 'droplet') => set({ problem, fuel: problem === 'gas' ? 'propane' : 'n-heptane' });

  async function download() {
    setMsg('Preparing…');
    try {
      const f = await api.fireCheckReport(req);
      const url = URL.createObjectURL(new Blob([f.text], { type: 'text/html' }));
      const a = document.createElement('a'); a.href = url; a.download = f.filename;
      document.body.appendChild(a); a.click(); a.remove();
      setTimeout(() => URL.revokeObjectURL(url), 2000);
      setMsg(`Saved ${f.filename}. Open it and choose Print to save a PDF.`);
    } catch (e) { setMsg('Report failed: ' + (e as Error).message); }
  }

  const num = (id: string, label: string, key: keyof FireCheckReq, unit: string, hint: string, step = 0.1) => (
    <div className="ctl fc-in">
      <div className="row"><label htmlFor={id}>{label}</label><span className="scale">{hint}</span></div>
      <div className="fc-num"><input id={id} type="number" inputMode="decimal" step={step} value={req[key] as number}
        onChange={e => set({ [key]: e.target.value === '' ? 0 : +e.target.value } as Partial<FireCheckReq>)} /><span className="muted">{unit}</span></div>
    </div>
  );

  return createPortal(
    <dialog id="fireDlg" ref={dlg} aria-labelledby="fcTitle" className="fc">
      <div className="dlg">
        <div className="phead"><h2 id="fcTitle" style={{ fontFamily: 'var(--font-display)', fontSize: 22, fontWeight: 600, color: 'var(--ink)', letterSpacing: '.04em' }}>Check against NASA tests</h2></div>
        <p className="muted" style={{ margin: 0, fontSize: 13 }}>Learned from NASA's microgravity tests with a measured outcome. Near a test, the test answers. Between tests, a validated model estimates. Outside them, no number.</p>
        <div className="seg" role="group" aria-label="Fire type">
          <button id="fcGas" aria-pressed={req.problem === 'gas'} onClick={() => pick('gas')}>Gas leak flame · CFI-G</button>
          <button id="fcDrop" aria-pressed={req.problem === 'droplet'} onClick={() => pick('droplet')}>Liquid fuel drop · FLEX</button>
        </div>
        <div className="fc-grid">
          <div className="ctl fc-in">
            <div className="row"><label htmlFor="fcFuel">Fuel</label></div>
            <select id="fcFuel" className="sel" value={req.fuel} onChange={e => set({ fuel: e.target.value })}>
              {(m?.fuels ?? [req.fuel]).map(f => <option key={f} value={f}>{f}</option>)}
            </select>
          </div>
          {num('fcO2', 'Oxygen', 'o2_pct', '%', range('o2_pct'), 0.5)}
          {num('fcP', 'Pressure', 'psi', 'psi', range('psi'), 0.1)}
          {req.problem === 'gas'
            ? num('fcFlow', 'Fuel flow (leak size)', 'fuel_flow', 'mg/s', range('fuel_flow'), 0.05)
            : num('fcD0', 'Drop size', 'd0_mm', 'mm', range('d0_mm'), 0.1)}
          {req.problem === 'droplet' && (
            <div className="ctl fc-in">
              <div className="row"><label htmlFor="fcDil">Rest of the air</label></div>
              <select id="fcDil" className="sel" value={req.diluent} onChange={e => set({ diluent: e.target.value as FireCheckReq['diluent'] })}>
                <option value="N2">Nitrogen</option><option value="CO2">Carbon dioxide</option><option value="He">Helium</option>
              </select>
            </div>
          )}
          <div className="ctl fc-in"><div className="row"><span>Gravity</span></div><span className="num">{g <= 0.02 ? 'microgravity' : `${g.toFixed(3)} g`}<small className="muted"> · from the simulator</small></span></div>
        </div>

        {err && <p className="err">{err}</p>}
        {res && (
          <div className="fc-res" aria-live="polite" data-zone={res.zone}>
            <div className="verdict">
              <span className={'pill zone-' + res.zone} id="fcZone">{ZONE[res.zone]}</span>
              <p id="fcVerdict">{res.verdict}</p>
              {res.reasons.length > 0 && <ul className="fc-reasons">{res.reasons.map(r => <li key={r}>{r}</li>)}</ul>}
            </div>
            {(res.estimate || res.quantities.length > 0) && (
              <div className="stats">
                {res.estimate && <div><b id="fcProb">{pct(res.estimate.probability)}</b><span>chance it {res.estimate.will} · {pct(res.estimate.low)}–{pct(res.estimate.high)}</span></div>}
                {res.quantities.map(q => <div key={q.label}><b>{q.value.toFixed(2)}</b><span>{q.label}, {q.unit} · {q.low.toFixed(2)}–{q.high.toFixed(2)}</span></div>)}
              </div>
            )}
            {res.drivers.length > 0 && (
              <p className="muted fc-small">Moves it most: {res.drivers.slice(0, 3).map(d => `${d.label.toLowerCase()} +${d.step} ${d.unit} → ${d.change_pts > 0 ? '+' : ''}${d.change_pts} pts`).join(' · ')}</p>
            )}
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
                ? <>Model: {res.model.chosen}, trained on {res.model.n_tests} {res.model.investigation} tests ({res.model.psi_id}). On {res.model.n_campaigns} NASA campaigns it never saw: AUC {res.model.auc?.toFixed(2)} (chance 0.50), Brier {res.model.brier?.toFixed(3)} vs {res.model.baseline_brier.toFixed(3)} for always guessing the average.</>
                : <>No model beat the always-the-average baseline on unseen campaigns, so only real tests are shown.</>}
            </p>
          </div>
        )}
        <div className="fc-foot">
          <span className="muted" style={{ fontSize: 12.5 }} aria-live="polite" id="fcMsg">{msg}</span>
          <span style={{ display: 'flex', gap: 8 }}>
            <button className="btn primary" id="fcReport" disabled={!res} onClick={download}>Download report</button>
            <button className="btn" id="fcClose" onClick={() => { dlg.current?.close?.(); onClose(); }}>Close</button>
          </span>
        </div>
      </div>
    </dialog>,
    document.body,
  );
}
