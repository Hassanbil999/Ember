"use client";
import { useId } from "react";
import { useSize } from "@/lib/chart";
import { useUI } from "@/lib/store";

/* Small, single-purpose visuals. Rules they all follow: position and length carry the data
   (never area or colour alone), labels sit on the marks, amber = burned, blue = went out. */

const T = { fontSize: 13, fill: "var(--text-3)" } as const;

export function FlameGlyph({ kind, size = 120, lively = true }: { kind: "earth" | "micro"; size?: number; lively?: boolean }) {
  const id = useId().replace(/:/g, "");
  return (
    <svg width={size} height={size} viewBox="0 0 120 120" aria-hidden>
      <defs>
        <radialGradient id={`e${id}`} cx="50%" cy="72%" r="60%"><stop offset="0%" stopColor="#FFF3D6" /><stop offset="35%" stopColor="#FFB04A" /><stop offset="100%" stopColor="#FF7A1A" stopOpacity="0" /></radialGradient>
        <radialGradient id={`m${id}`}><stop offset="0%" stopColor="#0B0F17" stopOpacity="0" /><stop offset="58%" stopColor="#3D8BFF" stopOpacity=".15" /><stop offset="80%" stopColor="#6FB6FF" stopOpacity=".95" /><stop offset="100%" stopColor="#5AA9FF" stopOpacity="0" /></radialGradient>
      </defs>
      {kind === "earth" ? (
        <g>
          <path d="M60 8 C 84 44, 92 66, 80 88 C 72 102, 48 102, 40 88 C 28 66, 36 44, 60 8 Z" fill={`url(#e${id})`}>
            {lively && <animate attributeName="d" dur="1.6s" repeatCount="indefinite" values="M60 8 C 84 44, 92 66, 80 88 C 72 102, 48 102, 40 88 C 28 66, 36 44, 60 8 Z;M61 12 C 82 46, 90 68, 80 88 C 72 102, 48 102, 40 88 C 30 66, 38 42, 61 12 Z;M60 8 C 84 44, 92 66, 80 88 C 72 102, 48 102, 40 88 C 28 66, 36 44, 60 8 Z" />}
          </path>
          <rect x="57" y="88" width="6" height="22" rx="2" fill="var(--text-3)" />
        </g>
      ) : (
        <g>
          <circle cx="60" cy="60" r="46" fill={`url(#m${id})`}>
            {lively && <animate attributeName="r" dur="3.2s" repeatCount="indefinite" values="46;43;46" />}
          </circle>
          <circle cx="60" cy="60" r="7" fill="var(--text-2)" />
        </g>
      )}
    </svg>
  );
}

export function FlamesViz() {
  return (
    <div className="grid grid-cols-2 gap-6">
      {([["earth", "On Earth", "Hot gas rises, fresh air rushes in below. The flame is tall, bright and yellow."],
         ["micro", "In microgravity", "Nothing rises. Oxygen only drifts in, so the flame is a dim blue sphere."]] as const).map(([k, t, s]) => (
        <div key={k} className="flex flex-col items-center rounded-md px-4 py-6 text-center" style={{ background: "var(--surface-2)" }}>
          <FlameGlyph kind={k} size={200} />
          <p className="mt-3 text-lg font-medium text-ink">{t}</p>
          <p className="mt-1 max-w-[30ch] text-sm text-ink-2">{s}</p>
        </div>
      ))}
    </div>
  );
}

export function EnvelopeViz({ v, height = 380 }: { v: any; height?: number }) {
  const [ref, { w }] = useSize<HTMLDivElement>();
  const openProv = useUI((s) => s.openProv);
  const m = { l: 62, r: 20, t: 16, b: 48 };
  const xs = v.points.map((p: any) => p.o2_frac * 100).concat(v.box.o2_frac.map((x: number) => x * 100), (v.band?.o2_frac ?? []).map((x: number) => x * 100));
  const ys = v.points.map((p: any) => p.pressure_kpa).concat(v.box.pressure_kpa);
  const x0 = Math.max(0, Math.floor((Math.min(...xs) - 2) / 5) * 5), x1 = Math.ceil((Math.max(...xs) + 2) / 5) * 5;
  const y0 = Math.floor((Math.min(...ys) - 5) / 20) * 20, y1 = Math.ceil((Math.max(...ys) + 5) / 20) * 20;
  const sx = (x: number) => m.l + ((x - x0) / (x1 - x0)) * (w - m.l - m.r);
  const sy = (y: number) => height - m.b - ((y - y0) / (y1 - y0)) * (height - m.t - m.b);
  const xt = Array.from({ length: Math.floor((x1 - x0) / 5) + 1 }, (_, i) => x0 + i * 5).filter((_, i, a) => a.length <= 9 || i % 2 === 0);
  const yt = Array.from({ length: Math.floor((y1 - y0) / 20) + 1 }, (_, i) => y0 + i * 20);
  const bx = sx(v.box.o2_frac[0] * 100), bw = sx(v.box.o2_frac[1] * 100) - bx, by = sy(v.box.pressure_kpa[1]), bh = sy(v.box.pressure_kpa[0]) - by;
  return (
    <div ref={ref} className="w-full">
      {w > 0 && (
        <svg width={w} height={height} role="img" aria-label="Real tests by oxygen and pressure, with the planned air range outlined">
          {yt.map((t) => (<g key={t}><line x1={m.l} x2={w - m.r} y1={sy(t)} y2={sy(t)} stroke="var(--line)" /><text x={m.l - 10} y={sy(t) + 4} textAnchor="end" {...T}>{t}</text></g>))}
          {xt.map((t) => <text key={t} x={sx(t)} y={height - m.b + 20} textAnchor="middle" {...T}>{t}%</text>)}
          <text x={(m.l + w - m.r) / 2} y={height - 6} textAnchor="middle" {...T}>Oxygen in the atmosphere</text>
          <text transform={`translate(16 ${(m.t + height - m.b) / 2}) rotate(-90)`} textAnchor="middle" {...T}>Total pressure (kPa)</text>
          {v.band && (() => {
            // tests known by oxygen only (no pressure recorded): an oxygen band over the full height
            const x0b = sx(v.band.o2_frac[0] * 100), x1b = Math.max(x0b + 3, sx(v.band.o2_frac[1] * 100));
            return (<g data-band>
              <rect x={x0b} y={m.t} width={x1b - x0b} height={height - m.t - m.b} fill="var(--text-3)" opacity={0.12} />
              <line x1={x1b} x2={x1b} y1={m.t} y2={height - m.b} stroke="var(--text-2)" strokeDasharray="3 3" />
              <text x={x1b - 6} y={m.t + 14} textAnchor="end" fontSize={13} fill="var(--text-2)">{v.band.label}</text>
              <text x={x1b - 6} y={m.t + 30} textAnchor="end" fontSize={13} fill="var(--text-3)">up to {(v.band.o2_frac[1] * 100).toFixed(1)}% O₂</text>
            </g>);
          })()}
          <rect x={bx} y={by} width={bw} height={bh} fill="var(--flame-soft)" stroke="var(--flame)" strokeWidth={1.5} strokeDasharray="6 4" rx={4} />
          <text x={bx + bw / 2} y={by - 8} textAnchor="middle" fontSize={14} fontWeight={600} fill="var(--flame)">{v.box.label}</text>
          {v.points.map((p: any) => (
            <circle key={p.test_id} cx={sx(p.o2_frac * 100)} cy={sy(p.pressure_kpa)} r={5.5} style={{ cursor: "pointer" }}
              fill={p.burned == null ? "transparent" : p.burned ? "var(--flame)" : "var(--ext)"} stroke={p.burned == null ? "var(--nodata)" : "var(--bg)"} strokeWidth={1.5}
              onClick={() => openProv({ testId: p.test_id, label: p.test_id })}><title>{`${p.test_id}: ${p.burned == null ? "outcome not recorded" : p.burned ? "burned" : "went out"}. Select to see the record.`}</title></circle>
          ))}
        </svg>
      )}
      <p className="mt-1 flex flex-wrap items-center gap-x-5 gap-y-1 text-sm text-ink-2">
        <span className="flex items-center gap-2"><span className="h-3 w-3 rounded-full bg-flame" />Burned</span>
        <span className="flex items-center gap-2"><span className="h-3 w-3 rounded-full bg-ext" />Went out</span>
        {v.band && <span className="flex items-center gap-2"><span className="h-3 w-5 rounded-sm" style={{ background: "var(--text-3)", opacity: 0.35 }} />{v.band.label}</span>}
        <span className="text-ink-3">Select a dot to open that test.</span>
      </p>
    </div>
  );
}

export function CoverageViz({ rows }: { rows: any[] }) {
  const openProv = useUI((s) => s.openProv);
  const max = Math.max(1, ...rows.map((r) => r.n));
  return (
    <div className="w-full">
      <div className="grid grid-cols-[minmax(130px,1.1fr)_3fr_minmax(150px,1.2fr)] items-center gap-x-5 gap-y-3 text-sm">
        <span className="text-ink-3">Environment</span><span className="text-ink-3">Real tests inside its air range</span><span className="text-ink-3">Its gravity</span>
        {rows.map((r) => (
          <div key={r.id} className="contents">
            <div><p className="text-base text-ink">{r.label}</p><p className="text-xs text-ink-3">{r.air}</p></div>
            <button className="flex h-9 items-center gap-3 text-left" disabled={!r.n} onClick={() => openProv({ citation: { kind: "aggregate", op: "count", field: "test_id", rows: r.ids }, label: r.label })}
              title={r.n ? "Select to list these tests" : undefined}>
              <span className="h-5 rounded-sm" style={{ width: `${(r.n / max) * 78}%`, minWidth: r.n ? 4 : 0, background: "var(--text-2)" }} />
              <span className={`mono text-base ${r.n ? "text-ink" : "gap-glow"}`} style={r.n ? undefined : { color: "var(--warn)" }}>{r.n ? r.n : "0 tests"}</span>
            </button>
            <div>
              {r.gravity_tested
                ? <span className="text-sm text-ink-2">{r.gravity}: tested</span>
                : <span className="gap-glow text-sm font-medium" style={{ color: "var(--warn)" }}>{r.gravity}: never tested</span>}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

export function Bars({ v }: { v: any }) {
  const max = v.max ?? Math.max(...v.rows.map((r: any) => r.value)) * 1.08;
  const tone = v.tone === "ext" ? "var(--ext)" : v.tone === "text" ? "var(--text-2)" : "var(--flame)";
  const pctUnit = v.unit.startsWith("%");
  return (
    <div className="w-full">
      <div className="grid grid-cols-[minmax(110px,auto)_1fr] items-center gap-x-4 gap-y-2.5">
        {v.rows.map((r: any) => (
          <div key={r.label} className="contents">
            <span className="text-sm text-ink-2">{r.label}</span>
            <div className="flex h-7 items-center gap-3">
              <span className="h-5 rounded-sm" style={{ width: `${Math.max(0.5, (r.value / max) * 82)}%`, background: r.muted ? "var(--line-strong)" : tone }} />
              <span className="mono text-sm text-ink">{r.value}{pctUnit ? "%" : ""}</span>
              {r.n != null && <span className="text-xs text-ink-3">{pctUnit ? `${r.n} tests` : `of ${r.n}`}</span>}
            </div>
          </div>
        ))}
      </div>
      <p className="mt-2 text-xs text-ink-3">{pctUnit ? v.unit.replace("% ", "Share that ") : v.unit[0].toUpperCase() + v.unit.slice(1)}</p>
    </div>
  );
}

export function Strip({ v }: { v: any }) {
  const [ref, { w }] = useSize<HTMLDivElement>();
  const groups: string[] = Array.from(new Set(v.rows.map((r: any) => r.group)));
  const xs = v.rows.map((r: any) => r.x * v.scale);
  const x0 = Math.floor(Math.min(...xs) / 5) * 5, x1 = Math.ceil(Math.max(...xs) / 5) * 5;
  const rowH = 34, m = { l: 190, r: 16, t: 6, b: 40 }, h = m.t + groups.length * rowH + m.b;
  const sx = (x: number) => m.l + ((x - x0) / (x1 - x0)) * (w - m.l - m.r);
  const ticks = Array.from({ length: Math.floor((x1 - x0) / 5) + 1 }, (_, i) => x0 + i * 5);
  return (
    <div ref={ref} className="w-full">
      {w > 0 && (
        <svg width={w} height={h} role="img" aria-label={`${v.x_label}: burned versus went out, by group`}>
          {ticks.map((t) => (<g key={t}><line x1={sx(t)} x2={sx(t)} y1={m.t} y2={h - m.b} stroke="var(--line)" /><text x={sx(t)} y={h - m.b + 18} textAnchor="middle" {...T}>{t}</text></g>))}
          <text x={(m.l + w - m.r) / 2} y={h - 4} textAnchor="middle" {...T}>{v.x_label}</text>
          {groups.map((g, i) => {
            const cy = m.t + i * rowH + rowH / 2;
            return (
              <g key={g}>
                <text x={m.l - 14} y={cy + 4} textAnchor="end" fontSize={13} fill="var(--text-2)">{g}</text>
                {v.rows.filter((r: any) => r.group === g).map((r: any, j: number) => (
                  <circle key={j} cx={sx(r.x * v.scale)} cy={cy + (r.burned ? -6 : 6)} r={4.5} fill={r.burned ? "var(--flame)" : "var(--ext)"} fillOpacity={0.85} />
                ))}
              </g>
            );
          })}
        </svg>
      )}
      <p className="mt-1 flex items-center gap-5 text-xs text-ink-2">
        <span className="flex items-center gap-2"><span className="h-2.5 w-2.5 rounded-full bg-flame" />Burned (upper row)</span>
        <span className="flex items-center gap-2"><span className="h-2.5 w-2.5 rounded-full bg-ext" />Went out (lower row)</span>
      </p>
    </div>
  );
}

export function Visual({ v }: { v: any }) {
  if (v.kind === "envelope") return <EnvelopeViz v={v} />;
  if (v.kind === "coverage") return <CoverageViz rows={v.rows} />;
  if (v.kind === "flames") return <FlamesViz />;
  if (v.kind === "bars") return <Bars v={v} />;
  if (v.kind === "strip") return <Strip v={v} />;
  return null;
}
