/* "From NASA tables to the model" (Statistics): the cleaning funnel as a pipeline strip, the unsupervised groups of
   test conditions (Gaussian mixture), and what the supervised Gaussian process learned (chance map, empty where the
   fire check would say untested). Group colours: the validated dark-surface categorical slots in fixed order, always
   with a numbered label, since colour alone cannot separate six groups in a scatter. */
import { useState } from 'react';
import type { PipelineView } from '../api';

export const GROUP_COLOR = ['#3987e5', '#d95926', '#199e70', '#c98500', '#d55181', '#0ca30c'];
const W = 480, H = 330, M = { l: 46, r: 14, t: 14, b: 42 };
const nice = (v: number) => String(Math.abs(v) >= 10 ? +v.toFixed(1) : +v.toFixed(2));
/* Short labels for a group's profile: "O₂ 37.1 % · 12.7 psi · leak 0.9 mg/s"; CO₂ and helium only when present. */
const SHORT: Record<string, string> = { o2_pct: 'O₂', psi: '', fuel_flow: 'leak', d0_mm: 'drop', co2_pct: 'CO₂', he_pct: 'He' };

interface Tip { x: number; y: number; lines: string[] }
const TipBox = ({ tip }: { tip: Tip | null }) => tip ? <div className="tooltip" style={{ left: tip.x + 14, top: tip.y + 14 }} role="status">{tip.lines.map(l => <div key={l}>{l}</div>)}</div> : null;

function scales(xs: number[], ys: number[]) {
  const pad = (a: number, b: number) => { const d = (b - a) * 0.06 || 1; return [a - d, b + d] as const; };
  const [x0, x1] = pad(Math.min(...xs), Math.max(...xs)), [y0, y1] = pad(Math.min(...ys), Math.max(...ys));
  const sx = (v: number) => M.l + ((v - x0) / (x1 - x0)) * (W - M.l - M.r);
  const sy = (v: number) => H - M.b - ((v - y0) / (y1 - y0)) * (H - M.t - M.b);
  const ticks = (a: number, b: number) => { const step = (b - a) > 30 ? 10 : (b - a) > 12 ? 5 : 2; const out: number[] = []; for (let t = Math.ceil(a / step) * step; t <= b; t += step) out.push(t); return out; };
  return { sx, sy, xt: ticks(x0, x1), yt: ticks(y0, y1) };
}

function Axes({ sx, sy, xt, yt }: ReturnType<typeof scales>) {
  return <>
    {xt.map(v => <g key={'x' + v}><line x1={sx(v)} x2={sx(v)} y1={M.t} y2={H - M.b} className="grid" /><text x={sx(v)} y={H - M.b + 16} className="tick" textAnchor="middle">{v}</text></g>)}
    {yt.map(v => <g key={'y' + v}><line x1={M.l} x2={W - M.r} y1={sy(v)} y2={sy(v)} className="grid" /><text x={M.l - 8} y={sy(v) + 4} className="tick" textAnchor="end">{v}</text></g>)}
    <text x={(M.l + W - M.r) / 2} y={H - 6} className="axis" textAnchor="middle">Oxygen, %</text>
    <text x={12} y={(M.t + H - M.b) / 2} className="axis" textAnchor="middle" transform={`rotate(-90 12 ${(M.t + H - M.b) / 2})`}>Pressure, psi</text>
  </>;
}

/* 1 · cleaning, as a pipeline: each box is a stage, its bar the share of the original rows that remain. */
export function PipelineStrip({ v }: { v: PipelineView }) {
  const first = v.cleaning[0]?.n || 1;
  return (
    <ol className="pipe" id="pipeFunnel" aria-label="Cleaning: rows kept at each stage">
      {v.cleaning.map((s, i) => (
        <li key={s.stage}>
          <b>{s.n}</b><span>{s.stage}</span>
          <i className="bar"><i style={{ width: `${(s.n / first) * 100}%` }} /></i>
          {i > 0 && s.n < v.cleaning[i - 1].n && <em>−{v.cleaning[i - 1].n - s.n}</em>}
        </li>
      ))}
    </ol>
  );
}

/* 2 · unsupervised: groups of test conditions, drawn on oxygen × pressure. */
export function ClusterChart({ v }: { v: PipelineView }) {
  const [tip, setTip] = useState<Tip | null>(null);
  const c = v.clusters, pts = c.points;
  const S = scales(pts.map(p => p.o2_pct), pts.map(p => p.psi));
  const profile = (g: PipelineView['clusters']['groups'][number]) => c.inputs
    .filter(i => !(i.key === 'co2_pct' || i.key === 'he_pct') || g.mean[i.key] >= 0.05)
    .map(i => [SHORT[i.key] ?? i.label, nice(g.mean[i.key]), i.unit].filter(Boolean).join(' ')).join(' · ');
  return (
    <figure className="chart" id="pipeClusters">
      <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label={`${c.k} groups of ${v.investigation} test conditions found by a Gaussian mixture without using the outcome.`} onMouseLeave={() => setTip(null)}>
        <Axes {...S} />
        {pts.map(p => <circle key={p.id} cx={S.sx(p.o2_pct)} cy={S.sy(p.psi)} r={4.5} fill={GROUP_COLOR[(p.group - 1) % 6]} className="ring"
          onMouseMove={e => setTip({ x: e.clientX, y: e.clientY, lines: [`${p.id} · ${p.fuel}`, `group ${p.group} · ${p.o2_pct} % O₂ · ${p.psi} psi`] })} />)}
        {c.groups.map(g => {
          const mine = pts.filter(p => p.group === g.id);
          const x = S.sx(mine.reduce((a, p) => a + p.o2_pct, 0) / mine.length), y = S.sy(mine.reduce((a, p) => a + p.psi, 0) / mine.length);
          return <g key={g.id} className="gid"><circle cx={x} cy={y} r={10} fill={GROUP_COLOR[(g.id - 1) % 6]} /><text x={x} y={y + 4} textAnchor="middle">{g.id}</text></g>;
        })}
      </svg>
      <ul className="groups">
        {c.groups.map(g => (
          <li key={g.id}><i style={{ background: GROUP_COLOR[(g.id - 1) % 6] }}>{g.id}</i>
            <span><b>{g.n} tests</b> · {profile(g)}</span><em>{Math.round(g.kept_burning * 100)}% kept burning</em></li>
        ))}
      </ul>
      <p className="note">Gaussian mixture on {c.inputs.map(i => i.label.toLowerCase()).join(', ')}, outcome not used; {c.k} groups chosen by BIC. Agreement with NASA's {c.n_campaigns} campaigns: {c.ari_campaigns.toFixed(2)} (1 = same grouping).</p>
      <TipBox tip={tip} />
    </figure>
  );
}

/* 3 · supervised: the Gaussian process's chance over oxygen × pressure, empty where untested. */
export function ChanceMap({ v }: { v: PipelineView }) {
  const [tip, setTip] = useState<Tip | null>(null);
  const s = v.surface, nx = s.o2.length;
  const S = scales([s.o2[0], s.o2[nx - 1]], [s.psi[0], s.psi[s.psi.length - 1]]);
  const dx = Math.abs(S.sx(s.o2[1]) - S.sx(s.o2[0])), dy = Math.abs(S.sy(s.psi[1]) - S.sy(s.psi[0]));
  const nums = s.chance.filter((x): x is number => x != null), max = Math.max(...nums, 0.01);
  const held = s.held.map(h => `${h.label} ${nice(h.value)}${h.unit ? ' ' + h.unit : ''}`).join(', ');
  return (
    <figure className="chart" id="pipeMap">
      <figcaption>Fuel: {s.fuel} · {s.model}</figcaption>
      <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label={`Chance it keeps burning for ${s.fuel}, from ${Math.round(Math.min(...nums) * 100)} to ${Math.round(max * 100)} percent where an estimate is allowed; empty where untested.`} onMouseLeave={() => setTip(null)}>
        <defs><pattern id="untestedHatch" width="7" height="7" patternUnits="userSpaceOnUse" patternTransform="rotate(45)"><line x1="0" y1="0" x2="0" y2="7" stroke="#2c3866" strokeWidth="2" /></pattern></defs>
        <rect x={M.l} y={M.t} width={W - M.l - M.r} height={H - M.t - M.b} fill="url(#untestedHatch)" />
        {s.chance.map((p, i) => {
          if (p == null) return null;
          const o = s.o2[i % nx], ps = s.psi[Math.floor(i / nx)];
          return <rect key={i} x={S.sx(o) - dx / 2} y={S.sy(ps) - dy / 2} width={dx + 0.5} height={dy + 0.5} fill="#ff7a3d" fillOpacity={0.1 + 0.88 * (p / max)}
            onMouseMove={e => setTip({ x: e.clientX, y: e.clientY, lines: [`${nice(o)} % O₂ · ${nice(ps)} psi`, `${Math.round(p * 100)} % chance it ${s.outcome_yes}`] })} />;
        })}
        <Axes {...S} />
        {s.tests.map(t => <circle key={t.id} cx={S.sx(t.o2_pct)} cy={S.sy(t.psi)} r={4} className={t.burned ? 'td-b' : 'td-o'}
          onMouseMove={e => setTip({ x: e.clientX, y: e.clientY, lines: [`${t.id}`, `${t.o2_pct} % O₂ · ${t.psi} psi · ${t.burned ? s.outcome_yes : s.outcome_no}`] })} />)}
      </svg>
      <div className="legend map">
        <span className="ramp"><i />0–{Math.round(max * 100)}% chance it {s.outcome_yes}</span>
        <span><i className="lg-hatch" />untested: no number</span>
        <span><i className="lg-tb" />{s.outcome_yes}</span><span><i className="lg-to" />{s.outcome_no}</span>
      </div>
      <p className="note">Other inputs held at {held}. Dots: every NASA test of this fuel.</p>
      <TipBox tip={tip} />
    </figure>
  );
}
