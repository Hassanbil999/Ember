"use client";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useEffect, useMemo, useRef, useState } from "react";
import { get } from "@/lib/api";
import { gravityLabel, PSI } from "@/lib/format";
import { useMeta } from "@/lib/meta";
import { useUI } from "@/lib/store";
import FlameScene, { SceneOverride } from "@/components/lab/FlameScene";
import { useFlameSound } from "@/components/lab/useFlameSound";

/* Simulate: one hero flame, three sliders, one sentence. The model grid is fetched once per
   fuel; every slider move is answered in the browser by interpolating it (immediate feedback).
   Both modes run on real NASA PSI tests: gas flames on a spherical burner (CFI-G) and fuel droplets
   (FLEX). The same scene can replay a real droplet test: the droplet shrinks at its measured burning
   rate and the flame ends the way, and when, the record says it did. Sound is optional and off by default. */

type Mode = "gas" | "droplet";
type Grid = { axes: { var: string; values: number[] }[]; p: number[]; rate: number[]; dist: number[]; inside: number; edge: number;
  tested: Record<string, [number, number]>; tests: any[]; rate_label: string | null; rate_unit: string | null; gravity_is_feature: boolean;
  source: string; demo: boolean; cv: { accuracy: number; baseline: number; auc: number | null; scheme: string; rows: number } };
const GRAV = [{ v: 0, l: "Microgravity" }, { v: 0.165, l: "Moon" }, { v: 0.38, l: "Mars" }, { v: 1, l: "Earth" }];
const THIRD: Record<Mode, { var: string; label: string; unit: string; min: number; max: number; step: number; digits: number }> = {
  gas: { var: "fuel_flow_mg_s", label: "Fuel flow", unit: "mg/s", min: 0.1, max: 3.3, step: 0.05, digits: 2 },
  droplet: { var: "d0_mm", label: "Droplet size", unit: "mm", min: 1, max: 6, step: 0.1, digits: 1 },
};
const BURNER = 0.45;      // the CFI-G spherical burner, drawn like a droplet of fixed size

function bracket(vals: number[], x: number) {
  let i = 0;
  while (i < vals.length - 2 && x > vals[i + 1]) i++;
  return [i, Math.min(1, Math.max(0, (x - vals[i]) / (vals[i + 1] - vals[i])))] as const;
}
/** trilinear interpolation of a flat [o2][pressure][third] array */
function sample(g: Grid, arr: number[], a: number, b: number, c: number) {
  const [A, B, C] = g.axes.map((x) => x.values);
  const [i, ti] = bracket(A, a), [j, tj] = bracket(B, b), [k, tk] = bracket(C, c);
  const at = (di: number, dj: number, dk: number) => arr[((i + di) * B.length + (j + dj)) * C.length + (k + dk)];
  const l = (p: number, q: number, t: number) => p + (q - p) * t;
  return l(l(l(at(0, 0, 0), at(0, 0, 1), tk), l(at(0, 1, 0), at(0, 1, 1), tk), tj), l(l(at(1, 0, 0), at(1, 0, 1), tk), l(at(1, 1, 0), at(1, 1, 1), tk), tj), ti);
}

function Slider({ label, value, text, min, max, step, tested, onChange, id }: {
  label: string; value: number; text: React.ReactNode; min: number; max: number; step: number; tested?: [number, number]; onChange: (v: number) => void; id: string;
}) {
  const pos = (v: number) => `${((Math.min(max, Math.max(min, v)) - min) / (max - min)) * 100}%`;
  return (
    <div>
      <div className="flex items-baseline justify-between gap-3">
        <label htmlFor={id} className="text-base font-medium text-ink">{label}</label>
        <span className="text-right text-ink">{text}</span>
      </div>
      <input id={id} type="range" min={min} max={max} step={step} value={value} onChange={(e) => onChange(Number(e.target.value))} data-slider={id} />
      {/* where real tests exist on this axis: the slider says how far from data you are */}
      <div className="relative -mt-1 h-4" aria-hidden>
        <div className="absolute inset-x-0 top-1 h-px" style={{ background: "var(--line)" }} />
        {tested && <div className="absolute top-0.5 h-[3px] rounded" style={{ left: pos(tested[0]), right: `calc(100% - ${pos(tested[1])})`, background: "var(--text-3)" }} />}
      </div>
    </div>
  );
}

function Inner() {
  const sp = useSearchParams();
  const meta = useMeta();
  const openProv = useUI((s) => s.openProv);
  const [items, setItems] = useState<any>(null);
  const [mode, setMode] = useState<Mode>(sp.get("mode") === "droplet" ? "droplet" : "gas");
  const [item, setItem] = useState<string | null>(sp.get("item") ?? (sp.get("mode") === "droplet" ? null : "30% butane"));
  const [o2, setO2] = useState(0.21);
  const [pk, setPk] = useState(101.3);
  const [third, setThird] = useState(sp.get("mode") === "droplet" ? 3 : 1);
  const [gravity, setGravity] = useState(0);
  const [diluent, setDiluent] = useState("N2");
  const [preset, setPreset] = useState<string | null>(null);
  const [grid, setGrid] = useState<Grid | null>(null);
  const [sound, setSound] = useState(false);
  const [atm, setAtm] = useState<any>(null);
  const [rp, setRp] = useState<{ id: string; t: number; d: number; dur: number; speed: number; end: string; dEnd: number; done: boolean } | null>(null);
  const override = useRef<SceneOverride | null>(null);
  const stopReplay = useRef<() => void>(() => {});

  useEffect(() => { get("/lab/items").then(setItems); get("/atmosphere").then(setAtm).catch(() => {}); }, []);
  useEffect(() => () => stopReplay.current(), []);
  useEffect(() => {
    if (!items) return;
    const list: string[] = items[mode];
    if (!item || !list.includes(item)) setItem(list[0]);
    const t = THIRD[mode];
    if (third > t.max || third < t.min) setThird(mode === "droplet" ? 3 : 1);
  }, [items, mode]); // eslint-disable-line react-hooks/exhaustive-deps

  const presets: any[] = meta?.presets.presets ?? [];
  const apply = (p: any) => { setPreset(p.id); setO2(p.o2_frac); setPk(p.pressure_kpa); setGravity(p.gravity_g); };
  useEffect(() => {
    const p = presets.find((x) => x.id === sp.get("preset"));
    if (p) apply(p);
  }, [meta]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (!item || (items && !items[mode].includes(item))) return;      // do not wait for the item list: start with the default
    // every real test was in microgravity and no model takes gravity as an input: one grid per fuel
    get(`/lab/grid?mode=${mode}&item=${encodeURIComponent(item)}&gravity=0&diluent=${diluent}`).then(setGrid).catch(() => {});
  }, [mode, item, diluent, items]);

  const th = THIRD[mode];
  const maxRate = useMemo(() => (grid ? grid.rate.reduce((a, b) => Math.max(a, b), 0) || 1 : 1), [grid]);
  const out = useMemo(() => {
    if (!grid || grid.axes[2].var !== th.var) return null;
    const p = sample(grid, grid.p, o2, pk, third), rate = sample(grid, grid.rate, o2, pk, third), dist = sample(grid, grid.dist, o2, pk, third);
    const partial = gravity > 0.02 && gravity < 0.95;
    const offRange = Object.entries({ o2_frac: o2, pressure_kpa: pk, [th.var]: third }).filter(([k, v]) => grid.tested[k] && (v < grid.tested[k][0] || v > grid.tested[k][1])).map(([k]) => k);
    const status = dist > grid.edge ? "outside" : partial ? "untested" : dist > grid.inside || offRange.length ? "edge" : "inside";
    const conf = status === "outside" ? "none" : status !== "inside" ? "low" : Math.abs(p - 0.5) > 0.35 ? "high" : Math.abs(p - 0.5) > 0.15 ? "moderate" : "low";
    // nearest real test of this material, in units of each axis' tested width
    const span = (k: string) => (grid.tested[k] ? grid.tested[k][1] - grid.tested[k][0] : 1) || 1;
    let best: any = null, bd = Infinity;
    for (const t of grid.tests) {
      const d = Math.hypot((t.o2_frac - o2) / span("o2_frac"), (t.pressure_kpa - pk) / span("pressure_kpa"), (t[th.var] - third) / span(th.var));
      if (d < bd) { bd = d; best = t; }
    }
    let away = "";
    if (best) {
      const parts = [
        { n: Math.abs(best.o2_frac - o2) / span("o2_frac"), s: `${(Math.abs(best.o2_frac - o2) * 100).toFixed(1)}% O₂` },
        { n: Math.abs(best.pressure_kpa - pk) / span("pressure_kpa"), s: `${(Math.abs(best.pressure_kpa - pk) / PSI).toFixed(1)} psi` },
        { n: Math.abs(best[th.var] - third) / span(th.var), s: `${Math.abs(best[th.var] - third).toFixed(1)} ${th.unit}` },
      ].filter((x) => x.n > 0.02).sort((a, b) => b.n - a.n).slice(0, 2);
      away = parts.length ? parts.map((x) => x.s).join(" and ") + " away" : "at the same conditions";
    }
    // heat drives the drawing only: the droplet's predicted burning rate, or for a gas flame its fuel supply
    const heat = grid.rate_label ? Math.min(1, rate / (maxRate * 0.7)) : Math.min(1, (third - th.min) / (th.max - th.min) + 0.15);
    return { p, rate, status, conf, best, away, partial, heat };
  }, [grid, o2, pk, third, gravity, th, maxRate]);

  // breathing: the oxygen that reaches the lungs at this pressure and oxygen level (limits from NASA OCHMO-TB-003)
  const C = atm?.constants;
  const pio2 = C ? (pk / 0.1333224 - C.water_vapour_mmhg) * o2 : null;
  const breath = pio2 == null ? "" : pio2 < C.pio2_floor_mmhg ? "too little oxygen for a crew to breathe" : pio2 < C.pio2_normal_mmhg ? "breathable, mildly low on oxygen" : "breathable";
  const strain = pio2 == null ? 0 : Math.min(1, Math.max(0, (C.pio2_normal_mmhg - pio2) / 45));
  const dropOf = (mm: number) => Math.min(1, Math.max(0, (mm - 0.4) / 5.6));

  // replay a real test in the scene: d² = d0² − K·t, ending at the measured extinction diameter
  const replay = async (id: string) => {
    stopReplay.current();
    const rows = await get(`/tests?include_excluded=true&ids=${encodeURIComponent(id)}`);
    const r = rows[0];
    if (!r || r.d0_mm == null || r.burn_rate_k_mm2_s == null) return;
    const d0 = r.d0_mm, K = r.burn_rate_k_mm2_s, end = r.test_end ?? (r.burned ? "Completion" : "Extinction");
    const dEnd = r.extinction_d_mm ?? Math.sqrt(Math.max(0, d0 * d0 - K * (r.burn_time_s ?? (d0 * d0) / K)));
    const dur = r.burn_time_s ?? (d0 * d0 - dEnd * dEnd) / K, speed = Math.max(1, dur / 12);
    setPreset(null); setO2(r.o2_frac); setPk(r.pressure_kpa); setThird(Math.min(6, Math.max(1, d0)));
    let raf = 0, t0 = 0, tick = 0, alive = true;
    const heat = Math.min(1, K / 0.9);
    const step = (now: number) => {
      if (!alive) return;
      if (!t0) t0 = now;
      const t = ((now - t0) / 1000) * speed, burning = t < dur;
      const d = burning ? Math.sqrt(Math.max(dEnd * dEnd, d0 * d0 - K * t)) : end === "Extinction" ? dEnd : 0;
      override.current = { p: burning ? 1 : 0, heat, known: true, flow: 0, gravity: 0, o2: r.o2_frac, drop: dropOf(d) };
      if (tick++ % 5 === 0 || !burning) setRp({ id, t: Math.min(t, dur), d: burning ? d : dEnd, dur, speed, end, dEnd, done: !burning });
      if (t < dur + 3.2 * speed) raf = requestAnimationFrame(step); else stopReplay.current();
    };
    stopReplay.current = () => { alive = false; cancelAnimationFrame(raf); override.current = null; setRp(null); stopReplay.current = () => {}; };
    raf = requestAnimationFrame(step);
  };

  const conds = `${(o2 * 100).toFixed(0)}% O₂ and ${(pk / PSI).toFixed(1)} psi${mode === "gas" ? ` with ${third.toFixed(2)} mg/s of fuel` : `, ${third.toFixed(1)} mm droplet`}`;
  const what = mode === "gas" ? `a ${item ?? ""} gas flame` : `a ${item ?? ""} droplet`;
  const burns = !!out && out.p >= 0.5;
  const tone = !out || out.status === "outside" ? "var(--nodata)" : burns ? "var(--flame)" : "var(--ext)";
  const set = <T,>(fn: (v: T) => void) => (v: T) => { stopReplay.current(); setPreset(null); fn(v); };
  const live = out && out.status !== "outside" ? Math.min(1, Math.max(0, (out.p - 0.2) / 0.45)) : 0;
  useFlameSound(sound, { life: rp ? (rp.done ? 0 : 1) : live, heat: out?.heat ?? 0, flow: 0, strain });

  return (
    <div className="flex h-full min-h-[640px]" data-ready={out ? "lab" : undefined}>
      <section className="relative flex min-w-0 flex-1 flex-col px-8 pb-6 pt-6">
        <div className="flex flex-wrap items-center gap-2.5" role="group" aria-label="Places">
          <span className="mr-1 text-sm text-ink-3">Try a place</span>
          {presets.map((p) => <button key={p.id} className="chip" aria-pressed={preset === p.id} data-preset={p.id} onClick={() => apply(p)}>{p.label}</button>)}
        </div>

        {/* the scene is a window into a dark cabin in both themes */}
        <div data-theme="void" className="relative mt-4 min-h-0 flex-1 overflow-hidden rounded-md" style={{ background: "#05070C", border: "1px solid var(--line)" }}>
          {out && <FlameScene override={override} state={{ mode: "droplet", p: out.p, heat: out.heat, o2, flow: 0, gravity, known: out.status !== "outside", drop: mode === "gas" ? BURNER : dropOf(third) }} />}
          <button className="btn absolute right-4 top-4 h-9" style={{ background: "rgba(5,7,12,.6)" }} aria-pressed={sound} onClick={() => setSound(!sound)} data-sound>
            <svg width="16" height="16" viewBox="0 0 16 16" aria-hidden><path d="M2 6h2.5L8 3v10L4.5 10H2z" fill="currentColor" />{sound ? <path d="M10.5 5.5a3.5 3.5 0 010 5M12.3 3.6a6 6 0 010 8.8" fill="none" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" /> : <path d="M10.5 6l4 4m0-4l-4 4" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" />}</svg>
            {sound ? "Sound on" : "Sound off"}
          </button>
          {rp && (
            <div className="absolute left-6 top-5" data-replay-readout>
              <p className="text-sm text-ink-2">Real test, replayed from its record{rp.speed > 1.05 ? `, ${rp.speed.toFixed(1)}× speed` : ""}</p>
              <p className="mono mt-1 text-[40px] leading-none text-ink">{rp.id}</p>
              <p className="mt-2 text-base text-ink-2"><span className="mono text-ink">{rp.t.toFixed(1)} s</span> after ignition · droplet <span className="mono text-ink">{rp.d.toFixed(2)} mm</span></p>
              {rp.done && <p className="rise mt-2 max-w-[44ch] text-base" style={{ color: rp.end === "Extinction" ? "var(--ext)" : "var(--flame)" }}>
                {rp.end === "Extinction" ? `The flame went out with ${rp.dEnd.toFixed(2)} mm of fuel left, ${rp.dur.toFixed(1)} s after ignition.` : rp.end === "Completion" ? `Burned to completion in ${rp.dur.toFixed(1)} s.` : `The droplet broke apart ${rp.dur.toFixed(1)} s after ignition.`}</p>}
              <button className="btn mt-3 h-8" onClick={() => stopReplay.current()}>Back to the simulator</button>
            </div>
          )}
          {rp && <div className="pointer-events-none absolute inset-x-0 bottom-0 h-1" style={{ background: "var(--line)" }}><div className="h-full" style={{ width: `${(rp.t / rp.dur) * 100}%`, background: "var(--flame)" }} /></div>}
          {out && !rp && (
            <div className="pointer-events-none absolute left-6 top-5">
              <p className="text-[40px] font-semibold leading-none tracking-tight" style={{ color: tone }} data-verdict>
                {out.status === "outside" ? "No data here" : burns ? "Keeps burning" : "Goes out"}
              </p>
              {out.status !== "outside" && <p className="mt-2 text-base text-ink-2"><span className="mono text-ink">{Math.round(out.p * 100)}%</span> chance of sustained burning</p>}
            </div>
          )}
          <p className="pointer-events-none absolute bottom-4 left-6 right-6 flex flex-wrap items-end justify-between gap-2 text-sm text-ink-3">
            <span>{mode === "gas" ? `Spherical burner: ${item ?? ""}, ${third.toFixed(2)} mg/s` : `Droplet: ${item ?? ""}, ${third.toFixed(1)} mm`} · {gravityLabel(gravity)}{breath ? ` · Air: ${breath}` : ""}</span>
            <span>{rp ? "Illustration timed by the test's measurements, not footage" : "Illustration driven by the model, not footage"}</span>
          </p>
        </div>

        <p className="lead mt-4 min-h-[58px] text-ink" aria-live="polite" data-sentence>
          {out && (out.status === "outside" ? (
            <>At {conds}, there is no real test close enough to predict what {what} does. </>
          ) : (
            <>At {conds}, {what} is predicted to <span style={{ color: tone }} className="font-semibold">{burns ? "keep burning" : "go out"}</span> (confidence: {out.conf}). </>
          ))}
          {out?.best && (
            <span className="text-ink-2">Nearest real test: <button className="mono underline decoration-dotted underline-offset-4 hover:text-ink" onClick={() => openProv({ testId: out.best.test_id, label: out.best.test_id })}>{out.best.test_id}</button>, {out.away}; it {out.best.burned == null ? "has no recorded outcome" : out.best.burned ? "burned" : "went out"}.{mode === "droplet" && <> <button className="font-medium text-flame underline decoration-dotted underline-offset-4" data-replay onClick={() => replay(out.best.test_id)}>Watch it burn</button>.</>} </span>
          )}
          {out?.partial && <span style={{ color: "var(--warn)" }}>Nothing has ever been tested at {gravityLabel(gravity).split(" (")[0]}: this is bracketed between microgravity and Earth results.</span>}
        </p>
      </section>

      <aside className="rule-l flex w-[400px] shrink-0 flex-col gap-6 overflow-y-auto px-7 py-6" style={{ background: "var(--surface)" }} aria-label="Conditions">
        <div>
          <h1 className="title">Simulate</h1>
          <p className="mt-1 text-sm text-ink-2">Change the air. Watch the flame.</p>
        </div>
        <div>
          <label htmlFor="item" className="text-sm text-ink-3">What is burning</label>
          <select id="item" className="mt-1.5 h-10 w-full" value={`${mode}:${item ?? ""}`} data-item
            onChange={(e) => { const [m, ...r] = e.target.value.split(":"); setMode(m as Mode); setItem(r.join(":")); if (m !== mode) setGrid(null); }}>
            <optgroup label="Gas flames on a burner (CFI-G)">{(items?.gas ?? []).map((m: string) => <option key={m} value={`gas:${m}`}>{m}</option>)}</optgroup>
            <optgroup label="Fuel droplets (FLEX)">{(items?.droplet ?? []).map((m: string) => <option key={m} value={`droplet:${m}`}>{m}</option>)}</optgroup>
          </select>
          <p className="mt-1.5 text-xs text-ink-3">Real NASA tests. Solid materials have no simulator: their tables record no pressure. <Link className="underline decoration-dotted underline-offset-4 hover:text-ink" href="/answer?topic=moon-base">What is known about them</Link>.</p>
        </div>
        <Slider id="o2" label="Oxygen" value={o2} min={0.1} max={1} step={0.005} onChange={set(setO2)} tested={grid?.tested.o2_frac}
          text={<span className="mono text-xl">{(o2 * 100).toFixed(1)}<span className="text-sm text-ink-3"> %</span></span>} />
        <Slider id="pressure" label="Pressure" value={pk} min={20} max={320} step={0.5} onChange={set(setPk)} tested={grid?.tested.pressure_kpa}
          text={<><span className="mono text-xl">{(pk / PSI).toFixed(1)}<span className="text-sm text-ink-3"> psi</span></span><span className="mono ml-2 text-sm text-ink-3">{pk.toFixed(0)} kPa</span></>} />
        <Slider id="third" label={th.label} value={third} min={th.min} max={th.max} step={th.step} onChange={set(setThird)} tested={grid?.tested[th.var]}
          text={<span className="mono text-xl">{third.toFixed(th.digits)}<span className="text-sm text-ink-3"> {th.unit}</span></span>} />

        <p className="-mt-3 text-xs text-ink-3">The grey bar under each slider is the range covered by real tests.</p>
        <details>
          <summary className="cursor-pointer text-sm text-ink-2">More settings</summary>
          <div className="mt-3 space-y-4">
            <div>
              <p className="text-sm text-ink-3">Gravity</p>
              <div className="seg mt-1.5 w-full">{GRAV.map((g) => <button key={g.v} className="flex-1 px-2" aria-pressed={gravity === g.v} data-gravity={g.v} onClick={() => set(setGravity)(g.v)}>{g.l}</button>)}</div>
              {gravity > 0.02 && <p className="mt-1.5 text-xs" style={{ color: "var(--warn)" }}>All {mode === "gas" ? "gas-flame" : "droplet"} tests were in microgravity, so the gravity setting does not change this prediction.</p>}
            </div>
            {mode === "droplet" && (
              <div>
                <p className="text-sm text-ink-3">Rest of the atmosphere (nitrogen, or nitrogen mixed with)</p>
                <div className="seg mt-1.5 w-full">{(items?.diluents ?? []).map((d: string) => <button key={d} className="flex-1" aria-pressed={diluent === d} onClick={() => setDiluent(d)}>{({ N2: "Nitrogen", CO2: "30% CO₂", He: "30% helium" } as any)[d] ?? d}</button>)}</div>
              </div>
            )}
          </div>
        </details>

        {grid && out && (
          <div className="rule-t mt-auto pt-4 text-sm text-ink-2">
            {out.status !== "outside" && burns && grid.rate_label && <p>Predicted {grid.rate_label}: <span className="mono text-ink">{out.rate.toFixed(2)} {grid.rate_unit}</span></p>}
            <p className="mt-1.5">How far to trust this: the model is right <span className="mono text-ink">{Math.round(grid.cv.accuracy * 100)}%</span> of the time on test campaigns it has not seen{grid.cv.accuracy > grid.cv.baseline + 0.005
              ? <>, against <span className="mono text-ink">{Math.round(grid.cv.baseline * 100)}%</span> for always guessing the commonest outcome.</>
              : <>, which is <span style={{ color: "var(--warn)" }}>no better than always guessing the commonest outcome</span> (<span className="mono text-ink">{Math.round(grid.cv.baseline * 100)}%</span>){grid.cv.auc ? <>; it does rank risk better than chance (AUC <span className="mono text-ink">{grid.cv.auc.toFixed(2)}</span>, 0.5 is chance)</> : null}.</>} It learned from {grid.cv.rows} {grid.demo ? "synthetic demo" : grid.source} tests and knows no physics.</p>
            <p className="mt-2"><Link className="underline decoration-dotted underline-offset-4 hover:text-ink" href="/trade">See this against breathing and spacewalk limits</Link></p>
          </div>
        )}
      </aside>
    </div>
  );
}

export default function LabPage() {
  return <Suspense><Inner /></Suspense>;
}
