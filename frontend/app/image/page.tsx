"use client";
import { useSearchParams } from "next/navigation";
import { Suspense, useEffect, useRef, useState } from "react";
import { clearCache, download, get, post } from "@/lib/api";
import { svgString, svgToPng, useSize } from "@/lib/chart";
import { fmt, fmtVar } from "@/lib/format";
import { useUI } from "@/lib/store";
import AnnotatedFrame, { ALL_FEATURES, Feature } from "@/components/vision/AnnotatedFrame";
import { D2Chart } from "@/components/charts/More";

function Validation({ summary }: { summary: any }) {
  if (!summary) return null;
  const pts = summary.tests.flatMap((t: any) => t.validation.rows.map((r: any) => ({ ...r, test: t.test_id })));
  const k = pts.filter((p: any) => p.variable === "burn_rate_k_mm2_s");
  const lo = Math.min(...k.map((p: any) => Math.min(p.extracted, p.published))) * 0.92, hi = Math.max(...k.map((p: any) => Math.max(p.extracted, p.published))) * 1.05;
  const s = (v: number) => 8 + ((v - lo) / (hi - lo)) * 184;
  return (
    <div>
      <p className="eyebrow">Validation vs published values</p>
      <svg width={200} height={200} className="mt-2" role="img" aria-label="Extracted burning-rate constant against published value">
        <rect x={8} y={8} width={184} height={184} fill="none" stroke="var(--line)" />
        <line x1={s(lo)} y1={200 - s(lo)} x2={s(hi)} y2={200 - s(hi)} stroke="var(--text-3)" strokeDasharray="3 3" />
        {k.map((p: any) => <circle key={p.test} cx={s(p.published)} cy={200 - s(p.extracted)} r={3.5} fill={p.agree ? "var(--text)" : "var(--warn)"}><title>{`${p.test}: extracted ${p.extracted.toFixed(4)} vs published ${p.published.toFixed(4)}`}</title></circle>)}
        <text x={12} y={22} fontSize={13} fill="var(--text-3)">extracted K</text><text x={188} y={186} fontSize={13} textAnchor="end" fill="var(--text-3)">published K</text>
      </svg>
      <p className="mono mt-1 text-xs">mean |error| {fmt(summary.mean_abs_error_pct, 3)}% · {summary.n_comparisons} comparisons</p>
      {summary.all_test_patterns && <p className="mt-1 text-2xs" style={{ color: "var(--warn)" }}>All media are synthetic test patterns. Agreement here proves the pipeline, not flame physics.</p>}
    </div>
  );
}

function ImageInner() {
  const sp = useSearchParams();
  const role = useUI((s) => s.role);
  const openProv = useUI((s) => s.openProv);
  const [list, setList] = useState<any>(null);
  const [test, setTest] = useState<string | null>(sp.get("test"));
  const [r, setR] = useState<any>(null);
  const [frame, setFrame] = useState(0);
  const [view, setView] = useState<"backlit" | "flame">("backlit");
  const [feat, setFeat] = useState<Feature[]>(ALL_FEATURES);
  const [mode, setMode] = useState<"inspect" | "compare">("inspect");
  const [params, setParams] = useState<any>({ threshold: 0.5, floor: 18, roi: null, window: null });
  const [job, setJob] = useState<any>(null);
  const [picked, setPicked] = useState<Feature | null>(null);
  const [cmp, setCmp] = useState<string[]>([]);
  const [tSync, setTSync] = useState(0);
  const [playing, setPlaying] = useState(false);
  const svg = useRef<SVGSVGElement>(null);
  const [box, bs] = useSize<HTMLDivElement>();

  const loadList = () => get("/vision/tests", { cache: false }).then((l) => { setList(l); if (!test && l.tests.length) setTest(l.tests[0].test_id); setCmp(l.tests.slice(0, 4).map((t: any) => t.test_id)); });
  useEffect(() => { loadList(); /* eslint-disable-next-line */ }, []);
  useEffect(() => {
    if (!test) return;
    get(`/vision/${test}`, { cache: false }).then((x) => {
      setR(x); setFrame(Math.floor(x.frames.length * 0.3));
      setParams({ threshold: x.views.backlit?.params?.threshold ?? 0.5, floor: x.views.flame?.params?.floor ?? 18, roi: x.views.backlit?.params?.roi ?? null, window: x.overrides?.window ?? null });
    });
  }, [test]);
  useEffect(() => {
    if (!playing || !r) return;
    const id = setInterval(() => setFrame((f) => (f + 1) % r.frames.length), 1000 / (r.views.backlit?.fps ?? 5));
    return () => clearInterval(id);
  }, [playing, r]);

  const rerun = async () => {
    const body = { params: { backlit: { threshold: params.threshold, roi: params.roi }, flame: { floor: params.floor }, ...(params.window ? { window: params.window } : {}) } };
    const { job: jid } = await post(`/vision/${test}/rerun`, body);
    setJob({ status: "running", progress: 0 });
    const poll = setInterval(async () => {
      const j = await get(`/vision/job/${jid}`, { cache: false });
      setJob(j);
      if (j.status !== "running") { clearInterval(poll); clearCache("/vision"); get(`/vision/${test}`, { cache: false }).then(setR); loadList(); }
    }, 300);
  };

  const cur = r?.frames[frame];
  const meta = r ? { ...(r.views[view] ?? r.views.backlit), kind: r.kind } : null;
  const row = list?.tests.find((t: any) => t.test_id === test)?.row;
  const caption = r ? `Test ${test} · frame ${frame} · t = ${cur?.t.toFixed(2)} s · ${r.kind === "test_pattern" ? "TEST PATTERN (synthetic) — not a flame, not NASA footage" : "footage"} · Freefall Atlas Image Lab` : "";
  const W = Math.max(500, bs.w);

  return (
    <div className="grid h-full grid-cols-[240px_minmax(0,1fr)_300px]">
      <aside className="rule-r space-y-6 overflow-y-auto px-5 pb-10 pt-5" aria-label="Tests with media">
        <div>
          <p className="eyebrow">Flame image measurements</p>
          <p className="mt-1 text-xs text-ink-3">Raw frames → measurements → evidence. Configured in config/media.yaml.</p>
          <p className="mono mt-3 rounded-sm px-2 py-1.5 text-2xs" style={{ border: "1px dashed var(--warn)", color: "var(--warn)" }}>TEST PATTERN — the loaded media are programmatically drawn shapes with known diameters, used to verify the extractors. No NASA footage is loaded.</p>
        </div>
        <div className="seg w-full"><button className="flex-1" aria-pressed={mode === "inspect"} onClick={() => setMode("inspect")}>Inspector</button><button className="flex-1" aria-pressed={mode === "compare"} onClick={() => setMode("compare")}>Side by side</button></div>
        <div>
          <p className="eyebrow">Tests · {list?.tests.length ?? 0}</p>
          {list?.tests.map((t: any) => (
            <div key={t.test_id} className={`rule-b flex items-center gap-2 py-2 ${test === t.test_id && mode === "inspect" ? "text-ink" : "text-ink-2"}`}>
              {mode === "compare" && <input type="checkbox" checked={cmp.includes(t.test_id)} onChange={(e) => setCmp(e.target.checked ? [...cmp, t.test_id].slice(-4) : cmp.filter((c) => c !== t.test_id))} aria-label={`compare ${t.test_id}`} />}
              <button className="flex-1 text-left" onClick={() => { setTest(t.test_id); setMode("inspect"); }}>
                <span className="mono text-[13px]">{t.test_id}</span> <span className="mono text-2xs" style={{ color: "var(--warn)" }}>{t.kind === "test_pattern" ? "test pattern" : ""}</span>
                <span className="block text-2xs text-ink-3">{t.row.fuel} · {fmtVar("o2_frac", t.row.o2_frac)} · {t.views.join(" + ")}</span>
                {t.fit?.ok && <span className="mono block text-2xs text-ink-3">K {fmt(t.fit.K, 4)} · R² {t.fit.r2.toFixed(4)}</span>}
              </button>
            </div>
          ))}
        </div>
        <Validation summary={list?.summary} />
      </aside>

      <section ref={box} className="min-w-0 overflow-y-auto" aria-label="Frames">
        {mode === "inspect" && r && cur && meta && (
          <div className="px-6 pb-10 pt-4">
            <div className="flex items-center gap-3">
              <span className="mono text-[15px]">{test}</span>
              {row && <span className="text-xs text-ink-3">{row.fuel} · {fmtVar("o2_frac", row.o2_frac)} O₂ · {fmtVar("pressure_kpa", row.pressure_kpa)} · {row.diluent} · d₀ {fmtVar("d0_mm", row.d0_mm)}</span>}
              <div className="seg ml-auto"><button aria-pressed={view === "backlit"} onClick={() => setView("backlit")}>Backlit view</button><button aria-pressed={view === "flame"} onClick={() => setView("flame")} disabled={!r.views.flame}>Flame view</button></div>
            </div>
            <div className="mt-3 flex flex-wrap items-center gap-3 text-xs text-ink-2">
              <span className="eyebrow">Callouts</span>
              {ALL_FEATURES.map((f) => <label key={f} className="flex items-center gap-1.5"><input type="checkbox" checked={feat.includes(f)} onChange={(e) => setFeat(e.target.checked ? [...feat, f] : feat.filter((x) => x !== f))} />{f}</label>)}
              <span className="ml-auto flex gap-1.5">
                <button className="btn h-7 text-xs" onClick={async () => svg.current && download(`annotated_${test}_f${frame}.png`, await svgToPng(svg.current))}>PNG</button>
                <button className="btn h-7 text-xs" onClick={() => svg.current && download(`annotated_${test}_f${frame}.svg`, svgString(svg.current), "image/svg+xml")}>SVG</button>
              </span>
            </div>
            <div className="mt-3">
              <AnnotatedFrame ref={svg} testId={test!} frame={cur} meta={meta} role={role} width={Math.min(W - 48, 820)} features={feat} view={view} caption={caption} onPick={setPicked} />
            </div>
            {picked && (
              <div className="rule mt-2 rounded-sm px-3 py-2 text-xs">
                <span className="eyebrow">Provenance · {picked}</span>
                <p className="mono mt-1 text-ink-2">file data/raw/{(picked === "flame" ? r.views.flame : r.views.backlit)?.path} · frame {cur.frame} · t {cur.t.toFixed(3)} s</p>
                <p className="mono text-ink-2">extractor {(picked === "flame" ? r.views.flame : r.views.backlit)?.extractor} v{(picked === "flame" ? r.views.flame : r.views.backlit)?.version} · params {JSON.stringify((picked === "flame" ? r.views.flame : r.views.backlit)?.params)}</p>
                <p className="mono text-ink-2">confidence {(picked === "flame" ? cur.flame?.confidence : cur.droplet?.confidence) ?? "—"} · mask vision/{test}.json#frame={cur.frame}</p>
                <button className="mt-1 text-ink-3 underline" onClick={() => openProv({ testId: test!, label: test! })}>test row provenance</button>
              </div>
            )}
            <div className="mt-4 flex items-center gap-3">
              <button className="btn h-7 w-16 justify-center text-xs" onClick={() => setPlaying(!playing)}>{playing ? "❚❚ pause" : "▶ play"}</button>
              <div className="relative flex-1">
                <input type="range" min={0} max={r.frames.length - 1} value={frame} onChange={(e) => setFrame(+e.target.value)} aria-label="Frame scrubber" aria-valuetext={`frame ${frame}`} />
                {r.derived.events.map((ev: any) => <span key={ev.type} title={ev.type} className="absolute -top-1 h-2 w-px" style={{ left: `${(ev.frame / (r.frames.length - 1)) * 100}%`, background: ev.type === "extinction" ? "var(--ext)" : "var(--flame)" }} />)}
              </div>
              <span className="mono w-28 text-right text-xs">f {frame} · {cur.t.toFixed(2)} s</span>
            </div>
            <div className="mt-4">
              <p className="eyebrow">d² vs time · hover to scrub · shift-drag to set the fit window</p>
              <D2Chart curve={r.derived.curve} fit={r.derived.fit} width={Math.min(W - 48, 820)} height={260} frame={frame} onHover={setFrame}
                onWindow={(w) => setParams({ ...params, window: w })} events={r.derived.events} />
            </div>
          </div>
        )}
        {mode === "compare" && list && (
          <div className="px-6 pb-10 pt-4">
            <div className="flex items-center gap-3">
              <p className="eyebrow">Synchronized in time · {cmp.length} tests</p>
              <input className="flex-1" type="range" min={0} max={Math.max(...list.tests.map((t: any) => (t.fit?.window?.[1] ?? 10) * 1.3))} step={0.1} value={tSync} onChange={(e) => setTSync(+e.target.value)} aria-label="Shared time" />
              <span className="mono w-16 text-right text-xs">t {tSync.toFixed(1)} s</span>
            </div>
            <div className="mt-4 grid grid-cols-2 gap-6">
              {cmp.map((id) => <ComparePanel key={id} id={id} t={tSync} role={role} width={Math.min((W - 72) / 2, 420)} row={list.tests.find((x: any) => x.test_id === id)?.row} />)}
            </div>
          </div>
        )}
      </section>

      <aside className="rule-l space-y-6 overflow-y-auto px-5 pb-10 pt-5" aria-label="Measurements and corrections">
        {r && (
          <>
            <div>
              <p className="eyebrow">Derived</p>
              <dl className="mt-2 grid grid-cols-[1fr_auto] gap-y-1 text-xs">
                <dt className="text-ink-3">burning-rate constant K</dt><dd className="mono">{r.derived.fit.ok ? `${fmt(r.derived.fit.K, 4)} mm²/s` : "—"}</dd>
                <dt className="text-ink-3">fit R² · n</dt><dd className="mono">{r.derived.fit.ok ? `${r.derived.fit.r2.toFixed(4)} · ${r.derived.fit.n}` : "—"}</dd>
                <dt className="text-ink-3">fit window</dt><dd className="mono">{r.derived.fit.window?.map((v: number) => v.toFixed(2)).join("–")} s</dd>
                <dt className="text-ink-3">d₀ (first frame)</dt><dd className="mono">{fmt(r.derived.d0_mm, 4)} mm</dd>
                <dt className="text-ink-3">extinction diameter</dt><dd className="mono">{r.derived.extinction_d_mm ? `${fmt(r.derived.extinction_d_mm, 4)} mm` : "none detected"}</dd>
                <dt className="text-ink-3">median standoff ratio</dt><dd className="mono">{r.derived.standoff_ratio_median ? r.derived.standoff_ratio_median.toFixed(2) : "—"}</dd>
              </dl>
              <p className="mt-2 text-2xs text-ink-3">These enter the canonical tests table as image-derived variables (img_*), with video file, frame range and extractor version as provenance.</p>
            </div>
            <div>
              <p className="eyebrow">Events</p>
              {r.derived.events.map((e: any) => <button key={e.type} className="rule-b flex w-full justify-between py-1 text-left text-xs hover:bg-surface-2" onClick={() => setFrame(e.frame)}><span>{e.type.replace("_", " ")}</span><span className="mono text-ink-3">f {e.frame} · {e.t.toFixed(2)} s</span></button>)}
            </div>
            <div>
              <p className="eyebrow">Validation · this test</p>
              {r.validation.rows.map((v: any) => (
                <div key={v.variable} className="rule-b grid grid-cols-[1fr_auto] py-1 text-xs">
                  <span className="text-ink-2">{v.variable}</span>
                  <span className="mono" style={{ color: v.agree ? "var(--text)" : "var(--warn)" }}>{v.error_pct >= 0 ? "+" : ""}{v.error_pct.toFixed(2)}%</span>
                  <span className="mono col-span-2 text-2xs text-ink-3">extracted {fmt(v.extracted, 4)} · published {fmt(v.published, 4)}</span>
                </div>
              ))}
            </div>
            <div>
              <p className="eyebrow">Correction loop</p>
              <label className="mt-2 block text-xs text-ink-2">Droplet threshold <span className="mono float-right">{params.threshold.toFixed(2)}</span>
                <input type="range" min={0.2} max={0.8} step={0.01} value={params.threshold} onChange={(e) => setParams({ ...params, threshold: +e.target.value })} /></label>
              <label className="mt-2 block text-xs text-ink-2">Flame intensity floor <span className="mono float-right">{params.floor}</span>
                <input type="range" min={5} max={80} step={1} value={params.floor} onChange={(e) => setParams({ ...params, floor: +e.target.value })} /></label>
              <div className="mt-2 text-xs text-ink-2">Region of interest (px)
                <div className="mt-1 grid grid-cols-4 gap-1">
                  {["x", "y", "w", "h"].map((k, i) => (
                    <input key={k} type="number" aria-label={`ROI ${k}`} placeholder={k} value={params.roi?.[i] ?? ""} className="w-full px-1 py-0.5"
                      onChange={(e) => { const roi = [...(params.roi ?? [0, 0, meta?.size?.[1] ?? 128, meta?.size?.[0] ?? 128])]; roi[i] = +e.target.value; setParams({ ...params, roi }); }} />
                  ))}
                </div>
                {params.roi && <button className="mt-1 text-2xs text-ink-3 underline" onClick={() => setParams({ ...params, roi: null })}>clear ROI</button>}
              </div>
              {params.window && <p className="mono mt-2 text-xs text-ink-2">fit window {params.window.map((v: number) => v.toFixed(2)).join("–")} s <button className="text-ink-3 underline" onClick={() => setParams({ ...params, window: null })}>auto</button></p>}
              <button className="btn primary mt-3 h-7 w-full justify-center text-xs" onClick={rerun} disabled={job?.status === "running"}>Re-run extraction</button>
              {job && (
                <div className="mt-2">
                  <div className="h-1 overflow-hidden rounded-sm bg-surface-3"><div className="h-full bg-ink transition-all" style={{ width: `${(job.progress ?? 0) * 100}%` }} /></div>
                  <p className="mono mt-1 text-2xs text-ink-3">{job.status}{job.error ? ` · ${job.error}` : ""}</p>
                </div>
              )}
              {r.overrides && Object.keys(r.overrides).length > 0 && <p className="mono mt-2 break-all text-2xs text-ink-3">manual corrections recorded {r.overrides._when ?? ""}: {JSON.stringify({ ...r.overrides, _when: undefined })}</p>}
            </div>
          </>
        )}
      </aside>
    </div>
  );
}

function ComparePanel({ id, t, role, width, row }: { id: string; t: number; role: string; width: number; row: any }) {
  const [r, setR] = useState<any>(null);
  useEffect(() => { get(`/vision/${id}`).then(setR); }, [id]);
  if (!r) return <div className="text-xs text-ink-3">loading {id}…</div>;
  const i = Math.min(r.frames.length - 1, Math.round(t * (r.views.backlit?.fps ?? 5)));
  const f = r.frames[i];
  return (
    <div>
      <p className="mono text-xs">{id} <span className="text-ink-3">· {row?.fuel} · {fmtVar("o2_frac", row?.o2_frac)} · {row?.diluent}</span></p>
      <AnnotatedFrame testId={id} frame={f} meta={{ ...r.views.backlit, kind: r.kind }} role={role} width={width} features={["droplet", "state"]} animate />
      <p className="mono text-2xs text-ink-3">{t * (r.views.backlit?.fps ?? 5) > r.frames.length - 1 ? "past end of record" : `frame ${i}`}</p>
    </div>
  );
}

export default function Page() { return <Suspense fallback={null}><ImageInner /></Suspense>; }
