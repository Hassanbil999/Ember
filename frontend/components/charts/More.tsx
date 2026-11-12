"use client";
import * as d3 from "d3";
import { forwardRef, useMemo, useState } from "react";
import { fmt, fmtVar, scaled, unitOf, vmeta } from "@/lib/format";
import { outcomeColor, PALETTES, PaletteName } from "@/lib/chart";
import { AxisBottom, AxisLeft, HatchDefs } from "./Axes";

const M = { t: 26, r: 18, b: 40, l: 52 };

/* ------------------------------------------------------------ Envelope */
export const Envelope = forwardRef<SVGSVGElement, {
  grid: { xs: number[]; ys: number[]; p: number[][]; x: string; y: string; label: string };
  rows: any[]; width: number; height: number; logX?: boolean; marker?: { x?: number; y?: number; label?: string } | null;
  onPoint?: (r: any) => void; title?: string;
}>(function Envelope({ grid, rows, width: W, height: H, logX, marker, onPoint, title }, ref) {
  const { xs, ys, p, x, y } = grid;
  const sx = (logX ? d3.scaleLog() : d3.scaleLinear()).domain([xs[0], xs[xs.length - 1]]).range([M.l, W - M.r]) as d3.ScaleContinuousNumeric<number, number>;
  const syRaw = d3.scaleLinear().domain([ys[0], ys[ys.length - 1]]).range([H - M.b, M.t]);
  const sc = vmeta(y).display_scale ?? 1;
  const syDisp = d3.scaleLinear().domain([ys[0] * sc, ys[ys.length - 1] * sc]).range([H - M.b, M.t]);
  const nx = xs.length, ny = ys.length;
  const flat = p.flat();
  const contours = d3.contours().size([nx, ny]).thresholds([0.25, 0.5, 0.75])(flat);
  // map grid index space → pixel space
  const gx = (i: number) => {
    const f = i / (nx - 1);
    const v = logX ? Math.exp(Math.log(xs[0]) + (Math.log(xs[nx - 1]) - Math.log(xs[0])) * f) : xs[0] + (xs[nx - 1] - xs[0]) * f;
    return sx(v);
  };
  const gy = (j: number) => syRaw(ys[0] + (ys[ny - 1] - ys[0]) * (j / (ny - 1)));
  const path = d3.geoPath(d3.geoTransform({ point(px, py) { this.stream.point(gx(px - 0.5), gy(py - 0.5)); } }));
  const cell = (i: number, j: number) => {
    const v = p[j][i];
    if (v >= 0.75) return "var(--flame-soft)";
    if (v <= 0.25) return "var(--ext-soft)";
    return "url(#hatch-unc)";
  };
  const cw = (W - M.l - M.r) / nx, ch = (H - M.t - M.b) / ny;
  const pts = rows.filter((r) => r[x] != null && r[y] != null && (!logX || r[x] > 0));
  return (
    <svg ref={ref} width={W} height={H} role="img" aria-label={`Envelope: model probability of sustained burning over ${vmeta(x).label} and ${vmeta(y).label}`}>
      <HatchDefs />
      {title && <text x={M.l} y={14} fontSize={13} fill="var(--text)">{title}</text>}
      {p.map((row, j) => row.map((_, i) => (
        <rect key={`${i}-${j}`} x={M.l + i * cw} y={H - M.b - (j + 1) * ch} width={cw + 0.5} height={ch + 0.5} fill={cell(i, j)} />
      )))}
      <clipPath id="env-clip"><rect x={M.l + 2} y={M.t + 2} width={W - M.l - M.r - 4} height={H - M.t - M.b - 4} /></clipPath>
      {contours.map((c) => (
        <path key={c.value} clipPath="url(#env-clip)" d={path(c as any) ?? ""} fill="none" stroke={c.value === 0.5 ? "var(--text)" : "var(--unc)"} strokeWidth={c.value === 0.5 ? 1.3 : 0.8} strokeDasharray={c.value === 0.5 ? undefined : "3 3"} />
      ))}
      <AxisBottom x={sx} y={H - M.b} label={`${vmeta(x).label} (${unitOf(x)})${logX ? " · log" : ""}`} />
      <AxisLeft y={syDisp} x={M.l} label={`${vmeta(y).label} (${unitOf(y)})`} />
      {pts.map((r) => (
        <circle key={r.test_id} cx={sx(r[x])} cy={syRaw(r[y])} r={3.2} fill={r.gravity_g >= 0.5 ? "transparent" : outcomeColor(r.burned)} stroke={r.gravity_g >= 0.5 ? outcomeColor(r.burned) : "var(--bg)"} strokeWidth={0.8} style={{ cursor: "pointer" }} onClick={() => onPoint?.(r)}>
          <title>{`${r.test_id} · ${r.burned ? "burned" : "extinguished"}`}</title>
        </circle>
      ))}
      {marker?.x != null && marker?.y != null && (
        <g transform={`translate(${sx(marker.x)},${syRaw(marker.y)})`}><circle r={8} fill="none" stroke="var(--text)" strokeWidth={1.3} /><text x={12} y={-10} fontSize={13} fill="var(--text)">{marker.label}</text></g>
      )}
      <g transform={`translate(${W - M.r - 250},${M.t + 4})`} fontSize={13} fill="var(--text-2)">
        <rect width={10} height={10} fill="var(--flame-soft)" stroke="var(--flame)" strokeWidth={.6} /><text x={14} y={9}>p(burn) ≥ 0.75</text>
        <rect x={98} width={10} height={10} fill="url(#hatch-unc)" stroke="var(--unc)" strokeWidth={.6} /><text x={112} y={9}>uncertain</text>
        <rect x={172} width={10} height={10} fill="var(--ext-soft)" stroke="var(--ext)" strokeWidth={.6} /><text x={186} y={9}>≤ 0.25</text>
      </g>
    </svg>
  );
});

/* ------------------------------------------------------------ Distribution */
export const Distribution = forwardRef<SVGSVGElement, { rows: any[]; v: string; width: number; height: number; split?: string; bins?: number; title?: string; palette?: PaletteName }>(
  function Distribution({ rows, v, width: W, height: H, split = "burned", bins = 24, title, palette = "default" }, ref) {
    const vals = rows.map((r) => scaled(v, r[v])).filter((x): x is number => x != null);
    const sx = d3.scaleLinear().domain(d3.extent(vals) as [number, number]).nice().range([M.l, W - M.r]);
    const bin = d3.bin().domain(sx.domain() as [number, number]).thresholds(sx.ticks(bins));
    const keys = split === "burned" ? [1, 0] : Array.from(new Set(rows.map((r) => r[split]).filter((x) => x != null)));
    const series = keys.map((k) => ({ k, bins: bin(rows.filter((r) => r[split] === k).map((r) => scaled(v, r[v])).filter((x): x is number => x != null)) }));
    const ymax = d3.max(series.flatMap((s) => s.bins.map((b) => b.length))) ?? 1;
    const sy = d3.scaleLinear().domain([0, ymax]).nice().range([H - M.b, M.t]);
    const col = (k: any, i: number) => (split === "burned" ? outcomeColor(k) : PALETTES[palette][i % 6]);
    return (
      <svg ref={ref} width={W} height={H} role="img" aria-label={`Distribution of ${vmeta(v).label}`}>
        {title && <text x={M.l} y={14} fontSize={13} fill="var(--text)">{title}</text>}
        {series.map((s, i) => (
          <g key={String(s.k)}>
            <path d={d3.line<any>().curve(d3.curveStepAfter).x((b) => sx(b.x0)).y((b) => sy(b.length))([...s.bins, { x0: s.bins[s.bins.length - 1]?.x1, length: 0 }]) ?? ""} fill="none" stroke={col(s.k, i)} strokeWidth={1.4} />
            {s.bins.map((b, j) => <rect key={j} x={sx(b.x0!)} y={sy(b.length)} width={Math.max(0, sx(b.x1!) - sx(b.x0!))} height={sy(0) - sy(b.length)} fill={col(s.k, i)} opacity={0.12} />)}
            {s.bins.length > 0 && (() => { const top = s.bins.reduce((a, b) => (b.length > a.length ? b : a)); return <text x={sx((top.x0! + top.x1!) / 2)} y={sy(top.length) - 6} fontSize={13} textAnchor="middle" fill={col(s.k, i)}>{split === "burned" ? (s.k ? "burned" : "extinguished") : String(s.k)}</text>; })()}
          </g>
        ))}
        <AxisBottom x={sx} y={H - M.b} label={`${vmeta(v).label}${unitOf(v) ? ` (${unitOf(v)})` : ""}`} />
        <AxisLeft y={sy} x={M.l} label="tests" />
      </svg>
    );
  });

/* ------------------------------------------------------------ Parallel coordinates (drag axes to reorder) */
export const Parallel = forwardRef<SVGSVGElement, { rows: any[]; vars: string[]; width: number; height: number; onReorder?: (v: string[]) => void; title?: string }>(
  function Parallel({ rows, vars, width: W, height: H, onReorder, title }, ref) {
    const [drag, setDrag] = useState<{ v: string; x: number } | null>(null);
    const sx = d3.scalePoint().domain(vars).range([M.l + 10, W - M.r - 30]);
    const ys = useMemo(() => Object.fromEntries(vars.map((v) => [v, d3.scaleLinear().domain(d3.extent(rows, (r) => r[v]) as [number, number]).nice().range([H - M.b, M.t + 14])])), [rows, vars, H]);
    const xOf = (v: string) => (drag && drag.v === v ? drag.x : sx(v)!);
    const line = (r: any) => d3.line<string>().defined((v) => r[v] != null)((vars).map((v) => v))?.toString();
    void line;
    return (
      <svg ref={ref} width={W} height={H} role="img" aria-label={`Parallel coordinates over ${vars.join(", ")}`}
        onPointerMove={(e) => { if (!drag) return; const r = (e.currentTarget as SVGSVGElement).getBoundingClientRect(); setDrag({ ...drag, x: e.clientX - r.left }); }}
        onPointerUp={() => {
          if (!drag) return;
          const order = [...vars].sort((a, b) => xOf(a) - xOf(b));
          setDrag(null); onReorder?.(order);
        }}>
        {title && <text x={M.l} y={14} fontSize={13} fill="var(--text)">{title}</text>}
        {rows.map((r) => {
          const pts = vars.filter((v) => r[v] != null).map((v) => [xOf(v), ys[v](r[v])] as [number, number]);
          return <path key={r.test_id} d={d3.line()(pts) ?? ""} fill="none" stroke={outcomeColor(r.burned)} strokeWidth={0.8} opacity={0.35} />;
        })}
        {vars.map((v) => (
          <g key={v} transform={`translate(${xOf(v)},0)`}>
            <line y1={ys[v].range()[0]} y2={ys[v].range()[1]} stroke="var(--line-strong)" />
            {ys[v].ticks(4).map((t) => <text key={t} x={-4} y={ys[v](t)} dy="0.32em" fontSize={13} textAnchor="end" className="mono" fill="var(--text-3)">{fmt(scaled(v, t)!, 3)}</text>)}
            <text y={M.t} textAnchor="middle" fontSize={13} fill="var(--text)" style={{ cursor: "grab" }}
              onPointerDown={(e) => { (e.target as Element).setPointerCapture?.(e.pointerId); setDrag({ v, x: sx(v)! }); }}>
              ⇆ {vmeta(v).short ?? vmeta(v).label}
            </text>
          </g>
        ))}
      </svg>
    );
  });

/* ------------------------------------------------------------ Correlation / MI matrix */
export const CorrMatrix = forwardRef<SVGSVGElement, { rel: any; width: number; height: number; metric: "spearman" | "mutual_info"; clustered: boolean; title?: string }>(
  function CorrMatrix({ rel, width: W, height: H, metric, clustered, title }, ref) {
    const [hover, setHover] = useState<{ i: number; j: number } | null>(null);
    const order: number[] = clustered ? rel.order : rel.vars.map((_: any, i: number) => i);
    const n = order.length;
    const L = 150, T = 30;
    const size = Math.min((W - L - 20) / n, (H - T - 60) / n);
    const mat = rel[metric];
    const maxMI = Math.max(0.01, ...mat.flat().filter((v: any) => v != null && !Number.isNaN(v)));
    const color = (v: number | null) => {
      if (v == null || Number.isNaN(v)) return "url(#hatch-unc-gray)";
      if (metric === "mutual_info") return d3.interpolateLab("transparent", "#8F88B8")(Math.min(1, v / maxMI)) as string;
      return v >= 0 ? `color-mix(in srgb, var(--flame) ${Math.round(Math.abs(v) * 85)}%, transparent)` : `color-mix(in srgb, var(--ext) ${Math.round(Math.abs(v) * 85)}%, transparent)`;
    };
    const h = hover ? { a: rel.vars[order[hover.i]], b: rel.vars[order[hover.j]], v: mat[order[hover.i]][order[hover.j]], n: rel.n[order[hover.i]][order[hover.j]] } : null;
    return (
      <svg ref={ref} width={W} height={H} role="img" aria-label={`${metric === "spearman" ? "Spearman correlation" : "Mutual information"} matrix`}>
        <HatchDefs />
        {title && <text x={8} y={14} fontSize={13} fill="var(--text)">{title}</text>}
        {order.map((oi, i) => (
          <g key={oi}>
            <text x={L - 8} y={T + i * size + size / 2} dy="0.32em" textAnchor="end" fontSize={13} fill="var(--text-2)">{vmeta(rel.vars[oi]).label}</text>
            {order.map((oj, j) => {
              const v = mat[oi][oj];
              return (
                <g key={oj} onPointerEnter={() => setHover({ i, j })} onPointerLeave={() => setHover(null)}>
                  <rect x={L + j * size} y={T + i * size} width={size - 1} height={size - 1} fill={i === j ? "var(--surface-3)" : color(v)} stroke={hover && hover.i === i && hover.j === j ? "var(--text)" : "none"} />
                  {size > 34 && i !== j && v != null && <text x={L + j * size + size / 2} y={T + i * size + size / 2} dy="0.32em" textAnchor="middle" fontSize={13} className="mono" fill="var(--text)">{v.toFixed(2)}</text>}
                </g>
              );
            })}
          </g>
        ))}
        <text x={L} y={T + n * size + 18} fontSize={13} fill="var(--text-2)">
          {h ? `${vmeta(h.a).label} × ${vmeta(h.b).label}: ${h.v == null ? "insufficient data" : h.v.toFixed(3)} · n = ${h.n}` : metric === "spearman" ? "Spearman ρ — amber positive, blue negative. Hover for n." : "Mutual information (nats) — detects non-linear association. Hover for n."}
        </text>
        <text x={L} y={T + n * size + 36} fontSize={13} fill="var(--text-3)">Association, not causation. Cells with fewer than 12 paired tests are hatched.</text>
      </svg>
    );
  });

/* ------------------------------------------------------------ Timeline */
export const Timeline = forwardRef<SVGSVGElement, { rows: any[]; y: string; width: number; height: number; title?: string; onPoint?: (r: any) => void }>(
  function Timeline({ rows, y, width: W, height: H, title, onPoint }, ref) {
    const pts = rows.filter((r) => r.mission_date && r[y] != null).map((r) => ({ ...r, _d: new Date(r.mission_date) }));
    const sx = d3.scaleTime().domain(d3.extent(pts, (r) => r._d) as [Date, Date]).nice().range([M.l, W - M.r]);
    const sy = d3.scaleLinear().domain(d3.extent(pts, (r) => scaled(y, r[y])!) as [number, number]).nice().range([H - M.b, M.t]);
    const camps = d3.groups(pts, (r) => r.campaign);
    return (
      <svg ref={ref} width={W} height={H} role="img" aria-label={`Timeline of ${vmeta(y).label}`}>
        {title && <text x={M.l} y={14} fontSize={13} fill="var(--text)">{title}</text>}
        {camps.map(([c, rs]) => {
          const [a, b] = d3.extent(rs, (r) => r._d) as [Date, Date];
          return <g key={c}><line x1={sx(a)} x2={sx(b)} y1={H - M.b - 6} y2={H - M.b - 6} stroke="var(--text-3)" /><text x={sx(a)} y={H - M.b - 10} fontSize={13} className="mono" fill="var(--text-3)">{c}</text></g>;
        })}
        <g transform={`translate(0,${H - M.b})`}>
          <line x1={M.l} x2={W - M.r} stroke="var(--line-strong)" />
          {sx.ticks(6).map((t) => <text key={+t} x={sx(t)} y={15} fontSize={13} textAnchor="middle" className="mono" fill="var(--text-3)">{d3.timeFormat("%Y")(t)}</text>)}
        </g>
        <AxisLeft y={sy as any} x={M.l} label={`${vmeta(y).label}${unitOf(y) ? ` (${unitOf(y)})` : ""}`} />
        {pts.map((r) => <circle key={r.test_id} cx={sx(r._d)} cy={sy(scaled(y, r[y])!)} r={3.2} fill={outcomeColor(r.burned)} opacity={0.85} onClick={() => onPoint?.(r)} style={{ cursor: "pointer" }}><title>{`${r.test_id} ${r.mission_date} ${fmtVar(y, r[y])}`}</title></circle>)}
      </svg>
    );
  });

/* ------------------------------------------------------------ d² vs t (Image Lab) */
export function D2Chart({ curve, fit, width: W, height: H, frame, onHover, onWindow, events }: {
  curve: { t: number; d: number | null; d2: number | null }[]; fit: any; width: number; height: number; frame: number;
  onHover: (i: number) => void; onWindow?: (w: [number, number]) => void; events: any[];
}) {
  const [drag, setDrag] = useState<null | { a: number; b: number }>(null);
  const pts = curve.map((c, i) => ({ ...c, i })).filter((c) => c.d2 != null);
  const sx = d3.scaleLinear().domain([0, d3.max(curve, (c) => c.t) ?? 1]).range([M.l, W - M.r]);
  const sy = d3.scaleLinear().domain([0, (d3.max(pts, (c) => c.d2!) ?? 1) * 1.08]).range([H - M.b - 46, M.t]);
  const rH = 36, rTop = H - M.b - 30;
  const resid = fit?.residuals ?? [];
  const rmax = Math.max(1e-6, ...resid.map((r: any) => Math.abs(r.r)));
  const sr = d3.scaleLinear().domain([-rmax, rmax]).range([rTop + rH, rTop]);
  const w = fit?.window as [number, number] | undefined;
  const local = (e: React.PointerEvent) => sx.invert(e.clientX - (e.currentTarget as SVGElement).getBoundingClientRect().left);
  return (
    <svg width={W} height={H} role="img" aria-label="Droplet diameter squared versus time with d-squared law fit"
      onPointerMove={(e) => {
        const t = local(e);
        if (drag) setDrag({ ...drag, b: t });
        else { const near = pts.reduce((a, c) => (Math.abs(c.t - t) < Math.abs(a.t - t) ? c : a), pts[0]); if (near) onHover(near.i); }
      }}
      onPointerDown={(e) => { if (onWindow && e.shiftKey) { const t = local(e); setDrag({ a: t, b: t }); } }}
      onPointerUp={() => { if (drag && onWindow && Math.abs(drag.b - drag.a) > 0.2) onWindow([Math.min(drag.a, drag.b), Math.max(drag.a, drag.b)]); setDrag(null); }}>
      {w && <rect x={sx(w[0])} y={M.t} width={sx(w[1]) - sx(w[0])} height={sy(0) - M.t} fill="var(--surface-3)" />}
      {w && <text x={sx(w[0]) + 4} y={M.t + 12} fontSize={13} fill="var(--text-3)">fit window</text>}
      {drag && <rect x={sx(Math.min(drag.a, drag.b))} y={M.t} width={Math.abs(sx(drag.b) - sx(drag.a))} height={sy(0) - M.t} fill="var(--unc-soft)" stroke="var(--unc)" />}
      <AxisLeft y={sy} x={M.l} label="d² (mm²)" ticks={4} />
      <AxisBottom x={sx} y={H - M.b} label="time (s)" />
      {events.map((ev) => (
        <g key={ev.type} transform={`translate(${sx(ev.t)},0)`}>
          <line y1={M.t} y2={H - M.b} stroke={ev.type === "extinction" ? "var(--ext)" : ev.type === "ignition" ? "var(--flame)" : "var(--text-3)"} strokeDasharray="2 3" />
          <text x={3} y={M.t + 26} fontSize={13} fill="var(--text-2)">{ev.type.replace("_", " ")}</text>
        </g>
      ))}
      {fit?.ok && w && <line x1={sx(w[0])} x2={sx(w[1])} y1={sy(fit.d0_fit_mm ** 2 - fit.K * w[0])} y2={sy(fit.d0_fit_mm ** 2 - fit.K * w[1])} stroke="var(--text)" strokeWidth={1.2} />}
      {pts.map((c) => <circle key={c.i} cx={sx(c.t)} cy={sy(c.d2!)} r={c.i === frame ? 4.5 : 2.2} fill={c.i === frame ? "var(--text)" : "var(--text-2)"} />)}
      {fit?.ok && <text x={W - M.r} y={M.t + 4} textAnchor="end" fontSize={13} className="mono" fill="var(--text)">K = {fit.K.toFixed(4)} ± {fit.K_se.toExponential(1)} mm²/s · R² = {fit.r2.toFixed(4)} · n = {fit.n}</text>}
      <line x1={M.l} x2={W - M.r} y1={sr(0)} y2={sr(0)} stroke="var(--line-strong)" />
      <text x={M.l - 6} y={sr(0)} dy="0.32em" textAnchor="end" fontSize={13} fill="var(--text-3)">resid.</text>
      {resid.map((r: any, i: number) => <line key={i} x1={sx(r.t)} x2={sx(r.t)} y1={sr(0)} y2={sr(r.r)} stroke="var(--unc)" />)}
    </svg>
  );
}
