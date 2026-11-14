/* Statistics charts.
   Coverage: outcome identity = burn orange + filled dot (kept burning) / cool blue + ring (went out); shape as well
   as colour. Model lines: fixed categorical slots per model name (blue, orange, aqua: the validated dark-surface
   trio), never re-assigned by rank; the model in use is drawn thicker and named in the legend. */
import { useState } from 'react';
import type { CheckPoint, ModelRow } from '../api';
import type { Preset } from '../types';

interface Tip { x: number; y: number; lines: string[] }
function Tooltip({ tip }: { tip: Tip | null }) {
  return tip ? <div className="tooltip" style={{ left: tip.x + 14, top: tip.y + 14 }} role="status">{tip.lines.map(l => <div key={l}>{l}</div>)}</div> : null;
}

/* ---------------- coverage: where NASA tested ---------------- */
const W = 560, H = 320, M = { l: 46, r: 14, t: 14, b: 40 };
const X = [10, 45] as const, Y = [0, 46] as const;
const sx = (v: number) => M.l + ((v - X[0]) / (X[1] - X[0])) * (W - M.l - M.r);
const sy = (v: number) => H - M.b - ((v - Y[0]) / (Y[1] - Y[0])) * (H - M.t - M.b);

/* Presets that share the same air become one marker ("Earth · ISS air"). */
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
  const summary = `${points.length} NASA tests: ${nYes} ${yes}, ${points.length - nYes} ${no}.`;
  const markers = airMarkers(presets);
  const fuels = [...new Set(points.map(p => p.fuel))].sort();
  return (
    <figure className="chart" id={id}>
      <figcaption>{title}</figcaption>
      <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label={`${title}. ${summary}`} onMouseLeave={() => setTip(null)}>
        {[10, 20, 30, 40].map(v => <g key={'x' + v}><line x1={sx(v)} x2={sx(v)} y1={M.t} y2={H - M.b} className="grid" /><text x={sx(v)} y={H - M.b + 16} className="tick" textAnchor="middle">{v}</text></g>)}
        {[0, 10, 20, 30, 40].map(v => <g key={'y' + v}><line x1={M.l} x2={W - M.r} y1={sy(v)} y2={sy(v)} className="grid" /><text x={M.l - 8} y={sy(v) + 4} className="tick" textAnchor="end">{v}</text></g>)}
        <text x={(M.l + W - M.r) / 2} y={H - 6} className="axis" textAnchor="middle">Oxygen, %</text>
        <text x={12} y={(M.t + H - M.b) / 2} className="axis" textAnchor="middle" transform={`rotate(-90 12 ${(M.t + H - M.b) / 2})`}>Pressure, psi</text>
        {points.map(p => <circle key={p.id} cx={sx(p.o2_pct)} cy={sy(p.psi)} r={4.5} className={p.burned ? 'dot-b' : 'dot-o'} />)}
        {points.map(p => <circle key={'h' + p.id} cx={sx(p.o2_pct)} cy={sy(p.psi)} r={9} className="hit"
          onMouseMove={e => setTip({ x: e.clientX, y: e.clientY, lines: [`${p.id} · ${p.fuel}`, `${p.o2_pct} % O₂ · ${p.psi} psi`, p.burned ? yes : no] })} />)}
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
      <Tooltip tip={tip} />
    </figure>
  );
}

/* ---------------- model lines: ROC on campaigns the model never saw ---------------- */
export const MODEL_COLOR: Record<string, string> = { 'logistic regression': '#3987e5', 'random forest': '#d95926', 'Gaussian process': '#199e70' };
const RW = 420, RH = 340, RM = { l: 48, r: 16, t: 14, b: 44 };
const rx = (v: number) => RM.l + v * (RW - RM.l - RM.r);
const ry = (v: number) => RH - RM.b - v * (RH - RM.t - RM.b);
const tprAt = (roc: [number, number][], f: number) => roc.reduce((t, [a, b]) => (a <= f + 1e-9 ? Math.max(t, b) : t), 0);

export function RocChart({ id, title, rows, chosen }: { id: string; title: string; rows: ModelRow[]; chosen: string | null }) {
  const [tip, setTip] = useState<Tip | null>(null);
  const [hx, setHx] = useState<number | null>(null);
  const models = rows.filter(r => r.roc && r.roc.length > 1) as (ModelRow & { roc: [number, number][] })[];
  const ordered = [...models.filter(m => m.model !== chosen), ...models.filter(m => m.model === chosen)];   // the model in use on top
  const path = (roc: [number, number][]) => roc.map(([a, b], i) => `${i ? 'L' : 'M'}${rx(a).toFixed(1)},${ry(b).toFixed(1)}`).join('');
  const move = (e: React.MouseEvent<SVGSVGElement>) => {
    const box = e.currentTarget.getBoundingClientRect();
    const f = Math.min(1, Math.max(0, ((e.clientX - box.left) / box.width * RW - RM.l) / (RW - RM.l - RM.r)));
    setHx(f);
    setTip({ x: e.clientX, y: e.clientY, lines: [`False alarms ${Math.round(f * 100)} %`, ...models.map(m => `${m.model}: catches ${Math.round(tprAt(m.roc, f) * 100)} %`)] });
  };
  const summary = models.map(m => `${m.model} AUC ${m.auc?.toFixed(2)}`).join(', ');
  return (
    <figure className="chart" id={id}>
      <figcaption>{title}</figcaption>
      <svg viewBox={`0 0 ${RW} ${RH}`} role="img" aria-label={`${title}. ${summary}. Diagonal: always guessing the average.`} onMouseMove={move} onMouseLeave={() => { setTip(null); setHx(null); }}>
        {[0, .25, .5, .75, 1].map(v => <g key={v}>
          <line x1={rx(v)} x2={rx(v)} y1={RM.t} y2={RH - RM.b} className="grid" /><line x1={RM.l} x2={RW - RM.r} y1={ry(v)} y2={ry(v)} className="grid" />
          <text x={rx(v)} y={RH - RM.b + 16} className="tick" textAnchor="middle">{v * 100}</text>
          <text x={RM.l - 8} y={ry(v) + 4} className="tick" textAnchor="end">{v * 100}</text>
        </g>)}
        <text x={(RM.l + RW - RM.r) / 2} y={RH - 8} className="axis" textAnchor="middle">False alarms, %</text>
        <text x={14} y={(RM.t + RH - RM.b) / 2} className="axis" textAnchor="middle" transform={`rotate(-90 14 ${(RM.t + RH - RM.b) / 2})`}>Fires caught, %</text>
        <line x1={rx(0)} y1={ry(0)} x2={rx(1)} y2={ry(1)} className="chance" />
        <text x={rx(.62)} y={ry(.56)} className="chance-l" transform={`rotate(-38 ${rx(.62)} ${ry(.56)})`}>coin flip</text>
        {ordered.map(m => <path key={m.model} d={path(m.roc)} fill="none" stroke={MODEL_COLOR[m.model] ?? 'var(--ink)'} strokeWidth={m.model === chosen ? 3 : 2} strokeLinejoin="round" opacity={m.model === chosen ? 1 : 0.8} />)}
        {hx != null && <line x1={rx(hx)} x2={rx(hx)} y1={RM.t} y2={RH - RM.b} className="cross" />}
        {hx != null && models.map(m => <circle key={'c' + m.model} cx={rx(hx)} cy={ry(tprAt(m.roc, hx))} r={4} fill={MODEL_COLOR[m.model]} className="ring" />)}
      </svg>
      <div className="legend lines">
        {models.map(m => <span key={m.model} className={m.model === chosen ? 'used' : ''}><i style={{ background: MODEL_COLOR[m.model] }} />{m.model} <b>{m.auc?.toFixed(2)}</b>{m.model === chosen && <em>in use</em>}</span>)}
      </div>
      <details className="tview"><summary>Show as a table</summary>
        <div className="tablebox"><table>
          <thead><tr><th>Model</th><th className="n">AUC</th><th className="n">Brier</th><th>Beats baseline</th></tr></thead>
          <tbody>{rows.map(r => <tr key={r.model}><td>{r.model}{r.model === chosen ? ' (in use)' : ''}</td><td className="n">{r.auc?.toFixed(3) ?? '—'}</td><td className="n">{r.brier?.toFixed(4) ?? '—'}</td><td>{r.beats_baseline == null ? 'baseline' : r.beats_baseline ? 'yes' : 'no'}</td></tr>)}</tbody>
        </table></div>
      </details>
      <Tooltip tip={tip} />
    </figure>
  );
}
