/* "Where is the line?": the chance a fire keeps going as oxygen rises, every other input held as entered.
   The model line and its range appear only where an estimate is allowed; untested oxygen is hatched.
   Same-fuel NASA tests sit on the top (kept going) and bottom (went out) rows: position and colour both
   carry the outcome, filled = tested near the engineer's other settings, hollow = at other settings. */
import { useState } from 'react';
import type { OxygenLine as Line } from '../api';

// outcome rows sit outside the plot (top: kept going, bottom: went out) so they never touch the model line
const W = 640, H = 262, M = { l: 44, r: 14, t: 30, b: 50 };
const ROW_YES = 14, ROW_NO = H - M.b + 14;
const IW = W - M.l - M.r, IH = H - M.t - M.b;

export function OxygenLine({ data, entered, yes, no }: { data: Line; entered: number; yes: string; no: string }) {
  const [hover, setHover] = useState<number | null>(null);
  const xs = data.points.map(p => p.o2_pct);
  const x0 = xs[0], x1 = xs[xs.length - 1];
  const X = (o: number) => M.l + ((o - x0) / (x1 - x0)) * IW;
  const Y = (p: number) => M.t + (1 - p) * IH;
  const est = data.points.filter(p => p.p !== null);
  const path = (k: 'p' | 'low' | 'high') => est.map((p, i) => `${i ? 'L' : 'M'}${X(p.o2_pct).toFixed(1)},${Y(p[k] as number).toFixed(1)}`).join('');
  const band = est.length ? `${path('high')}L${[...est].reverse().map(p => `${X(p.o2_pct).toFixed(1)},${Y(p.low as number).toFixed(1)}`).join('L')}Z` : '';
  // untested stretches along the axis (hatched)
  const gaps: [number, number][] = [];
  let s: number | null = null;
  data.points.forEach((p, i) => {
    if (p.p === null && s === null) s = p.o2_pct;
    if ((p.p !== null || i === data.points.length - 1) && s !== null) { gaps.push([s, p.p === null ? p.o2_pct : data.points[i - 1].o2_pct]); s = null; }
  });
  const ticks = Array.from({ length: Math.floor((x1 - x0) / 5) + 1 }, (_, i) => Math.ceil(x0 / 5) * 5 + i * 5).filter(t => t <= x1);
  const h = hover !== null ? data.points[hover] : null;
  const onMove = (e: React.PointerEvent<SVGRectElement>) => {
    const r = (e.currentTarget as SVGRectElement).getBoundingClientRect();
    const o = x0 + ((e.clientX - r.left) / r.width) * (x1 - x0);
    setHover(xs.reduce((b, v, i) => (Math.abs(v - o) < Math.abs(xs[b] - o) ? i : b), 0));
  };
  const L = data.line;
  const summary = L?.o2_pct != null
    ? `The estimated chance passes 50 % at about ${L.o2_pct} % oxygen.`
    : est.length ? `The estimated chance stays between ${Math.round((L?.min_p ?? 0) * 100)} % and ${Math.round((L?.max_p ?? 0) * 100)} % where an estimate is allowed.`
      : 'No estimate anywhere on this line: these settings are outside what NASA tested for this fuel.';

  return (
    <figure className="ol" aria-label={`Chance it keeps going as oxygen changes. ${summary}`}>
      <div className="ol-legend" aria-hidden="true">
        <span><i className="sw line" />Model estimate and range</span>
        <span><i className="sw dot b" />{yes}</span>
        <span><i className="sw dot o" />{no}</span>
        <span><i className="sw hollow" />at other settings</span>
        <span><i className="sw hatch" />untested</span>
      </div>
      <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-hidden="true">
        <defs><pattern id="olHatch" width="6" height="6" patternUnits="userSpaceOnUse" patternTransform="rotate(45)"><line x1="0" y1="0" x2="0" y2="6" stroke="var(--line)" strokeWidth="2" /></pattern></defs>
        {gaps.map(([a, b]) => <rect key={a} x={X(a)} y={M.t} width={Math.max(2, X(b) - X(a))} height={IH} fill="url(#olHatch)" />)}
        {[0, 0.5, 1].map(p => <g key={p}><line x1={M.l} x2={W - M.r} y1={Y(p)} y2={Y(p)} stroke="var(--line)" strokeDasharray={p === 0.5 ? '4 4' : undefined} />
          <text x={M.l - 6} y={Y(p) + 4} textAnchor="end" className="ol-ax">{p * 100} %</text></g>)}
        {ticks.map(t => <text key={t} x={X(t)} y={H - 6} textAnchor="middle" className="ol-ax">{t}</text>)}
        <text x={W - M.r} y={H - 20} textAnchor="end" className="ol-ax">oxygen, %</text>
        {band && <path d={band} fill="var(--ink)" opacity={0.12} />}
        {est.length > 1 && <path d={path('p')} fill="none" stroke="var(--ink)" strokeWidth={2} />}
        {L?.o2_pct != null && <g><line x1={X(L.o2_pct)} x2={X(L.o2_pct)} y1={Y(0.5) - 8} y2={Y(0.5) + 8} stroke="var(--ink)" strokeWidth={2} />
          <text x={X(L.o2_pct) - 6} y={Y(0.5) - 6} textAnchor="end" className="ol-lab">50 % at {L.o2_pct} %</text></g>}
        {(() => { const ex = X(Math.min(x1, Math.max(x0, entered))); const right = ex > W - M.r - 90;
          return <g><line x1={ex} x2={ex} y1={M.t} y2={M.t + IH} stroke="var(--muted)" strokeWidth={1.5} strokeDasharray="2 3" />
            <text x={right ? ex - 5 : ex + 5} y={M.t + 13} textAnchor={right ? 'end' : 'start'} className="ol-lab">yours {entered} %</text></g>; })()}
        {data.tests.map(t => {
          const cy = t.burned ? ROW_YES : ROW_NO, c = t.burned ? 'var(--burn)' : 'var(--cool)';
          return <circle key={t.code} cx={X(Math.min(x1, Math.max(x0, t.o2_pct)))} cy={cy} r={4} fill={t.near_settings ? c : 'none'}
            stroke={t.near_settings ? 'var(--panel-solid)' : c} strokeWidth={t.near_settings ? 2 : 1.5} opacity={t.near_settings ? 1 : 0.7}>
            <title>{`${t.code}: ${t.burned ? yes : no} at ${t.o2_pct} % oxygen${t.near_settings ? ', near your other settings' : ', at other settings'}`}</title></circle>;
        })}
        {h && <g pointerEvents="none"><line x1={X(h.o2_pct)} x2={X(h.o2_pct)} y1={M.t} y2={M.t + IH} stroke="var(--muted)" />
          {h.p !== null && <circle cx={X(h.o2_pct)} cy={Y(h.p)} r={4} fill="var(--ink)" stroke="var(--panel-solid)" strokeWidth={2} />}</g>}
        <rect x={M.l} y={M.t} width={IW} height={IH} fill="transparent" onPointerMove={onMove} onPointerLeave={() => setHover(null)} />
      </svg>
      <p className="muted fc-small ol-tip" aria-live="polite">{h
        ? (h.p !== null ? `${h.o2_pct} % oxygen: ${Math.round(h.p * 100)} % chance (range ${Math.round((h.low ?? 0) * 100)}–${Math.round((h.high ?? 0) * 100)} %), ${h.zone}` : `${h.o2_pct} % oxygen: untested, no estimate`)
        : summary}</p>
      {L?.falls_with_oxygen && <p className="fc-small ol-warn">Physics check: the estimate falls as oxygen rises above {L.falls_with_oxygen.from_o2} %. More oxygen is expected to help a flame, so this probably reflects other differences between those NASA tests (their exact flow or pressure), not oxygen itself. Read that part with caution.</p>}
      <figcaption className="muted fc-small">Held as entered: {data.held.join(', ').toLowerCase()}. Dots are the NASA tests of this fuel.</figcaption>
    </figure>
  );
}
