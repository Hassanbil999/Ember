/* Overview charts. Outcome identity: burn orange + filled dot = kept burning, cool blue + ring = went out
   (shape as well as colour, the same encoding as the flammability map; both hues validated on the dark surface). */
import { useState } from 'react';
import type { CheckPoint } from '../api';
import type { Preset } from '../types';

const W = 560, H = 320, M = { l: 46, r: 14, t: 14, b: 40 };
const X = [10, 45] as const, Y = [0, 46] as const;
const sx = (v: number) => M.l + ((v - X[0]) / (X[1] - X[0])) * (W - M.l - M.r);
const sy = (v: number) => H - M.b - ((v - Y[0]) / (Y[1] - Y[0])) * (H - M.t - M.b);

/* Presets that share the same air become one marker ("ISS cabin / Earth lab"). */
export function airMarkers(presets: Preset[]) {
  const by = new Map<string, { o2: number; psi: number; labels: string[] }>();
  for (const p of presets) {
    if (p.key === 'rover') continue;                     // same air as the Moon base, fan off
    const k = `${p.o2}|${p.psi}`;
    const m = by.get(k) ?? { o2: p.o2, psi: p.psi, labels: [] };
    m.labels.push(p.label.replace(' cabin', '').replace(' lab', ''));
    by.set(k, m);
  }
  return [...by.values()].map(m => ({ ...m, label: m.labels.join(' · ') + ' air' }));
}

interface Tip { x: number; y: number; text: string }

/* Put a marker's two-line label in the corner that covers the fewest test dots and stays inside the plot. */
function place(x: number, y: number, label: string, sub: string, points: CheckPoint[]) {
  const w = Math.max(label.length * 6.6, sub.length * 6.8) + 4, h = 30;
  const options = [
    { dx: 16, dy: -30, anchor: 'start' as const }, { dx: -16, dy: -30, anchor: 'end' as const },
    { dx: 16, dy: 18, anchor: 'start' as const }, { dx: -16, dy: 18, anchor: 'end' as const },
  ];
  let bestScore = Infinity, best = options[0];
  for (const o of options) {
    const x0 = o.anchor === 'start' ? x + o.dx : x + o.dx - w, x1 = x0 + w, y0 = y + o.dy - 4, y1 = y0 + h;
    const out = x0 < M.l || x1 > W - M.r || y0 < M.t || y1 > H - M.b ? 1000 : 0;
    const hits = points.filter(p => { const px = sx(p.o2_pct), py = sy(p.psi); return px > x0 - 5 && px < x1 + 5 && py > y0 - 5 && py < y1 + 5; }).length;
    if (out + hits < bestScore) { bestScore = out + hits; best = o; }
  }
  return { tx: x + best.dx, ty: y + best.dy + 10, anchor: best.anchor };
}

export function CoverageChart({ id, title, points, presets, yes, no }: { id: string; title: string; points: CheckPoint[]; presets: Preset[]; yes: string; no: string }) {
  const [tip, setTip] = useState<Tip | null>(null);
  const nYes = points.filter(p => p.burned).length;
  const o2 = points.map(p => p.o2_pct), ps = points.map(p => p.psi);
  const summary = `${points.length} NASA tests: ${nYes} ${yes}, ${points.length - nYes} ${no}. Oxygen ${Math.min(...o2)}–${Math.max(...o2)} %, pressure ${Math.min(...ps)}–${Math.max(...ps)} psi.`;
  const markers = airMarkers(presets);
  const fuels = [...new Set(points.map(p => p.fuel))].sort();
  const show = (e: React.MouseEvent, p: CheckPoint) => setTip({ x: e.clientX, y: e.clientY, text: `${p.id} · ${p.fuel} · ${p.o2_pct} % O₂ · ${p.psi} psi · ${p.burned ? yes : no}` });
  return (
    <figure className="chart" id={id}>
      <figcaption><b>{title}</b><span className="muted">{summary}</span></figcaption>
      <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label={`${title}. ${summary}`} onMouseLeave={() => setTip(null)}>
        {[10, 20, 30, 40].map(v => <g key={'x' + v}><line x1={sx(v)} x2={sx(v)} y1={M.t} y2={H - M.b} className="grid" /><text x={sx(v)} y={H - M.b + 16} className="tick" textAnchor="middle">{v}</text></g>)}
        {[0, 10, 20, 30, 40].map(v => <g key={'y' + v}><line x1={M.l} x2={W - M.r} y1={sy(v)} y2={sy(v)} className="grid" /><text x={M.l - 8} y={sy(v) + 4} className="tick" textAnchor="end">{v}</text></g>)}
        <text x={(M.l + W - M.r) / 2} y={H - 6} className="axis" textAnchor="middle">Oxygen, % by volume</text>
        <text x={12} y={(M.t + H - M.b) / 2} className="axis" textAnchor="middle" transform={`rotate(-90 12 ${(M.t + H - M.b) / 2})`}>Pressure, psi</text>
        {points.map(p => p.burned
          ? <circle key={p.id} cx={sx(p.o2_pct)} cy={sy(p.psi)} r={4} className="dot-b" />
          : <circle key={p.id} cx={sx(p.o2_pct)} cy={sy(p.psi)} r={4} className="dot-o" />)}
        {points.map(p => <circle key={'h' + p.id} cx={sx(p.o2_pct)} cy={sy(p.psi)} r={9} className="hit" onMouseMove={e => show(e, p)} />)}
        {markers.map(m => {
          const x = sx(m.o2), y = sy(m.psi), p = place(x, y, m.label, `${m.o2} % · ${m.psi} psi`, points);
          return (
            <g key={m.label} className="air">
              <circle cx={x} cy={y} r={8} /><line x1={x - 13} x2={x + 13} y1={y} y2={y} /><line x1={x} x2={x} y1={y - 13} y2={y + 13} />
              <text x={p.tx} y={p.ty} textAnchor={p.anchor}>{m.label}</text>
              <text x={p.tx} y={p.ty + 14} textAnchor={p.anchor} className="sub">{m.o2} % · {m.psi} psi</text>
            </g>
          );
        })}
      </svg>
      <div className="legend">
        <span><i className="lg-b" />{yes}</span><span><i className="lg-o" />{no}</span><span><i className="lg-air" />planned cabin air</span>
      </div>
      <details className="tview"><summary>Show as a table</summary>
        <div className="tablebox"><table>
          <thead><tr><th>Fuel</th><th className="n">Tests</th><th className="n">{yes}</th><th className="n">{no}</th><th className="n">O₂ %</th><th className="n">psi</th></tr></thead>
          <tbody>{fuels.map(f => {
            const ps2 = points.filter(p => p.fuel === f), y2 = ps2.filter(p => p.burned).length;
            const lo = (k: 'o2_pct' | 'psi') => Math.min(...ps2.map(p => p[k])), hi = (k: 'o2_pct' | 'psi') => Math.max(...ps2.map(p => p[k]));
            return <tr key={f}><td>{f}</td><td className="n">{ps2.length}</td><td className="n">{y2}</td><td className="n">{ps2.length - y2}</td><td className="n">{lo('o2_pct')}–{hi('o2_pct')}</td><td className="n">{lo('psi')}–{hi('psi')}</td></tr>;
          })}</tbody>
        </table></div>
      </details>
      {tip && <div className="tooltip" style={{ left: tip.x + 12, top: tip.y + 12 }} role="status">{tip.text}</div>}
    </figure>
  );
}

export function OutcomeBars({ rows }: { rows: { label: string; yes: number; no: number; yesText: string; noText: string }[] }) {
  return (
    <div className="obars">
      {rows.map(r => {
        const n = r.yes + r.no;
        return (
          <div className="obar" key={r.label}>
            <span className="olabel">{r.label}</span>
            <div className="otrack" role="img" aria-label={`${r.label}: ${r.yes} ${r.yesText}, ${r.no} ${r.noText}, of ${n} tests`}>
              <i className="seg-b" style={{ flexGrow: r.yes }} /><i className="seg-o" style={{ flexGrow: r.no }} />
            </div>
            <span className="ovals"><b>{r.yes}</b> {r.yesText} · <b>{r.no}</b> {r.noText}</span>
          </div>
        );
      })}
      <div className="legend"><span><i className="lg-b" />kept burning</span><span><i className="lg-o" />went out</span></div>
    </div>
  );
}
