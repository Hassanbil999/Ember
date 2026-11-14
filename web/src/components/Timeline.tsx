/* Timeline (prototype "TIMELINE"): play/pause, speed, draggable t1/t2 handles and playhead (keyboard-operable
   sliders), burned-length curve, out/burn-through marker and the stats line for t1 → t2. The playhead and clock
   update every frame through sim.onTick, outside React. */
import { useEffect, useLayoutEffect, useRef, useState } from 'react';
import { at, DT, fmtT, SAMPLE_MM } from '../sim/model';
import { sim, useSim } from '../sim/store';

const ICON_PLAY = <svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M7 4l13 8-13 8z" /></svg>;
const ICON_PAUSE = <svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M6 4h4v16H6zM14 4h4v16h-4z" /></svg>;

export function Timeline() {
  const s = useSim();
  const { series, tl } = s;
  const track = useRef<HTMLDivElement>(null);
  const ph = useRef<HTMLDivElement>(null);
  const tNow = useRef<HTMLSpanElement>(null);
  const tStat = useRef<HTMLSpanElement>(null);
  const [W, setW] = useState(0);
  const drag = useRef<null | 't1' | 't2' | 'play'>(null);

  useEffect(() => {
    if (!track.current) return;
    const ro = new ResizeObserver(() => setW(track.current?.clientWidth ?? 0));
    ro.observe(track.current); setW(track.current.clientWidth);
    return () => ro.disconnect();
  }, []);

  const xOfT = (t: number) => t / series.D * W;
  const tOfX = (x: number) => Math.min(series.D, Math.max(0, x / (W || 1) * series.D));

  function renderTime() {
    const { series: sr, tl: T } = sim;
    const w = track.current?.clientWidth ?? 0;
    if (ph.current) {
      ph.current.style.left = (T.t / sr.D * w) + 'px';
      ph.current.setAttribute('aria-valuenow', T.t.toFixed(1)); ph.current.setAttribute('aria-valuemax', String(sr.D)); ph.current.setAttribute('aria-valuetext', fmtT(T.t));
    }
    if (tNow.current) tNow.current.textContent = 't = ' + fmtT(T.t);
    if (tStat.current) {
      const a = at(sr.X, T.t1, sr.n), b = at(sr.X, T.t2, sr.n), dt = T.t2 - T.t1;
      let st = '';
      if (sr.tOut != null) st = 'Flame out at ' + fmtT(sr.tOut) + '. ';
      else if (sr.tEnd != null) st = 'Burns through at ' + fmtT(sr.tEnd) + '. ';
      tStat.current.innerHTML = st + 'From t1 <b>' + fmtT(T.t1) + '</b> to t2 <b>' + fmtT(T.t2) + '</b>, the front moves <b>' + (b - a).toFixed(1) + ' mm</b>' +
        (dt > 0 ? ' (<b>' + ((b - a) / dt).toFixed(2) + ' mm/s</b>)' : '');
    }
  }
  useEffect(() => sim.onTick(renderTime), []);
  useLayoutEffect(renderTime);

  function onDrag(e: React.PointerEvent) {
    if (!drag.current || !track.current) return;
    const rect = track.current.getBoundingClientRect(); const t = tOfX(e.clientX - rect.left);
    let { t1, t2 } = sim.tl;
    if (drag.current === 't1') t1 = Math.min(t, t2 - 0.5);
    else if (drag.current === 't2') t2 = Math.max(t, t1 + 0.5);
    else { sim.seek(t); return; }
    sim.setWindow(Math.max(0, t1), Math.min(series.D, t2));
  }
  function onDown(e: React.PointerEvent) {
    const h = (e.target as Element).closest('.hdl');
    drag.current = h ? (h.id === 'h1' ? 't1' : 't2') : 'play';
    track.current?.setPointerCapture(e.pointerId); onDrag(e);
  }
  function onKey(id: 'h1' | 'h2' | 'ph', e: React.KeyboardEvent) {
    const step = e.shiftKey ? 5 : 0.5, D = sim.series.D, T = sim.tl;
    let v = id === 'h1' ? T.t1 : id === 'h2' ? T.t2 : T.t;
    const k = e.key;
    if (k === 'ArrowRight' || k === 'ArrowUp') v += step; else if (k === 'ArrowLeft' || k === 'ArrowDown') v -= step;
    else if (k === 'Home') v = 0; else if (k === 'End') v = D; else return;
    e.preventDefault();
    v = Math.min(D, Math.max(0, v));
    if (id === 'h1') sim.setWindow(Math.min(v, T.t2 - 0.5), T.t2);
    else if (id === 'h2') sim.setWindow(T.t1, Math.max(v, T.t1 + 0.5));
    else sim.seek(v);
  }

  // burned-length curve
  const H = 30, D = series.D;
  let d = 'M0 ' + H;
  if (W) {
    const step = Math.max(1, Math.floor(series.n / 300));
    for (let k = 0; k < series.n; k += step) d += ' L' + (k * DT / D * W).toFixed(1) + ' ' + (H - 3 - (H - 6) * series.X[k] / SAMPLE_MM).toFixed(1);
    d += ' L' + W + ' ' + (H - 3 - (H - 6) * series.X[series.n - 1] / SAMPLE_MM).toFixed(1) + ' L' + W + ' ' + H + ' Z';
  }
  const ev = series.tOut != null ? series.tOut : series.tEnd != null ? series.tEnd : null;
  const tick = D <= 20 ? 5 : D <= 60 ? 10 : D <= 120 ? 20 : 60;
  const ticks: number[] = []; for (let t = tick; t < D; t += tick) ticks.push(t);
  const x1 = xOfT(tl.t1), x2 = xOfT(tl.t2);
  const sliderProps = (v: number) => ({ 'aria-valuemin': 0, 'aria-valuemax': D, 'aria-valuenow': +v.toFixed(1), 'aria-valuetext': fmtT(v) });

  return (
    <div className="timeline" id="timeline" aria-label="Timeline">
      <div className="tl-row">
        <button className="play" id="playBtn" aria-label={tl.playing ? 'Pause' : 'Play'} onClick={() => sim.togglePlay()}>{tl.playing ? ICON_PAUSE : ICON_PLAY}</button>
        <span className="tnow" id="tNow" ref={tNow} aria-live="off" />
        <label className="sr" htmlFor="speed">Playback speed</label>
        <select className="speed" id="speed" value={tl.speed} onChange={e => sim.setSpeed(+e.target.value)}>
          <option value="1">1×</option><option value="2">2×</option><option value="5">5×</option><option value="10">10×</option>
        </select>
        <span className="tstat" id="tStat" ref={tStat} />
      </div>
      <div className="track" id="track" ref={track} onPointerDown={onDown} onPointerMove={onDrag}
        onPointerUp={() => { drag.current = null; }} onPointerCancel={() => { drag.current = null; }}>
        <svg id="trackSvg" aria-hidden="true">
          {W > 0 && <>
            <rect x="0" y="0" width={W} height={H} rx="5" fill="#121a2b" />
            <rect x={x1} y="0" width={Math.max(0, x2 - x1)} height={H} fill="#1b2540" />
            <path d={d} fill="rgba(212,119,42,.28)" stroke="#d4772a" strokeWidth="1.2" />
            {ev != null && <line x1={xOfT(ev)} x2={xOfT(ev)} y1="2" y2={H - 2} stroke="#9cc6f6" strokeDasharray="3 3" />}
            {ticks.map(t => <text key={t} x={xOfT(t)} y={H + 12} fill="#5d6780" fontSize="10" textAnchor="middle" fontFamily="IBM Plex Mono,monospace">{t}</text>)}
          </>}
        </svg>
        <div className="hdl" id="h1" role="slider" tabIndex={0} aria-label="Start time t1" style={{ left: x1 }} {...sliderProps(tl.t1)} onKeyDown={e => onKey('h1', e)} />
        <div className="hdl" id="h2" role="slider" tabIndex={0} aria-label="End time t2" style={{ left: x2 }} {...sliderProps(tl.t2)} onKeyDown={e => onKey('h2', e)} />
        <div className="phd" id="ph" ref={ph} role="slider" tabIndex={0} aria-label="Current time" aria-valuemin={0} onKeyDown={e => onKey('ph', e)} />
      </div>
    </div>
  );
}
