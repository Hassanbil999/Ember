"use client";
import type { ScaleContinuousNumeric } from "d3";

type S = ScaleContinuousNumeric<number, number>;

const nice = (v: number) => String(+v.toPrecision(3));
/** log scales produce every integer tick; keep 1-2-5 multiples so labels never collide */
function ticksOf(s: S, n: number) {
  const t = s.ticks(n);
  const isLog = typeof (s as any).base === "function";
  if (!isLog) return t;
  return t.filter((v) => { const m = v / Math.pow(10, Math.floor(Math.log10(v) + 1e-9)); return [1, 2, 5].some((k) => Math.abs(m - k) < 1e-6); });
}

export function AxisBottom({ x, y, label, ticks = 6, fmt }: { x: S; y: number; label?: string; ticks?: number; fmt?: (v: number) => string }) {
  const tv = ticksOf(x, ticks);
  const f = fmt ?? nice;
  const [a, b] = x.range();
  return (
    <g transform={`translate(0,${y})`} aria-hidden>
      <line x1={a} x2={b} stroke="var(--line-strong)" />
      {tv.map((t) => (
        <g key={t} transform={`translate(${x(t)},0)`}>
          <line y2={4} stroke="var(--line-strong)" />
          <text y={15} textAnchor="middle" fontSize={13} className="mono" fill="var(--text-3)">{f(t)}</text>
        </g>
      ))}
      {label && <text x={b} y={30} textAnchor="end" fontSize={13} fill="var(--text-2)">{label}</text>}
    </g>
  );
}

export function AxisLeft({ y, x, label, ticks = 5, fmt }: { y: S; x: number; label?: string; ticks?: number; fmt?: (v: number) => string }) {
  const tv = ticksOf(y, ticks);
  const f = fmt ?? nice;
  const [a, b] = y.range();
  return (
    <g transform={`translate(${x},0)`} aria-hidden>
      <line y1={a} y2={b} stroke="var(--line-strong)" />
      {tv.map((t) => (
        <g key={t} transform={`translate(0,${y(t)})`}>
          <line x2={-4} stroke="var(--line-strong)" />
          <text x={-7} dy="0.32em" textAnchor="end" fontSize={13} className="mono" fill="var(--text-3)">{f(t)}</text>
        </g>
      ))}
      {label && <text x={4} y={Math.min(a, b) - 8} fontSize={13} fill="var(--text-2)">{label}</text>}
    </g>
  );
}

export function HatchDefs({ id = "hatch-unc" }: { id?: string }) {
  return (
    <defs>
      <pattern id={id} width="6" height="6" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
        <line x1="0" y1="0" x2="0" y2="6" stroke="var(--unc)" strokeWidth="1.4" opacity=".55" />
      </pattern>
      <pattern id={`${id}-gray`} width="6" height="6" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
        <line x1="0" y1="0" x2="0" y2="6" stroke="var(--nodata)" strokeWidth="1" opacity=".45" />
      </pattern>
    </defs>
  );
}
