/* Simulate view (prototype "SIMULATE"): full-bleed stage, Experiment panel, Result panel, timeline. */
import { useEffect, useRef } from 'react';
import { FlammabilityMap } from '../components/FlammabilityMap';
import { Link } from '../router';
import { Timeline } from '../components/Timeline';
import { coverage, nearest } from '../sim/evidence';
import { fmtU, gName, model, sFromU, uFromS } from '../sim/model';
import { StageEngine, isWide } from '../sim/stage';
import { sim, useSim } from '../sim/store';

const ICON_FLAME = <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true"><path d="M12 3c1 3 5 5.5 5 10a5 5 0 0 1-10 0c0-2.5 1.5-4 2.5-5 .3 1.8 1.2 2.6 2 3 .3-3-1-5.5.5-8z" /></svg>;
const ICON_OUT = <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true"><circle cx="12" cy="12" r="8" /><path d="M8 12h8" /></svg>;
const ICON_MENU = <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true"><path d="M4 6h16M4 12h16M4 18h16" /></svg>;
const CHEV_L = <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true"><path d="M15 6l-6 6 6 6" /></svg>;
const CHEV_R = <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true"><path d="M9 6l6 6-6 6" /></svg>;

interface Props {
  active: boolean;
  panelL: boolean; panelR: boolean;
  setPanels: (l: boolean, r: boolean) => void;
  onFindData: () => void;
}

export function SimulateView({ active, panelL, panelR, setPanels, onFindData }: Props) {
  const wide = typeof window !== 'undefined' ? isWide() : true;
  const lOn = panelL || !wide, rOn = panelR || !wide;
  return (
    <section id="view-sim" className={'view' + (lOn ? '' : ' l-off') + (rOn ? '' : ' r-off')} aria-label="Simulator" hidden={!active}>
      <Stage active={active} panelL={lOn} panelR={rOn} />
      <button className="edge left" id="openL" hidden={lOn} aria-controls="panelL" onClick={() => { setPanels(true, panelR); setTimeout(() => document.getElementById('closeL')?.focus()); }}>{ICON_MENU}Controls</button>
      <button className="edge right" id="openR" hidden={rOn} aria-controls="panelR" onClick={() => { setPanels(panelL, true); setTimeout(() => document.getElementById('closeR')?.focus()); }}>Result{CHEV_L}</button>
      <Controls open={lOn} onClose={() => { setPanels(false, panelR); setTimeout(() => document.getElementById('openL')?.focus()); }} onFindData={onFindData} />
      <Result open={rOn} onClose={() => { setPanels(panelL, false); setTimeout(() => document.getElementById('openR')?.focus()); }} />
      <Timeline />
    </section>
  );
}

function Stage({ active, panelL, panelR }: { active: boolean; panelL: boolean; panelR: boolean }) {
  const stageRef = useRef<HTMLDivElement>(null);
  const tRef = useRef<HTMLCanvasElement>(null), sRef = useRef<HTMLCanvasElement>(null), fRef = useRef<HTMLCanvasElement>(null);
  const eng = useRef<StageEngine | null>(null);

  useEffect(() => {
    const e = new StageEngine(stageRef.current!, tRef.current!, sRef.current!, fRef.current!);
    eng.current = e;
    const onResize = () => { e.resize(); };
    window.addEventListener('resize', onResize);
    return () => { window.removeEventListener('resize', onResize); eng.current = null; };
  }, []);

  useEffect(() => {
    const e = eng.current; if (!e) return;
    e.panelL = panelL; e.panelR = panelR; e.layout();
  }, [panelL, panelR]);

  useEffect(() => {
    if (!active) return;
    eng.current?.resize();
    let last = performance.now(), raf = 0;
    const loop = (now: number) => {
      const dt = Math.min(0.05, (now - last) / 1000); last = now;
      sim.advance(dt);
      eng.current?.frame(dt);
      raf = requestAnimationFrame(loop);
    };
    raf = requestAnimationFrame(loop);
    return () => cancelAnimationFrame(raf);
  }, [active]);

  return (
    <div className="stage" id="stage" ref={stageRef}>
      <canvas id="trails" ref={tRef} aria-hidden="true" />
      <canvas id="scene" ref={sRef} aria-hidden="true" />
      <canvas id="flame" ref={fRef} role="img" aria-label="Side view of a burning sample in a flow duct. Air streams past it; the flame's shape and color change with gravity, oxygen, pressure and airflow." />
    </div>
  );
}

function Controls({ open, onClose, onFindData }: { open: boolean; onClose: () => void; onFindData: () => void }) {
  const s = useSim();
  const st = s.params;
  return (
    <aside className={'panel left' + (open ? '' : ' off')} id="panelL" aria-label="Experiment controls" {...(open ? {} : { inert: '' })}>
      <div className="phead"><h2>Experiment</h2><button className="icon-btn hide-btn" id="closeL" aria-label="Hide controls" aria-controls="panelL" aria-expanded={open} onClick={onClose}>{CHEV_L}</button></div>
      <div className="chips" id="presetChips" role="group" aria-label="Environment">
        {s.presets.map(p => (
          <button key={p.key} className="chip" data-k={p.key} title={p.note ?? undefined} aria-pressed={st.preset === p.key} onClick={() => sim.applyPreset(p)}>{p.label}</button>
        ))}
      </div>
      <div className="ctl">
        <div className="row"><label htmlFor="gR">Gravity</label><output id="gO" htmlFor="gR">{st.g.toFixed(2)} g<small>{gName(st.g)}</small></output></div>
        <input type="range" id="gR" min="0" max="1" step="0.002" value={st.g} onChange={e => sim.set({ g: +e.target.value, preset: 'custom' })} />
        <div className="scale"><span>0 g</span><span>Moon</span><span>Mars</span><span>Earth</span></div>
      </div>
      <div className="ctl">
        <div className="row"><label htmlFor="oR">Oxygen</label><output id="oO" htmlFor="oR">{st.o2.toFixed(1)}%</output></div>
        <input type="range" id="oR" min="15" max="45" step="0.5" value={st.o2} onChange={e => sim.set({ o2: +e.target.value, preset: 'custom' })} />
      </div>
      <div className="ctl">
        <div className="row"><label htmlFor="pR">Pressure</label><output id="pO" htmlFor="pR">{st.p.toFixed(1)} psi<small>{(st.p * 6.89476).toFixed(0)} kPa</small></output></div>
        <input type="range" id="pR" min="4" max="15" step="0.1" value={st.p} onChange={e => sim.set({ p: +e.target.value, preset: 'custom' })} />
      </div>
      <div className="ctl">
        <div className="row"><label htmlFor="uR">Airflow</label><output id="uO" htmlFor="uR">{fmtU(st.u)}</output></div>
        <input type="range" id="uR" min="0" max="100" step="1" value={sFromU(st.u)} aria-valuetext={fmtU(st.u)} onChange={e => sim.set({ u: uFromS(+e.target.value), preset: 'custom' })} />
        <div className="scale"><span>off</span><span>1</span><span>10</span><span>50 cm/s</span></div>
      </div>
      <div className="seg" role="group" aria-label="Material">
        <button id="mFabric" aria-pressed={st.mat === 'fabric'} onClick={() => sim.set({ mat: 'fabric' }, true)}>Cotton-fiberglass fabric</button>
        <button id="mPmma" aria-pressed={st.mat === 'pmma'} onClick={() => sim.set({ mat: 'pmma' }, true)}>Acrylic rod (PMMA)</button>
      </div>
      <button className="btn" id="toData" onClick={onFindData}>Find data for these settings</button>
      <Link className="btn" id="toCheck" to={`/engine/check?o2=${st.o2}&psi=${st.p}`}>Check a fuel</Link>
    </aside>
  );
}

function Result({ open, onClose }: { open: boolean; onClose: () => void }) {
  const s = useSim();
  const st = s.params, r = s.series.r;
  let txt: string;
  if (r.burns) {
    const iss = model({ g: 0, o2: 21, p: 14.7, u: 10, mat: st.mat }, s.modelParams);
    const k = r.spread / iss.spread;
    txt = k >= 1.05 ? k.toFixed(1) + '× faster than in ISS cabin air.' : k <= 0.95 ? (1 / k).toFixed(1) + '× slower than in ISS cabin air.' : 'About as fast as in ISS cabin air.';
    if (st.u === 0 && st.g > 0.02 && st.g < 0.95) txt += ' The fan is off, but gravity still feeds it about ' + r.ub.toFixed(0) + ' cm/s of flow.';
  } else txt = (r.regime === 'quench' ? 'Starved of oxygen. ' : 'Blown off by the airflow. ') + 'Needs about ' + r.xlim.toFixed(1) + '% O₂ here.';

  const cov = coverage(st, s.points);
  const near = nearest(st, s.points);
  return (
    <aside className={'panel right' + (open ? '' : ' off')} id="panelR" aria-label="Result" data-server={s.server} {...(open ? {} : { inert: '' })}>
      <div className="phead"><h2>Result</h2><button className="icon-btn hide-btn" id="closeR" aria-label="Hide result" aria-controls="panelR" aria-expanded={open} onClick={onClose}>{CHEV_R}</button></div>
      <div className="verdict" aria-live="polite">
        <span className={'pill ' + (r.burns ? 'burns' : 'out')} id="pill">{r.burns ? <>{ICON_FLAME}Burns</> : <>{ICON_OUT}Goes out</>}</span>
        <p id="verdictText">{txt}</p>
      </div>
      <div className="stats">
        <div><b id="sSpread">{r.burns ? r.spread.toFixed(1) : '0'}</b><span>spread, mm/s</span></div>
        <div><b id="sMargin">{(r.margin >= 0 ? '+' : '') + r.margin.toFixed(1)}</b><span>O₂ above limit, pts</span></div>
      </div>
      <div>
        <FlammabilityMap />
        <div className="legend">
          <span><i style={{ background: 'var(--burn)' }} />burned</span>
          <span><i style={{ border: '2px solid var(--cool)', width: 9, height: 9 }} />went out</span>
          <span><i style={{ background: '#fff' }} />you</span>
          <span>· click to move</span>
        </div>
      </div>
      <Compare />
      <div className="evid">
        <span className="sec">Evidence</span>
        <p id="coverage">{cov.text}</p>
        {near && (
          <p id="nearest">Closest test ({near.fit} match): <b>{near.point.code}</b>
            {!near.point.verified && <span className="badge" title={near.point.unverified_reason ?? undefined}>{near.point.placeholder ? 'starter row · unverified' : 'unverified'}</span>}
            , {near.point.o2_pct}% O₂, {fmtU(near.point.flow_cm_s)}, {near.point.outcome_text}. <button className="link" data-sim={near.point.code} onClick={() => sim.load(near.point.code)}>Load it</button></p>
        )}
      </div>
      <details className="how"><summary>How this is calculated</summary>
        <p>A simple model fitted to two published results: BASS-II limits for acrylic (burns at 17% O₂ in microgravity, not at 18% in normal gravity, no spread below about 0.6 cm/s) and the Saffire-I spread rate of 1.8 mm/s.</p>
        <p>Flame limit: X<sub>lim</sub> = [X<sub>min</sub> + k·ln²(u<sub>eff</sub>/u*)]·(14.7/P)<sup>0.15</sup>, with u<sub>eff</sub> = √(u² + u<sub>b</sub>² + u<sub>d</sub>²) and gravity-driven flow u<sub>b</sub> ≈ 30√g cm/s. Spread: V = c·(X<sub>O₂</sub> − X<sub>lim</sub>)·u<sub>eff</sub>/(u<sub>eff</sub>+5).</p>
        <ParamsNote />
        <p>It shows trends. It is not a design tool.</p>
      </details>
    </aside>
  );
}

function ParamsNote() {
  const s = useSim();
  const m = s.paramsMeta?.[s.params.mat];
  if (!m) return null;
  return <p>Parameters for this material: {m.n_points >= 4 ? `fitted to ${m.n_points} verified test points (RMSE ${m.rmse?.toFixed(2)}).` : `SPEC defaults. The fit needs at least 4 verified test points with oxygen, pressure, airflow and an outcome; the loaded NASA tables have ${m.n_points}.`}</p>;
}

function Compare() {
  const s = useSim();
  const st = s.params, r = s.series.r;
  if (!st.compare) return null;
  const rec = s.pointByCode.get(st.compare);
  if (!rec || rec.o2_pct == null) return null;
  const same = Math.abs(st.g - (rec.gravity_g ?? 0)) < 1e-6 && Math.abs(st.o2 - rec.o2_pct) < 1e-6 && Math.abs(st.u - (rec.flow_cm_s || 0)) < 1e-6 && st.mat === rec.material;
  const known = rec.outcome === 'burned' || rec.outcome === 'went_out';
  const agree = (rec.outcome === 'burned') === r.burns;
  return (
    <div className="compare" id="compareBox">
      <b>Testing {rec.code}{!rec.verified && <span className="badge">{rec.placeholder ? 'starter row · unverified' : 'unverified'}</span>}</b>
      <span>Measured: {rec.outcome_text}{rec.spread_mm_s ? ' at ' + rec.spread_mm_s + ' mm/s' : ''}. Model: {r.burns ? 'burns at ' + r.spread.toFixed(1) + ' mm/s' : 'goes out'}.</span>
      {rec.pressure_kpa == null && <span className="muted">The source does not report pressure; simulated at 14.7 psi.</span>}
      <span className="muted">{!same ? 'Settings changed since loading.' : !known ? 'No measured outcome to compare.' : agree ? 'The model agrees.' : 'The model disagrees. Flag for review.'}</span>
      <span><button className="link" id="cmpClose" onClick={() => sim.set({ compare: null })}>Close</button></span>
    </div>
  );
}
