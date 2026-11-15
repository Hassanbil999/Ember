/* Flammability map (prototype drawMap): oxygen against airflow, the flame-limit line for the current gravity,
   pressure and material, measured tests as dots, and "you". Click to move the settings. */
import { useRef, useState } from 'react';
import { fmtU, limitAt } from '../sim/model';
import { sim, useSim } from '../sim/store';

const MAP = { w: 320, h: 200, l: 34, r: 8, t: 8, b: 30, x0: 0.1, x1: 50, y0: 14, y1: 46 };
const mx = (u: number) => MAP.l + (Math.log(Math.max(u, MAP.x0) / MAP.x0) / Math.log(MAP.x1 / MAP.x0)) * (MAP.w - MAP.l - MAP.r);
const my = (o: number) => MAP.t + (1 - (o - MAP.y0) / (MAP.y1 - MAP.y0)) * (MAP.h - MAP.t - MAP.b);
const ux = (x: number) => MAP.x0 * Math.pow(MAP.x1 / MAP.x0, (x - MAP.l) / (MAP.w - MAP.l - MAP.r));
const oy = (y: number) => MAP.y0 + (1 - (y - MAP.t) / (MAP.h - MAP.t - MAP.b)) * (MAP.y1 - MAP.y0);
const MONO = 'IBM Plex Mono,monospace';

export function FlammabilityMap() {
  const s = useSim();
  const state = s.params;
  const svgRef = useRef<SVGSVGElement>(null);
  const [tip, setTip] = useState<{ x: number; y: number; code: string } | null>(null);

  const pts: [number, number][] = [];
  for (let i = 0; i <= 80; i++) {
    const u = MAP.x0 * Math.pow(MAP.x1 / MAP.x0, i / 80);
    pts.push([mx(u), my(Math.min(MAP.y1, Math.max(MAP.y0, limitAt(u, state, s.modelParams))))]);
  }
  const line = pts.map((p, i) => (i ? 'L' : 'M') + p[0].toFixed(1) + ' ' + p[1].toFixed(1)).join(' ');
  const R = MAP.w - MAP.r, B = MAP.h - MAP.b;
  const gc = state.g < 0.02 ? 0 : state.g > 0.95 ? 1 : null;
  const recs = s.points.filter(r => r.material === state.mat && r.o2_pct != null && r.flow_cm_s != null && gc !== null && (r.gravity_g ?? 0) === gc);
  const cx = mx(Math.max(state.u, MAP.x0)), cy = my(Math.min(MAP.y1, Math.max(MAP.y0, state.o2)));

  function onClick(e: React.MouseEvent<SVGSVGElement>) {
    const svg = svgRef.current; if (!svg) return;
    const pt = svg.createSVGPoint(); pt.x = e.clientX; pt.y = e.clientY;
    const p = pt.matrixTransform(svg.getScreenCTM()!.inverse());
    if (p.x < MAP.l || p.x > MAP.w - MAP.r || p.y < MAP.t || p.y > MAP.h - MAP.b) return;
    let u = ux(p.x); if (u < 0.12) u = 0;
    sim.set({ u: +u.toFixed(u < 1 ? 2 : 1), o2: Math.round(oy(p.y) * 2) / 2, preset: 'custom' });
  }
  function onMove(e: React.MouseEvent<SVGSVGElement>) {
    const t = e.target as Element;
    const code = t.getAttribute && t.getAttribute('data-id');
    setTip(code ? { x: e.clientX, y: e.clientY, code } : null);
  }
  const tr = tip ? s.pointByCode.get(tip.code) : null;

  return (
    <>
      <svg id="map" ref={svgRef} viewBox="0 0 320 200" role="img" onClick={onClick} onMouseMove={onMove} onMouseLeave={() => setTip(null)}
        aria-label="Flammability map: oxygen against airflow. The line is the flame limit for the current gravity, pressure and material. Click to move the settings.">
        <path d={`${line} L${R} ${MAP.t} L${MAP.l} ${MAP.t} Z`} fill="rgba(212,119,42,.13)" />
        <path d={`${line} L${R} ${B} L${MAP.l} ${B} Z`} fill="rgba(63,142,232,.11)" />
        {[21, 30, 40].map(o => (
          <g key={o}>
            <line x1={MAP.l} x2={R} y1={my(o)} y2={my(o)} stroke="#1f2840" />
            <text x={MAP.l - 5} y={my(o) + 3.5} fill="#949eb3" fontSize="13" textAnchor="end" fontFamily={MONO}>{o} %</text>
          </g>
        ))}
        {[0.1, 1, 10, 50].map(u => <text key={u} x={mx(u)} y={B + 13} fill="#949eb3" fontSize="13" textAnchor="middle" fontFamily={MONO}>{u === 0.1 ? '≤0.1' : u}</text>)}
        <text x={(MAP.l + R) / 2} y={MAP.h - 3} fill="#949eb3" fontSize="13" textAnchor="middle">airflow, cm/s</text>
        <path d={line} fill="none" stroke="#e8ecf4" strokeWidth="2" />
        <text x={R - 4} y={MAP.t + 12} fill="#f3b07a" fontSize="13" fontWeight="500" textAnchor="end">Burns</text>
        <text x={R - 4} y={B - 6} fill="#9cc6f6" fontSize="13" fontWeight="500" textAnchor="end">Goes out</text>
        {recs.map(rec => {
          const b = rec.outcome === 'burned';
          return <circle key={rec.code} className="rec" data-id={rec.code} cx={mx(Math.max(rec.flow_cm_s!, MAP.x0))} cy={my(rec.o2_pct!)} r="5"
            fill={b ? '#d4772a' : '#0d121e'} stroke={b ? '#0d121e' : '#3f8ee8'} strokeWidth="2" />;
        })}
        <circle cx={cx} cy={cy} r="9" fill="none" stroke="#fff" strokeOpacity=".5" strokeWidth="1.5" />
        <circle cx={cx} cy={cy} r="4.5" fill="#fff" stroke="#0d121e" strokeWidth="2" />
      </svg>
      {tip && tr && (
        <div className="tooltip" style={{ left: tip.x + 14, top: tip.y + 14 }}>
          <b>{tr.code}</b> · {tr.sample_desc}<br />
          {tr.o2_pct}% O₂, {fmtU(tr.flow_cm_s)}, {tr.gravity_g ? '1 g' : '0 g'}: <b>{tr.outcome_text}</b>
          {!tr.verified && <><br /><span className="muted">{tr.placeholder ? 'Starter row, unverified' : 'Unverified'}</span></>}
        </div>
      )}
    </>
  );
}
