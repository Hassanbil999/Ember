"use client";
import * as d3 from "d3";
import { forwardRef, useMemo, useState } from "react";
import { fmtVar, scaled, unitOf, vmeta } from "@/lib/format";
import { outcomeColor, PALETTES, PaletteName } from "@/lib/chart";
import { AxisBottom, AxisLeft, HatchDefs } from "./Axes";

export interface Box { x0: number; x1: number; y0: number; y1: number; label: string; hatch?: boolean; sub?: string }
export interface Annotation { x: number; y: number; text: string }

export interface ScatterProps {
  rows: any[]; x: string; y: string; color?: string; size?: string;
  logX?: boolean; logY?: boolean; palette?: PaletteName;
  width: number; height: number;
  highlight?: string[]; marker?: { x?: number; y?: number; label?: string } | null;
  boxes?: Box[]; annotations?: Annotation[];
  onPoint?: (r: any) => void; onBrush?: (ids: string[]) => void; onCanvasClick?: (x: number, y: number) => void;
  mini?: boolean; xDomain?: [number, number]; yDomain?: [number, number]; title?: string; labels?: boolean;
  extra?: (sx: any, sy: any) => React.ReactNode; boxLabels?: "inline" | "column";
}

const M = { t: 26, r: 18, b: 40, l: 52 };
const MC = { t: 26, r: 40, b: 40, l: 52 };
const MM = { t: 8, r: 6, b: 18, l: 30 };

const Scatter = forwardRef<SVGSVGElement, ScatterProps>(function Scatter(p, ref) {
  const m = p.mini ? MM : p.boxLabels === "column" ? MC : M;
  const W = p.width, H = p.height;
  const [hover, setHover] = useState<any>(null);
  const [brush, setBrush] = useState<null | { x0: number; y0: number; x1: number; y1: number }>(null);

  const val = (r: any, k: string) => scaled(k, r[k]);
  const rows = useMemo(() => p.rows.filter((r) => val(r, p.x) != null && val(r, p.y) != null && (!p.logX || val(r, p.x)! > 0) && (!p.logY || val(r, p.y)! > 0)), [p.rows, p.x, p.y, p.logX, p.logY]);

  const ext = (k: string, log?: boolean, dom?: [number, number]): [number, number] => {
    if (dom) return [scaled(k, dom[0])!, scaled(k, dom[1])!];
    const e = d3.extent(rows, (r) => val(r, k)) as [number, number];
    if (e[0] == null) return [0, 1];
    if (log) return [e[0] * 0.85, e[1] * 1.15];
    const pad = (e[1] - e[0]) * 0.06 || 1;
    return [e[0] - pad, e[1] + pad];
  };
  let xd = ext(p.x, p.logX, p.xDomain), yd = ext(p.y, p.logY, p.yDomain);
  for (const b of p.boxes ?? []) {
    xd = [Math.min(xd[0], scaled(p.x, b.x0)!), Math.max(xd[1], scaled(p.x, b.x1)!)];
    yd = [Math.min(yd[0], scaled(p.y, b.y0)!), Math.max(yd[1], scaled(p.y, b.y1)!)];
  }
  const sx = (p.logX ? d3.scaleLog() : d3.scaleLinear()).domain(xd).range([m.l, W - m.r]).nice() as d3.ScaleContinuousNumeric<number, number>;
  const sy = (p.logY ? d3.scaleLog() : d3.scaleLinear()).domain(yd).range([H - m.b, m.t]).nice() as d3.ScaleContinuousNumeric<number, number>;

  const pal = PALETTES[p.palette ?? "default"];
  const cmeta = p.color ? vmeta(p.color) : null;
  const isOutcome = p.color === "burned";
  const isCat = cmeta && (cmeta.kind === "category" || cmeta.kind === "date" || p.color === "dataset" || p.color === "campaign");
  const cats = isCat ? Array.from(new Set(rows.map((r) => r[p.color!]).filter((v) => v != null))).sort() : [];
  const cnum = !isOutcome && !isCat && p.color ? (d3.extent(rows, (r) => r[p.color!]) as [number, number]) : null;
  const ramp = cnum ? d3.scaleLinear<string>().domain(cnum).range([pal[1], pal[0]]).interpolate(d3.interpolateLab) : null;
  const colorOf = (r: any) => {
    if (!p.color) return "var(--text-2)";
    const v = r[p.color];
    if (isOutcome) return outcomeColor(v);
    if (v == null) return "var(--nodata)";
    if (isCat) return pal[cats.indexOf(v) % pal.length];
    return ramp!(v);
  };
  const sz = p.size ? d3.scaleSqrt().domain(d3.extent(rows, (r) => r[p.size!]) as [number, number]).range([2.5, 9]) : null;
  const rOf = (r: any) => (p.mini ? 2.2 : sz && r[p.size!] != null ? sz(r[p.size!]) : 3.6);
  const hl = p.highlight ? new Set(p.highlight) : null;

  // direct labels at class centroids (no legend boxes)
  const labels: { text: string; x: number; y: number; color: string }[] = [];
  if (p.labels !== false && !p.mini) {
    const groups = isOutcome ? [[1, "burned"], [0, "extinguished"]] : isCat ? cats.map((c) => [c, String(c)]) : [];
    for (const [key, text] of groups as any[]) {
      const g = rows.filter((r) => r[p.color!] === key);
      if (g.length < 2) continue;
      const cx = d3.median(g, (r) => sx(val(r, p.x)!))!, cy = d3.median(g, (r) => sy(val(r, p.y)!))!;
      labels.push({ text, x: cx, y: cy, color: isOutcome ? outcomeColor(key) : pal[cats.indexOf(key) % pal.length] });
    }
  }

  const gutterX = rows.length ? sx(d3.max(rows, (r) => val(r, p.x)!)!) + 40 : 0;
  // box labels: right of each box, pushed apart vertically so they never overlap
  const boxLY: number[] = (() => {
    const bs = (p.boxes ?? []).map((b, i) => ({ i, y: sy(scaled(p.y, b.y1)!) + 4 })).sort((a, b) => a.y - b.y);
    const out: number[] = [];
    let last = -Infinity;
    for (const b of bs) { const y = Math.max(b.y, last + 32); out[b.i] = y; last = y; }
    return out;
  })();

  const local = (e: React.PointerEvent) => {
    const r = (e.currentTarget as SVGElement).ownerSVGElement!.getBoundingClientRect();
    return [e.clientX - r.left, e.clientY - r.top];
  };

  const xl = `${vmeta(p.x).label}${unitOf(p.x) ? ` (${unitOf(p.x)})` : ""}`;
  const yl = `${vmeta(p.y).label}${unitOf(p.y) ? ` (${unitOf(p.y)})` : ""}`;

  return (
    <svg ref={ref} width={W} height={H} role="img" aria-label={`${p.title ?? "Scatter"}: ${yl} against ${xl}, ${rows.length} points`} style={{ display: "block" }}>
      <HatchDefs />
      {p.title && !p.mini && <text x={m.l} y={14} fontSize={13} fill="var(--text)">{p.title}</text>}
      {(p.boxes ?? []).map((b, i) => {
        const x0 = sx(scaled(p.x, b.x0)!), x1 = sx(scaled(p.x, b.x1)!), y0 = sy(scaled(p.y, b.y1)!), y1 = sy(scaled(p.y, b.y0)!);
        return (
          <g key={i}>
            <rect x={x0} y={y0} width={x1 - x0} height={y1 - y0} fill={b.hatch ? "url(#hatch-unc)" : "var(--surface-3)"} stroke="var(--unc)" strokeDasharray="3 3" strokeWidth={1} />
            {p.boxLabels === "column" ? (() => {
              const right = x1 > W - m.r - 230;
              const ly = boxLY[i], lx = right ? x0 - 18 : Math.max(x1 + 18, gutterX);
              const anc = right ? "end" : "start";
              return <>
                <polyline points={`${right ? x0 : x1},${y0} ${lx + (right ? 8 : -8)},${ly} ${lx + (right ? 2 : -2)},${ly}`} fill="none" stroke="var(--unc)" strokeWidth={0.8} />
                <text x={lx} y={ly + 3} fontSize={13} textAnchor={anc} fill="var(--text)" style={{ paintOrder: "stroke", stroke: "var(--bg)", strokeWidth: 3 }}>{b.label}</text>
                {b.sub && <text x={lx} y={ly + 17} fontSize={13} textAnchor={anc} className="mono" fill="var(--text-3)" style={{ paintOrder: "stroke", stroke: "var(--bg)", strokeWidth: 3 }}>{b.sub}</text>}
              </>;
            })() : <>
              <text x={x0 + 4} y={y0 - 5} fontSize={13} fill="var(--text-2)">{b.label}</text>
              {b.sub && <text x={x0 + 4} y={y1 + 12} fontSize={13} className="mono" fill="var(--text-3)">{b.sub}</text>}
            </>}
          </g>
        );
      })}
      {p.extra?.(sx, sy)}
      <AxisBottom x={sx} y={H - m.b} label={p.mini ? undefined : xl} ticks={p.mini ? 3 : 6} />
      <AxisLeft y={sy} x={m.l} label={p.mini ? undefined : yl} ticks={p.mini ? 3 : 5} />
      <rect x={m.l} y={m.t} width={Math.max(0, W - m.l - m.r)} height={Math.max(0, H - m.t - m.b)} fill="transparent"
        onPointerDown={(e) => { if (!p.onBrush && !p.onCanvasClick) return; const [x, y] = local(e); setBrush({ x0: x, y0: y, x1: x, y1: y }); (e.target as Element).setPointerCapture(e.pointerId); }}
        onPointerMove={(e) => { if (!brush) return; const [x, y] = local(e); setBrush({ ...brush, x1: x, y1: y }); }}
        onPointerUp={(e) => {
          if (!brush) return;
          const small = Math.abs(brush.x1 - brush.x0) < 4 && Math.abs(brush.y1 - brush.y0) < 4;
          if (small && p.onCanvasClick) p.onCanvasClick(sx.invert(brush.x0), sy.invert(brush.y0));
          else if (!small && p.onBrush) {
            const [a, b] = [Math.min(brush.x0, brush.x1), Math.max(brush.x0, brush.x1)];
            const [c, d] = [Math.min(brush.y0, brush.y1), Math.max(brush.y0, brush.y1)];
            p.onBrush(rows.filter((r) => { const X = sx(val(r, p.x)!), Y = sy(val(r, p.y)!); return X >= a && X <= b && Y >= c && Y <= d; }).map((r) => r.test_id));
          }
          setBrush(null);
        }} />
      <g>
        {rows.map((r) => {
          const dim = hl && !hl.has(r.test_id);
          const c = colorOf(r);
          const hollow = r.gravity_g >= 0.5;
          return (
            <circle key={r.test_id} cx={sx(val(r, p.x)!)} cy={sy(val(r, p.y)!)} r={rOf(r)}
              fill={hollow ? "transparent" : c} stroke={hollow ? c : "var(--bg)"} strokeWidth={hollow ? 1.2 : 0.6}
              opacity={dim ? 0.18 : 0.9} style={{ cursor: p.onPoint ? "pointer" : "default", transition: "opacity 150ms" }}
              onPointerEnter={() => setHover(r)} onPointerLeave={() => setHover(null)}
              onClick={() => p.onPoint?.(r)} />
          );
        })}
      </g>
      {labels.map((l) => (
        <text key={l.text} x={l.x + 10} y={l.y - 10} fontSize={13} fill={l.color} style={{ paintOrder: "stroke", stroke: "var(--bg)", strokeWidth: 3 }}>{l.text}</text>
      ))}
      {p.marker && p.marker.x != null && p.marker.y != null && (
        <g transform={`translate(${sx(scaled(p.x, p.marker.x)!)},${sy(scaled(p.y, p.marker.y)!)})`} pointerEvents="none">
          <circle r={9} fill="none" stroke="var(--text)" strokeWidth={1.2} />
          <line x1={-14} x2={-10} stroke="var(--text)" /><line x1={10} x2={14} stroke="var(--text)" />
          <line y1={-14} y2={-10} stroke="var(--text)" /><line y1={10} y2={14} stroke="var(--text)" />
          {p.marker.label && <text x={14} y={-12} fontSize={13} fill="var(--text)" style={{ paintOrder: "stroke", stroke: "var(--bg)", strokeWidth: 3 }}>{p.marker.label}</text>}
        </g>
      )}
      {(p.annotations ?? []).map((a, i) => (
        <g key={i} transform={`translate(${sx(a.x)},${sy(a.y)})`}>
          <line x1={0} y1={0} x2={18} y2={-18} stroke="var(--text-2)" />
          <text x={21} y={-20} fontSize={13} fill="var(--text)" style={{ paintOrder: "stroke", stroke: "var(--bg)", strokeWidth: 3 }}>{a.text}</text>
        </g>
      ))}
      {brush && <rect x={Math.min(brush.x0, brush.x1)} y={Math.min(brush.y0, brush.y1)} width={Math.abs(brush.x1 - brush.x0)} height={Math.abs(brush.y1 - brush.y0)} fill="var(--unc-soft)" stroke="var(--unc)" pointerEvents="none" />}
      {hover && !p.mini && (
        <g transform={`translate(${Math.min(sx(val(hover, p.x)!) + 10, W - 190)},${Math.max(sy(val(hover, p.y)!) - 58, 4)})`} pointerEvents="none">
          <rect width={180} height={52} rx={3} fill="var(--surface)" stroke="var(--line-strong)" />
          <text x={8} y={16} fontSize={13} className="mono" fill="var(--text)">{hover.test_id}{hover.burned != null ? (hover.burned ? " · burned" : " · extinguished") : ""}</text>
          <text x={8} y={31} fontSize={13} className="mono" fill="var(--text-2)">{vmeta(p.x).short ?? p.x} {fmtVar(p.x, hover[p.x])}</text>
          <text x={8} y={45} fontSize={13} className="mono" fill="var(--text-2)">{vmeta(p.y).short ?? p.y} {fmtVar(p.y, hover[p.y])}</text>
        </g>
      )}
    </svg>
  );
});

export default Scatter;
