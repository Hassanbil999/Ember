"use client";
import Link from "next/link";
import { useEffect, useMemo, useRef, useState } from "react";
import { get } from "@/lib/api";
import { useSize } from "@/lib/chart";
import { PSI } from "@/lib/format";
import { useMeta } from "@/lib/meta";
import { useUI } from "@/lib/store";

/* The atmosphere trade: one map of cabin pressure against oxygen, with the three things a crew
   atmosphere must satisfy laid over each other. Breathing and spacewalk limits come from NASA
   medical briefs (served with their sources by /api/atmosphere); the fire layer is the same
   model grid as the simulator, interpolated in the browser, so dragging the point costs nothing. */

type Grid = { axes: { var: string; values: number[] }[]; p: number[]; dist: number[]; inside: number; edge: number; tests: any[]; tested: Record<string, [number, number]> };
const X0 = 4.3, X1 = 15, Y0 = 0.15, Y1 = 0.7;            // psi, oxygen fraction
const NX = 132, NY = 84;                                    // raster of the fire layer
const MMHG = 0.1333224;
const HALO = { stroke: "var(--surface)", strokeWidth: 4, paintOrder: "stroke" } as const;      // keeps labels legible over the fire layer

function bracket(vals: number[], x: number) {
  let i = 0;
  while (i < vals.length - 2 && x > vals[i + 1]) i++;
  return [i, Math.min(1, Math.max(0, (x - vals[i]) / (vals[i + 1] - vals[i])))] as const;
}
function sample(g: Grid, arr: number[], a: number, b: number, c: number) {
  const [A, B, Cc] = g.axes.map((x) => x.values);
  const [i, ti] = bracket(A, a), [j, tj] = bracket(B, b), [k, tk] = bracket(Cc, c);
  const at = (di: number, dj: number, dk: number) => arr[((i + di) * B.length + (j + dj)) * Cc.length + (k + dk)];
  const l = (p: number, q: number, t: number) => p + (q - p) * t;
  return l(l(l(at(0, 0, 0), at(0, 0, 1), tk), l(at(0, 1, 0), at(0, 1, 1), tk), tj), l(l(at(1, 0, 0), at(1, 0, 1), tk), l(at(1, 1, 0), at(1, 1, 1), tk), tj), ti);
}
const hm = (min: number) => (min < 1 ? "none" : min < 60 ? `${Math.round(min)} min` : `${Math.floor(min / 60)} h ${String(Math.round(min % 60)).padStart(2, "0")} min`);

export default function TradePage() {
  const meta = useMeta();
  const openProv = useUI((s) => s.openProv);
  const [atm, setAtm] = useState<any>(null);
  const [items, setItems] = useState<any>(null);
  const [sel, setSel] = useState("droplet:n-heptane");
  const [grid, setGrid] = useState<Grid | null>(null);
  const [pt, setPt] = useState({ psi: 8.2, o2: 0.34 });
  const [ref, size] = useSize<HTMLDivElement>();
  const canvas = useRef<HTMLCanvasElement>(null);
  const [mode, ...rest] = sel.split(":");
  const item = rest.join(":");
  const third = mode === "gas" ? 1 : 3;                     // 1 mg/s of gas to the burner, or a 3 mm droplet

  useEffect(() => { get("/atmosphere").then(setAtm); get("/lab/items").then(setItems); }, []);
  useEffect(() => { setGrid(null); get(`/lab/grid?mode=${mode}&item=${encodeURIComponent(item)}&gravity=0&diluent=N2`).then(setGrid).catch(() => {}); }, [mode, item]);

  const C = atm?.constants;
  const phys = useMemo(() => {
    if (!C) return null;
    const pio2 = (psi: number, o2: number) => ((psi * PSI) / MMHG - C.water_vapour_mmhg) * o2;
    const pre = (psi: number, o2: number) => {
      const r0 = (psi * (1 - o2)) / C.suit_psi;
      return { r0, min: r0 <= C.r_accept ? 0 : (C.half_life_min / Math.LN2) * Math.log(r0 / C.r_accept) };
    };
    return { pio2, pre };
  }, [C]);
  const fire = (psi: number, o2: number) => {
    const p = sample(grid!, grid!.p, o2, psi * PSI, third), d = sample(grid!, grid!.dist, o2, psi * PSI, third);
    const [oLo, oHi] = grid!.tested.o2_frac, [pLo, pHi] = grid!.tested.pressure_kpa;
    const inRange = o2 >= oLo - 0.01 && o2 <= oHi + 0.01 && psi * PSI >= pLo - 3 && psi * PSI <= pHi + 3;
    return { p, known: d <= grid!.edge && inRange, inside: d <= grid!.inside && inRange };
  };

  // fire layer raster + the share of "liveable" atmospheres that still burn
  const summary = useMemo(() => {
    if (!grid || !phys || !canvas.current) return null;
    const cv = canvas.current, ctx = cv.getContext("2d")!;
    cv.width = NX; cv.height = NY;
    const img = ctx.createImageData(NX, NY);
    let ok = 0, burn = 0, out = 0, unknown = 0;
    for (let iy = 0; iy < NY; iy++) for (let ix = 0; ix < NX; ix++) {
      const psi = X0 + ((ix + 0.5) / NX) * (X1 - X0), o2 = Y1 - ((iy + 0.5) / NY) * (Y1 - Y0);
      const f = fire(psi, o2), k = (iy * NX + ix) * 4;
      if (f.known) {
        const a = 0.16 + Math.abs(f.p - 0.5) * 1.1;
        const c = f.p >= 0.5 ? [255, 154, 61] : [90, 169, 255];
        img.data[k] = c[0]; img.data[k + 1] = c[1]; img.data[k + 2] = c[2]; img.data[k + 3] = Math.round(255 * Math.min(0.72, a));
      } else if ((ix + iy) % 6 < 1) { img.data[k] = img.data[k + 1] = img.data[k + 2] = 140; img.data[k + 3] = 46; }   // hatch: no data
      if (phys.pio2(psi, o2) >= C.pio2_floor_mmhg && phys.pre(psi, o2).min <= 60) {
        ok++;
        if (!f.known) unknown++; else if (f.p >= 0.5) burn++; else out++;
      }
    }
    ctx.putImageData(img, 0, 0);
    return { ok, burn, out, unknown };
  }, [grid, phys, C, third]); // eslint-disable-line react-hooks/exhaustive-deps

  const W = size.w, H = Math.max(420, size.h), m = { l: 64, r: 18, t: 14, b: 50 };
  const sx = (psi: number) => m.l + ((psi - X0) / (X1 - X0)) * (W - m.l - m.r);
  const sy = (o2: number) => m.t + ((Y1 - o2) / (Y1 - Y0)) * (H - m.t - m.b);
  const curve = (f: (psi: number) => number) => {
    const pts: string[] = [];
    for (let i = 0; i <= 80; i++) { const psi = X0 + (i / 80) * (X1 - X0), o2 = f(psi); if (o2 >= Y0 - 0.02 && o2 <= Y1 + 0.02) pts.push(`${sx(psi).toFixed(1)},${sy(Math.min(Y1, Math.max(Y0, o2))).toFixed(1)}`); }
    return pts.join(" ");
  };
  const o2ForPio2 = (target: number) => (psi: number) => target / ((psi * PSI) / MMHG - (C?.water_vapour_mmhg ?? 47));
  const o2ForPre = (min: number) => (psi: number) => 1 - (C.suit_psi * C.r_accept * Math.exp((Math.LN2 * min) / C.half_life_min)) / psi;
  const move = (e: React.PointerEvent) => {
    if (e.type === "pointermove" && !(e.buttons & 1)) return;
    const r = e.currentTarget.getBoundingClientRect();
    const psi = X0 + ((e.clientX - r.left - m.l) / (W - m.l - m.r)) * (X1 - X0), o2 = Y1 - ((e.clientY - r.top - m.t) / (H - m.t - m.b)) * (Y1 - Y0);
    setPt({ psi: Math.min(X1, Math.max(X0, Math.round(psi * 10) / 10)), o2: Math.min(Y1, Math.max(Y0, Math.round(o2 * 200) / 200)) });
  };

  const now = useMemo(() => {
    if (!grid || !phys) return null;
    const pio2 = phys.pio2(pt.psi, pt.o2), pre = phys.pre(pt.psi, pt.o2), f = fire(pt.psi, pt.o2);
    const iss = phys.pre(14.7, 0.21).min;
    let best: any = null, bd = Infinity;
    for (const t of grid.tests) { const d = Math.hypot((t.o2_frac - pt.o2) / 0.2, (t.pressure_kpa - pt.psi * PSI) / 60); if (d < bd) { bd = d; best = t; } }
    const breath = pio2 < C.pio2_floor_mmhg ? "too little oxygen to breathe safely" : pio2 < C.pio2_normal_mmhg ? "breathable, mildly low on oxygen" : "breathable";
    const conf = !f.known ? "none" : !f.inside ? "low" : Math.abs(f.p - 0.5) > 0.35 ? "high" : Math.abs(f.p - 0.5) > 0.15 ? "moderate" : "low";
    return { pio2, pre, f, iss, best, breath, conf };
  }, [grid, phys, pt, C, third]); // eslint-disable-line react-hooks/exhaustive-deps

  const demoItem = mode === "gas" ? meta?.datasets?.cfig_normal?.demo : meta?.datasets?.flex?.demo;
  const what = mode === "gas" ? `${item} gas flames` : `${item} droplets`;
  const tone = !now ? "var(--text)" : !now.f.known ? "var(--nodata)" : now.f.p >= 0.5 ? "var(--flame)" : "var(--ext)";

  return (
    <div className="flex h-full min-h-[680px]" data-ready={now && summary ? "trade" : undefined}>
      <section className="flex min-w-0 flex-1 flex-col px-8 pb-5 pt-6">
        <h1 className="title">What air should the crew breathe?</h1>
        <p className="lead mt-2 min-h-[84px] text-ink" aria-live="polite" data-trade-sentence>
          {now && (<>
            At <span className="mono">{pt.psi.toFixed(1)}</span> psi and <span className="mono">{(pt.o2 * 100).toFixed(0)}</span>% oxygen the cabin is {now.breath}, a spacewalk needs {now.pre.min < 1 ? "no pre-breathe" : `about ${hm(now.pre.min)} of pre-breathe`}
            {now.iss - now.pre.min >= 1 ? ` (${hm(now.iss - now.pre.min)} less than on the ISS)` : ""}, and{" "}
            {now.f.known
              ? <>{what} are predicted to <span className="font-semibold" style={{ color: tone }}>{now.f.p >= 0.5 ? "keep burning" : "go out"}</span> (confidence: {now.conf}).</>
              : <span style={{ color: "var(--warn)" }}>no real test is close enough to say whether {what} burn.</span>}
          </>)}
        </p>

        <div ref={ref} className="relative mt-3 min-h-0 flex-1 select-none overflow-hidden rounded-md" style={{ border: "1px solid var(--line)", background: "var(--surface)", touchAction: "none", cursor: "crosshair" }}
          onPointerDown={move} onPointerMove={move} role="application" aria-label="Map of cabin pressure against oxygen. Click or drag to choose an atmosphere.">
          <canvas ref={canvas} className="absolute" style={{ left: m.l, top: m.t, width: Math.max(0, W - m.l - m.r), height: Math.max(0, H - m.t - m.b), imageRendering: "auto" }} aria-hidden />
          {W > 0 && C && (
            <svg width={W} height={H} className="absolute inset-0">
              {/* axes */}
              {[5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15].map((p) => (<g key={p}><line x1={sx(p)} x2={sx(p)} y1={H - m.b} y2={H - m.b + 5} stroke="var(--line-strong)" /><text x={sx(p)} y={H - m.b + 21} textAnchor="middle" fontSize={13} fill="var(--text-3)">{p}</text></g>))}
              {[0.2, 0.3, 0.4, 0.5, 0.6, 0.7].map((o) => (<g key={o}><line x1={m.l - 5} x2={m.l} y1={sy(o)} y2={sy(o)} stroke="var(--line-strong)" /><text x={m.l - 10} y={sy(o) + 4} textAnchor="end" fontSize={13} fill="var(--text-3)">{o * 100}%</text></g>))}
              <text x={(m.l + W - m.r) / 2} y={H - 8} textAnchor="middle" fontSize={13} fill="var(--text-3)">Cabin pressure (psi)</text>
              <text transform={`translate(17 ${(m.t + H - m.b) / 2}) rotate(-90)`} textAnchor="middle" fontSize={13} fill="var(--text-3)">Oxygen in the cabin air</text>

              {/* breathing: below the floor nobody can live */}
              <polygon points={`${sx(X0)},${H - m.b} ${curve(o2ForPio2(C.pio2_floor_mmhg))} ${sx(X1)},${H - m.b}`} fill="var(--bg)" fillOpacity={0.86} />
              <polyline points={curve(o2ForPio2(C.pio2_floor_mmhg))} fill="none" stroke="var(--text)" strokeWidth={2} />
              <text x={sx(4.6)} y={sy(0.185)} fontSize={14} fontWeight={600} fill="var(--text-2)" {...HALO}>Too little oxygen to breathe</text>
              <polyline points={curve(o2ForPio2(C.pio2_normal_mmhg))} fill="none" stroke="var(--text-3)" strokeWidth={1} strokeDasharray="2 5" />
              <text x={sx(6.25)} y={sy(o2ForPio2(C.pio2_normal_mmhg)(6.25)) - 6} fontSize={13} fill="var(--text-3)" {...HALO}>sea-level oxygen</text>

              {/* spacewalks: pre-breathe needed before going outside */}
              {[0, 60, 120, 240].map((min) => {
                const y = o2ForPre(min)(14.9);
                return (<g key={min}>
                  <polyline points={curve(o2ForPre(min))} fill="none" stroke="var(--unc)" strokeWidth={1.5} strokeDasharray="7 5" />
                  <text x={sx(14.9)} y={sy(y) - 7} textAnchor="end" fontSize={13} fill="var(--unc)" {...HALO}>{min === 0 ? "no pre-breathe below this line" : `${min / 60} h pre-breathe`}</text>
                </g>);
              })}

              {/* fire: NASA's design line, and the real tests */}
              <line x1={m.l} x2={W - m.r} y1={sy(C.o2_flammability_line)} y2={sy(C.o2_flammability_line)} stroke="var(--flame)" strokeWidth={1.5} strokeDasharray="3 4" />
              <text x={m.l + 10} y={sy(C.o2_flammability_line) - 7} fontSize={13} fill="var(--flame)" {...HALO}>NASA materials flammability line: 30% oxygen</text>
              {(grid?.tests ?? []).filter((t) => t.pressure_kpa / PSI >= X0 && t.pressure_kpa / PSI <= X1 && t.o2_frac >= Y0 && t.o2_frac <= Y1).map((t) => (
                <circle key={t.test_id} cx={sx(t.pressure_kpa / PSI)} cy={sy(t.o2_frac)} r={3.5} fill={t.burned == null ? "var(--nodata)" : t.burned ? "var(--flame)" : "var(--ext)"} stroke="var(--bg)" strokeWidth={1} />
              ))}

              {/* reference atmospheres */}
              {atm.references.map((r: any) => (
                <g key={r.id} style={{ cursor: "pointer" }} onPointerDown={(e) => { e.stopPropagation(); setPt({ psi: r.pressure_psi, o2: r.o2_frac }); }} data-ref={r.id}>
                  <rect x={sx(r.pressure_psi) - 6} y={sy(r.o2_frac) - 6} width={12} height={12} transform={`rotate(45 ${sx(r.pressure_psi)} ${sy(r.o2_frac)})`} fill="var(--bg)" stroke="var(--text)" strokeWidth={2} />
                  <text x={sx(r.pressure_psi) + (r.id === "iss" ? -14 : 14)} y={sy(r.o2_frac) + (r.id === "exploration" ? -12 : r.id === "iss" ? 20 : 5)} textAnchor={r.id === "iss" ? "end" : "start"} fontSize={14} fontWeight={600} fill="var(--text)" stroke="var(--bg)" strokeWidth={4} paintOrder="stroke">{r.label}</text>
                </g>
              ))}

              {/* the chosen atmosphere */}
              <g pointerEvents="none">
                <line x1={sx(pt.psi)} x2={sx(pt.psi)} y1={m.t} y2={H - m.b} stroke="var(--text)" strokeOpacity={0.25} />
                <line x1={m.l} x2={W - m.r} y1={sy(pt.o2)} y2={sy(pt.o2)} stroke="var(--text)" strokeOpacity={0.25} />
                <circle cx={sx(pt.psi)} cy={sy(pt.o2)} r={11} fill="none" stroke="var(--text)" strokeWidth={2.5} />
                <circle cx={sx(pt.psi)} cy={sy(pt.o2)} r={3.5} fill="var(--text)" />
              </g>
            </svg>
          )}
        </div>
        <p className="mt-2.5 flex flex-wrap items-center gap-x-5 gap-y-1 text-sm text-ink-2">
          <span className="flex items-center gap-2"><span className="h-3 w-5 rounded-sm" style={{ background: "var(--flame)", opacity: 0.6 }} />predicted to keep burning</span>
          <span className="flex items-center gap-2"><span className="h-3 w-5 rounded-sm" style={{ background: "var(--ext)", opacity: 0.6 }} />predicted to go out</span>
          <span className="flex items-center gap-2"><span className="h-3 w-5 rounded-sm" style={{ background: "repeating-linear-gradient(135deg, var(--nodata) 0 1px, transparent 1px 5px)" }} />no test data nearby</span>
          <span className="flex items-center gap-2"><span className="h-2.5 w-2.5 rounded-full bg-ink-3" />real tests</span>
          <span className="text-ink-3">Click or drag on the map.</span>
        </p>
      </section>

      <aside className="rule-l flex w-[420px] shrink-0 flex-col gap-5 overflow-y-auto px-7 py-6" style={{ background: "var(--surface)" }} aria-label="Reading of the chosen atmosphere">
        <div>
          <label htmlFor="trade-item" className="text-sm text-ink-3">Fire layer: what is burning</label>
          <select id="trade-item" className="mt-1.5 h-10 w-full" value={sel} onChange={(e) => setSel(e.target.value)} data-trade-item>
            <optgroup label="Fuel droplets: real NASA data (FLEX)">{(items?.droplet ?? []).map((x: string) => <option key={x} value={`droplet:${x}`}>{x}</option>)}</optgroup>
            <optgroup label="Gas flames: real NASA data (CFI-G)">{(items?.gas ?? []).map((x: string) => <option key={x} value={`gas:${x}`}>{x}</option>)}</optgroup>
          </select>
          <p className="mt-1.5 text-xs" style={{ color: demoItem ? "var(--warn)" : "var(--text-3)" }}>
            {demoItem ? "Synthetic demo data: an example of the method, not a NASA result." : mode === "gas" ? "Real CFI-G tests from NASA PSI." : "Real FLEX tests from NASA PSI."}{" "}
            {mode === "gas" ? "Fuel flow fixed at 1 mg/s." : "Droplet fixed at 3 mm, in nitrogen."} Solid materials are not on this map: their tables record no pressure.
          </p>
        </div>

        {now && (<>
          <div className="card p-4" data-card="breathing">
            <p className="text-sm text-ink-3">Breathing</p>
            <p className="mt-0.5 text-xl font-semibold text-ink">{now.breath[0].toUpperCase() + now.breath.slice(1)}</p>
            <p className="mt-1 text-sm text-ink-2">Oxygen reaching the lungs: <span className="mono text-ink">{now.pio2.toFixed(0)} mmHg</span>. Sea level is {C.pio2_normal_mmhg}; NASA's floor for exploration is {C.pio2_floor_mmhg}.</p>
          </div>
          <div className="card p-4" data-card="spacewalk">
            <p className="text-sm text-ink-3">Before each spacewalk</p>
            <p className="mt-0.5 text-xl font-semibold text-ink">{now.pre.min < 1 ? "No pre-breathe needed" : `About ${hm(now.pre.min)} breathing pure oxygen`}</p>
            <p className="mt-1 text-sm text-ink-2">Estimate. Nitrogen-to-suit ratio <span className="mono text-ink">{now.pre.r0.toFixed(2)}</span>; {C.r_accept} is the accepted value for a {C.suit_psi} psi suit. The ISS needs about {hm(now.iss)}.</p>
          </div>
          <div className="card p-4" data-card="fire" style={{ borderLeft: `3px solid ${tone}` }}>
            <p className="text-sm text-ink-3">Fire: {what}</p>
            <p className="mt-0.5 text-xl font-semibold" style={{ color: tone }}>{!now.f.known ? "No data here" : now.f.p >= 0.5 ? "Predicted to keep burning" : "Predicted to go out"}</p>
            <p className="mt-1 text-sm text-ink-2">
              {now.f.known && <><span className="mono text-ink">{Math.round(now.f.p * 100)}%</span> chance of sustained burning, confidence {now.conf}. </>}
              {now.best && <>Nearest real test: <button className="mono underline decoration-dotted underline-offset-4 hover:text-ink" onClick={() => openProv({ testId: now.best.test_id, label: now.best.test_id })}>{now.best.test_id}</button> at {(now.best.pressure_kpa / PSI).toFixed(1)} psi, {(now.best.o2_frac * 100).toFixed(0)}% oxygen.</>}
              {pt.o2 > C.o2_flammability_line && <span style={{ color: "var(--flame)" }}> Above NASA's 30% materials line.</span>}
            </p>
          </div>
        </>)}

        {summary && summary.ok > 0 && (
          <div data-trade-summary>
            <p className="text-sm text-ink-3">Across every atmosphere on this map that is breathable and needs under an hour of pre-breathe</p>
            <div className="mt-2 flex h-3.5 overflow-hidden rounded-full">
              <span style={{ width: `${(summary.burn / summary.ok) * 100}%`, background: "var(--flame)" }} />
              <span style={{ width: `${(summary.out / summary.ok) * 100}%`, background: "var(--ext)" }} />
              <span style={{ width: `${(summary.unknown / summary.ok) * 100}%`, background: "var(--nodata)" }} />
            </div>
            <p className="mt-2 text-sm text-ink">
              <span className="mono">{Math.round((summary.burn / summary.ok) * 100)}%</span> keep {what} burning, <span className="mono">{Math.round((summary.out / summary.ok) * 100)}%</span> put them out, and for <span className="mono">{Math.round((summary.unknown / summary.ok) * 100)}%</span> there is no test data near enough to say.
            </p>
          </div>
        )}

        {atm && (
          <details className="rule-t pt-4 text-sm text-ink-2">
            <summary className="cursor-pointer text-ink">Where these limits come from</summary>
            <ul className="mt-2 space-y-1.5">{atm.sources.map((s: any) => <li key={s.id}><a className="underline decoration-dotted underline-offset-4 hover:text-ink" href={s.url} target="_blank" rel="noreferrer">{s.title}</a></li>)}</ul>
            <ul className="mt-3 space-y-1.5 text-ink-3">{atm.caveats.map((c: string, i: number) => <li key={i}>{c}</li>)}</ul>
          </details>
        )}
        <div className="mt-auto flex flex-wrap gap-2.5">
          <Link className="btn" href={`/lab?mode=${mode}&item=${encodeURIComponent(item)}`}>Open in the simulator</Link>
          <Link className="btn" href="/answer?topic=untested">What was never tested</Link>
        </div>
      </aside>
    </div>
  );
}
