"use client";
import { useSearchParams } from "next/navigation";
import { Suspense, useEffect, useMemo, useRef, useState } from "react";
import { download, get, post } from "@/lib/api";
import { PaletteName, svgString, svgToPng, useSize } from "@/lib/chart";
import { fmtVar, gravityLabel, vmeta } from "@/lib/format";
import { useMeta } from "@/lib/meta";
import { useUI } from "@/lib/store";
import Scatter, { Annotation } from "@/components/charts/Scatter";
import { CorrMatrix, Distribution, Envelope, Parallel, Timeline } from "@/components/charts/More";

type ChartType = "scatter" | "envelope" | "multiples" | "distribution" | "timeline" | "parallel" | "matrix" | "gap" | "advisor";
const TYPES: { id: ChartType; label: string; hint: string }[] = [
  { id: "scatter", label: "Scatter", hint: "two variables, colour by a third" },
  { id: "envelope", label: "Envelope", hint: "burn / extinguish regions with uncertainty band" },
  { id: "multiples", label: "Small multiples", hint: "one panel per category" },
  { id: "distribution", label: "Distribution", hint: "histogram split by outcome" },
  { id: "timeline", label: "Timeline", hint: "tests over mission date" },
  { id: "parallel", label: "Parallel coordinates", hint: "many variables at once" },
  { id: "matrix", label: "Correlation matrix", hint: "Spearman / mutual information" },
  { id: "gap", label: "Coverage / gap map", hint: "tested conditions vs target habitats" },
  { id: "advisor", label: "Next-experiment advisor", hint: "where a new test would teach most" },
];
const NUMS = ["o2_frac", "pressure_kpa", "o2_pp_kpa", "flow_cm_s", "d0_mm", "thickness_mm", "burn_rate_k_mm2_s", "extinction_d_mm", "spread_rate_mm_s", "img_burn_rate_k_mm2_s"];
const COLORS = ["burned", "fuel", "material", "diluent", "campaign", "o2_frac", "pressure_kpa", "dataset"];

/* starting chart and model per dataset; every dataset here is real NASA PSI data */
type DsDefault = { x: string; y: string; logX: boolean; facet: string; model: string; title: string;
  envelope?: { x: string; y: string; fixed: Record<string, any> } };
const SOLID: DsDefault = { x: "o2_frac", y: "thickness_mm", logX: false, facet: "material", model: "gas_sustain",
  title: "Solid-material tests in orbit: oxygen and sample thickness" };
const DS_DEFAULTS: Record<string, DsDefault> = {
  flex: { x: "o2_frac", y: "burn_rate_k_mm2_s", logX: false, facet: "fuel", model: "droplet_burn", title: "Burning-rate constant vs oxygen",
    envelope: { x: "pressure_kpa", y: "o2_frac", fixed: { fuel: "n-heptane", co2_frac: 0, he_frac: 0, d0_mm: 3 } } },
  cfig_normal: { x: "o2_frac", y: "pressure_kpa", logX: false, facet: "fuel", model: "gas_sustain", title: "Gas flames: still burning or went out, by oxygen and pressure",
    envelope: { x: "pressure_kpa", y: "o2_frac", fixed: { fuel: "30% butane", fuel_flow_mg_s: 1.0 } } },
  bass2: SOLID, saffire1: SOLID, saffire2: SOLID, saffire3: SOLID,
  cfi: { x: "o2_frac", y: "pressure_kpa", logX: false, facet: "fuel", model: "droplet_burn", title: "CFI cool-flame droplet tests: oxygen and pressure" },
  cfig_inverse: { x: "oxidizer_o2_frac", y: "pressure_kpa", logX: false, facet: "fuel", model: "gas_sustain", title: "Inverse flames: oxygen in the oxidizer stream and pressure" },
  acme_bre: { x: "o2_frac", y: "flames_ignited", logX: false, facet: "fuel", model: "gas_sustain", title: "Burning Rate Emulator: oxygen levels where flames ignited" },
  spice: { x: "fuel_flow_mg_s", y: "flow_cm_s", logX: false, facet: "fuel", model: "gas_sustain", title: "SPICE smoke-point flames: fuel flow and air speed" },
  same_r: { x: "heater_ratio", y: "smoke_aging_s", logX: false, facet: "material", model: "gas_sustain", title: "SAME-R smoke tests: heater setting and smoke aging" },
  same: { x: "flow_cm_s", y: "smoke_aging_s", logX: false, facet: "material", model: "gas_sustain", title: "SAME smoke tests: airflow and smoke aging" },
  efield: { x: "flames_ignited", y: "flames_ignited", logX: false, facet: "fuel", model: "gas_sustain", title: "E-FIELD flames ignited per test day" },
};
const dsDefault = (ds: string) => DS_DEFAULTS[ds] ?? SOLID;

function StudioInner() {
  const sp = useSearchParams();
  const meta = useMeta();
  const { openProv, addReport, report, removeReport, clearReport } = useUI();
  const [dataset, setDataset] = useState(sp.get("dataset") || "flex");
  const d0 = dsDefault(sp.get("dataset") || "flex");
  const [type, setType] = useState<ChartType>((sp.get("chart") as ChartType) || "scatter");
  const [rows, setRows] = useState<any[]>([]);
  const [allRows, setAllRows] = useState<any[]>([]);
  const [x, setX] = useState(d0.x);
  const [y, setY] = useState(d0.y);
  const [color, setColor] = useState("burned");
  const [size, setSize] = useState("");
  const [logX, setLogX] = useState(d0.logX);
  const [logY, setLogY] = useState(false);
  const [palette, setPalette] = useState<PaletteName>("default");
  const [title, setTitle] = useState(d0.title);
  const [ann, setAnn] = useState<Annotation[]>([]);
  const [annMode, setAnnMode] = useState(false);
  const [pending, setPending] = useState<{ x: number; y: number } | null>(null);
  const [annText, setAnnText] = useState("");
  const [sel, setSel] = useState<string[] | null>(null);
  const [facet, setFacet] = useState(d0.facet);
  const [grid, setGrid] = useState<any>(null);
  const [rel, setRel] = useState<any>(null);
  const [metric, setMetric] = useState<"spearman" | "mutual_info">("spearman");
  const [pvars, setPvars] = useState<string[]>([]);
  const [gap, setGap] = useState<any>(null);
  const [adv, setAdv] = useState<any>(null);
  const [advModel, setAdvModel] = useState(d0.model);
  const [advTarget, setAdvTarget] = useState("moon_base");
  const [cite, setCite] = useState<any>(null);
  const [showTable, setShowTable] = useState(false);
  const svg = useRef<SVGSVGElement>(null);
  const [box, bsize] = useSize<HTMLDivElement>();
  const groupFilter = sp.get("group");
  const TITLES: Partial<Record<ChartType, string>> = {
    envelope: "Where it burns: model envelope with uncertainty band", multiples: "Small multiples", distribution: "Distribution by outcome",
    timeline: "Tests over time", parallel: "All conditions at once", matrix: "Relationships between variables",
    gap: "Tested conditions vs target habitats", advisor: "Where the next test would teach most",
  };
  useEffect(() => { if (TITLES[type]) setTitle(TITLES[type]!); /* eslint-disable-next-line */ }, [type]);

  useEffect(() => {
    get(`/tests?dataset=${dataset}`).then((r) => {
      setAllRows(r);
      if (groupFilter) get(`/node/${encodeURIComponent(groupFilter)}`).then((n) => setRows(r.filter((t: any) => n.group?.test_ids.includes(t.test_id))));
      else setRows(r);
    });
    get(`/relationships/${dataset}`).then((r) => { setRel(r); setPvars(r.order.map((i: number) => r.vars[i]).filter((v: string) => v !== "burned")); });
    const d = dsDefault(dataset);
    setX(d.x); setY(d.y); setLogX(d.logX); setFacet(d.facet); setAdvModel(d.model);
    if (type === "scatter") setTitle(d.title);
    setSel(null); setAnn([]);
  }, [dataset, groupFilter]);

  useEffect(() => {
    if (type !== "envelope") return;
    // solid-material tables have no model (no pressure, and BASS-II no outcome): show the droplet envelope for them
    const d = dsDefault(dataset), env = d.envelope ?? DS_DEFAULTS.flex.envelope!, model = d.envelope ? d.model : "droplet_burn";
    get(`/envelope?model=${model}&x=${env.x}&y=${env.y}&logx=false&fixed=${encodeURIComponent(JSON.stringify(env.fixed))}`).then(setGrid);
  }, [type, dataset]);
  useEffect(() => { if (type === "gap" && !gap) get("/gapmap").then(setGap); }, [type, gap]);
  useEffect(() => { if (type === "advisor") post("/advisor", { model: advModel, target: advTarget }).then(setAdv); }, [type, advModel, advTarget]);

  const plotted = sel ? rows.filter((r) => sel.includes(r.test_id)) : rows;
  const W = Math.max(400, bsize.w), H = Math.max(320, bsize.h - 8);
  const caption = `${title} — Freefall Atlas · ${dataset}${meta?.demo ? " · DEMO FIXTURE, not NASA results" : ""} · n=${plotted.length}`;
  const facets = useMemo(() => Array.from(new Set(plotted.map((r) => r[facet]).filter(Boolean))).sort() as string[], [plotted, facet]);
  const target = meta?.presets.targets.find((t: any) => t.id === advTarget);

  const exportSVG = () => svg.current && download(`${title.replace(/\W+/g, "_")}.svg`, svgString(svg.current, caption), "image/svg+xml");
  const exportPNG = async () => svg.current && download(`${title.replace(/\W+/g, "_")}.png`, await svgToPng(svg.current, caption));
  const exportCSV = async () => download(`${title.replace(/\W+/g, "_")}.csv`, await post<string>("/export/csv", { ids: plotted.map((r) => r.test_id), title: caption }, "text"), "text/csv");
  const exportCite = async () => setCite(await post("/export/citations", { tests: plotted.map((r) => r.test_id), investigations: Array.from(new Set(plotted.map((r) => r.investigation_id))) }));
  const toReport = () => svg.current && addReport({ id: `chart-${Date.now()}`, kind: "chart", title, svg: svgString(svg.current), caption });

  const exportReport = async () => {
    const c = await post<any>("/export/citations", { tests: allRows.slice(0, 60).map((r) => r.test_id), investigations: Array.from(new Set(allRows.map((r) => r.investigation_id))) });
    const body = report.map((r) => r.kind === "chart"
      ? `<figure>${r.svg}<figcaption>${r.caption ?? ""}</figcaption></figure>`
      : `<section><h3>${r.title}</h3><p>${r.text ?? ""}</p><p class="m">${r.cite ?? ""}</p></section>`).join("\n");
    const html = `<!doctype html><html><head><meta charset="utf-8"><title>Freefall Atlas report</title><style>body{font:14px/1.5 system-ui;max-width:860px;margin:40px auto;color:#0A111E;background:#F6F8FB}h1{font-weight:500}figure{margin:28px 0}figcaption,.m{font:11px ui-monospace,monospace;color:#555}svg{max-width:100%;height:auto;background:#0B0E14}pre{white-space:pre-wrap;font:11px ui-monospace,monospace;background:#EEF1F6;padding:12px}.demo{border:1px dashed #8E939B;padding:8px 12px;font-size:12px}</style></head><body>
<h1>Freefall Atlas report</h1><p class="m">Generated ${new Date().toISOString().slice(0, 10)}</p>${meta?.demo ? '<p class="demo">Contains DEMO FIXTURE data (synthetic) — not NASA results.</p>' : ""}
${body}<h2>References</h2><pre>${c.text}</pre><h2>BibTeX</h2><pre>${c.bibtex}</pre></body></html>`;
    download("freefall_atlas_report.html", html, "text/html");
  };

  const encode = (label: string, v: string, set: (s: string) => void, opts: string[], allowNone = false) => (
    <label className="flex items-center gap-2 text-xs text-ink-2">
      <span className="w-12 text-ink-3">{label}</span>
      <select className="min-w-0 flex-1" value={v} onChange={(e) => set(e.target.value)}>
        {allowNone && <option value="">none</option>}
        {opts.filter((o) => o === "" || o === "burned" || o === "dataset" || o === "campaign" || allRows.some((r) => r[o] != null)).map((o) => <option key={o} value={o}>{vmeta(o).label}{o.startsWith("img_") ? " (image-derived)" : ""}</option>)}
      </select>
    </label>
  );

  return (
    <div className="grid h-full grid-cols-[260px_minmax(0,1fr)_280px]" data-ready={allRows.length ? "studio" : undefined}>
      <aside className="rule-r space-y-5 overflow-y-auto px-5 pb-10 pt-5" aria-label="Chart settings">
        <div>
          <p className="eyebrow">Data</p>
          <select className="mt-2 w-full" value={dataset} onChange={(e) => setDataset(e.target.value)} aria-label="Dataset">
            {Object.entries(meta?.datasets ?? {}).filter(([, d]) => d.adapter !== "pdf_reports" && d.enabled)
              .map(([id, d]) => <option key={id} value={id}>{d.title.replace(" experimental table", "")}</option>)}
          </select>
          <p className="mono mt-1.5 text-2xs text-ink-3">{plotted.length} tests{groupFilter ? ` · group ${groupFilter.split(":").at(-1)}` : ""}{sel ? ` · ${sel.length} brushed` : ""}</p>
          {sel && <button className="btn mt-2 h-6 text-xs" onClick={() => setSel(null)}>clear selection</button>}
        </div>
        <div>
          <p className="eyebrow">Chart</p>
          <div className="mt-2">
            {TYPES.map((t) => (
              <button key={t.id} onClick={() => setType(t.id)} aria-pressed={type === t.id}
                className={`block w-full rounded-sm px-2 py-1.5 text-left text-[13px] ${type === t.id ? "bg-surface-3 text-ink" : "text-ink-2 hover:bg-surface-2"}`}>
                {t.label}<span className="block text-2xs text-ink-3">{t.hint}</span>
              </button>
            ))}
          </div>
        </div>
        {(type === "scatter" || type === "multiples") && (
          <div className="space-y-2">
            <p className="eyebrow">Encoding</p>
            {encode("x", x, setX, NUMS)}{encode("y", y, setY, NUMS)}{encode("colour", color, setColor, COLORS)}{type === "scatter" && encode("size", size, setSize, ["", ...NUMS], true)}
            {type === "multiples" && encode("facet", facet, setFacet, ["fuel", "material", "diluent", "campaign"])}
            <div className="flex gap-3 pt-1 text-xs text-ink-2">
              <label className="flex items-center gap-1.5"><input type="checkbox" checked={logX} onChange={(e) => setLogX(e.target.checked)} /> log x</label>
              <label className="flex items-center gap-1.5"><input type="checkbox" checked={logY} onChange={(e) => setLogY(e.target.checked)} /> log y</label>
            </div>
          </div>
        )}
        {(type === "distribution" || type === "timeline") && <div className="space-y-2"><p className="eyebrow">Variable</p>{encode("var", y, setY, NUMS)}</div>}
        {type === "matrix" && <div className="seg"><button aria-pressed={metric === "spearman"} onClick={() => setMetric("spearman")}>Spearman</button><button aria-pressed={metric === "mutual_info"} onClick={() => setMetric("mutual_info")}>MI</button></div>}
        {type === "advisor" && (
          <div className="space-y-2 text-xs">
            <p className="eyebrow">Advisor</p>
            <select className="w-full" value={advModel} onChange={(e) => setAdvModel(e.target.value)}>{Object.values(meta?.models ?? {}).map((m: any) => <option key={m.id} value={m.id}>{m.label}</option>)}</select>
            <select className="w-full" value={advTarget} onChange={(e) => setAdvTarget(e.target.value)}>{meta?.presets.targets.map((t: any) => <option key={t.id} value={t.id}>{t.label}</option>)}</select>
          </div>
        )}
        <div className="space-y-2">
          <p className="eyebrow">Style</p>
          <label className="flex items-center gap-2 text-xs text-ink-2"><span className="w-12 text-ink-3">palette</span>
            <select className="flex-1" value={palette} onChange={(e) => setPalette(e.target.value as PaletteName)}><option value="default">Freefall</option><option value="colorblind">Colour-blind safe (Okabe–Ito)</option></select></label>
          <button className={`btn h-7 w-full justify-center text-xs ${annMode ? "primary" : ""}`} onClick={() => setAnnMode(!annMode)} disabled={type !== "scatter"}>{annMode ? "Click the chart to annotate…" : "Add annotation"}</button>
          {ann.length > 0 && <button className="btn ghost h-6 text-xs" onClick={() => setAnn([])}>clear {ann.length} annotation(s)</button>}
          <p className="text-2xs text-ink-3">Outcome colours are fixed by meaning: amber = burned, blue = extinguished, violet hatch = uncertain, dotted grey = no data.</p>
        </div>
      </aside>

      <section className="flex min-w-0 flex-col" aria-label="Chart">
        <div className="rule-b flex items-center gap-2 px-5 py-2.5">
          <span contentEditable suppressContentEditableWarning className="min-w-[120px] rounded-sm px-1 text-[15px] outline-none focus:bg-surface-2" aria-label="Chart title (editable)"
            onBlur={(e) => setTitle(e.currentTarget.textContent || "Untitled")}>{title}</span>
          <div className="ml-auto flex items-center gap-1.5">
            <button className="btn h-7 text-xs" onClick={exportPNG}>PNG</button>
            <button className="btn h-7 text-xs" onClick={exportSVG}>SVG</button>
            <button className="btn h-7 text-xs" onClick={exportCSV}>CSV</button>
            <button className="btn h-7 text-xs" onClick={exportCite}>Cite</button>
            <button className="btn h-7 text-xs" onClick={() => setShowTable(!showTable)} aria-pressed={showTable}>Table</button>
            <button className="btn primary h-7 text-xs" onClick={toReport}>+ Report</button>
          </div>
        </div>
        {pending && (
          <form className="rule-b flex items-center gap-2 px-5 py-2 text-xs" onSubmit={(e) => { e.preventDefault(); if (annText.trim()) setAnn([...ann, { ...pending, text: annText.trim() }]); setPending(null); setAnnText(""); }}>
            <span className="text-ink-3">Annotation at ({+pending.x.toPrecision(3)}, {+pending.y.toPrecision(3)})</span>
            <input type="text" autoFocus value={annText} onChange={(e) => setAnnText(e.target.value)} className="flex-1" aria-label="Annotation text" />
            <button className="btn h-7 text-xs" type="submit">Add</button><button className="btn ghost h-7 text-xs" type="button" onClick={() => setPending(null)}>Cancel</button>
          </form>
        )}
        <div ref={box} className="min-h-0 flex-1 overflow-hidden px-4 pt-3">
          {bsize.w > 0 && type === "scatter" && (
            <Scatter ref={svg} rows={plotted} x={x} y={y} color={color} size={size || undefined} logX={logX} logY={logY} palette={palette}
              width={W - 10} height={H} title={undefined} annotations={ann}
              onPoint={(r) => openProv({ testId: r.test_id, label: r.test_id })}
              onBrush={(ids) => ids.length && setSel(ids)}
              onCanvasClick={annMode ? (ax, ay) => { setPending({ x: ax, y: ay }); setAnnMode(false); } : undefined} />
          )}
          {bsize.w > 0 && type === "envelope" && grid && (
            <Envelope ref={svg} grid={grid} rows={plotted.filter((r) => r.gravity_g == null || r.gravity_g < 0.5)} width={W - 10} height={H} logX={dataset !== "flex"}
              onPoint={(r) => openProv({ testId: r.test_id, label: r.test_id })} />
          )}
          {bsize.w > 0 && type === "multiples" && (
            <svg ref={svg} width={W - 10} height={H}>
              {facets.map((f, i) => {
                const cols = Math.ceil(Math.sqrt(facets.length)), cw = (W - 10) / cols, rh = H / Math.ceil(facets.length / cols);
                return (
                  <g key={f} transform={`translate(${(i % cols) * cw},${Math.floor(i / cols) * rh})`}>
                    <text x={34} y={14} fontSize={13} fill="var(--text)">{f} <tspan fill="var(--text-3)" className="mono">n={plotted.filter((r) => r[facet] === f).length}</tspan></text>
                    <g transform="translate(0,18)">
                      <ScatterInSvg rows={plotted.filter((r) => r[facet] === f)} all={plotted} x={x} y={y} color={color} logX={logX} logY={logY} w={cw - 12} h={rh - 26} palette={palette} />
                    </g>
                  </g>
                );
              })}
            </svg>
          )}
          {bsize.w > 0 && type === "distribution" && <Distribution ref={svg} rows={plotted} v={y} width={W - 10} height={H} palette={palette} />}
          {bsize.w > 0 && type === "timeline" && <Timeline ref={svg} rows={plotted} y={y} width={W - 10} height={H} onPoint={(r) => openProv({ testId: r.test_id, label: r.test_id })} />}
          {bsize.w > 0 && type === "parallel" && <Parallel ref={svg} rows={plotted} vars={pvars} width={W - 10} height={H} onReorder={setPvars} />}
          {bsize.w > 0 && type === "matrix" && rel && <CorrMatrix ref={svg} rel={rel} metric={metric} clustered width={W - 10} height={H} />}
          {bsize.w > 0 && type === "gap" && gap && (
            <Scatter ref={svg} rows={gap.points} x="o2_frac" y="pressure_kpa" color="burned" width={W - 10} height={H} palette={palette} logY boxLabels="column" labels={false}
              boxes={gap.targets.map((t: any) => {
                const n = gap.points.filter((p: any) => p.o2_frac >= t.o2_frac[0] && p.o2_frac <= t.o2_frac[1] && p.pressure_kpa >= t.pressure_kpa[0] && p.pressure_kpa <= t.pressure_kpa[1]).length;
                const partial = t.gravity_g > 0.02 && t.gravity_g < 0.95;
                return { x0: t.o2_frac[0], x1: t.o2_frac[1], y0: t.pressure_kpa[0], y1: t.pressure_kpa[1], label: t.label, hatch: partial,
                  sub: `${n} tests in box${partial ? ` · ${gravityLabel(t.gravity_g)} untested` : ""}` };
              })}
              onPoint={(r) => openProv({ testId: r.test_id, label: r.test_id })} />
          )}
          {bsize.w > 0 && type === "advisor" && adv && target && (
            <Scatter ref={svg} rows={allRows} x="o2_frac" y="pressure_kpa" color="burned" width={W - 10} height={H}
              boxes={[{ x0: target.o2_frac[0], x1: target.o2_frac[1], y0: target.pressure_kpa[0], y1: target.pressure_kpa[1], label: `target: ${target.label}`, hatch: target.gravity_g > 0.02 && target.gravity_g < 0.95 }]}
              extra={(sx, sy) => adv.suggestions.map((s: any, i: number) => (
                <g key={i} transform={`translate(${sx(s.conditions.o2_frac * 100)},${sy(s.conditions.pressure_kpa)})`}>
                  <rect x={-6} y={-6} width={12} height={12} fill="none" stroke="var(--text)" strokeWidth={1.4} transform="rotate(45)" />
                  <text x={10} y={4} fontSize={13} className="mono" fill="var(--text)" style={{ paintOrder: "stroke", stroke: "var(--bg)", strokeWidth: 3 }}>#{i + 1}</text>
                </g>
              ))}
              onPoint={(r) => openProv({ testId: r.test_id, label: r.test_id })} />
          )}
        </div>
        {showTable && (
          <div className="rule-t max-h-56 overflow-auto px-5 py-2">
            <table className="w-full text-xs" aria-label="Data behind the chart">
              <thead><tr className="rule-b text-left text-ink-3"><th className="py-1 font-normal">test</th>{[x, y, color].map((v) => <th key={v} className="font-normal">{vmeta(v).label}</th>)}</tr></thead>
              <tbody>{plotted.slice(0, 300).map((r) => <tr key={r.test_id} className="rule-b"><td className="mono py-0.5">{r.test_id}</td>{[x, y, color].map((v) => <td key={v} className="mono">{typeof r[v] === "number" ? fmtVar(v, r[v]) : String(r[v] ?? "—")}</td>)}</tr>)}</tbody>
            </table>
          </div>
        )}
        {cite && (
          <div className="rule-t grid max-h-48 grid-cols-2 gap-3 overflow-auto px-5 py-3">
            <pre className="mono whitespace-pre-wrap text-2xs text-ink-2">{cite.text}</pre>
            <pre className="mono whitespace-pre-wrap text-2xs text-ink-2">{cite.bibtex}</pre>
          </div>
        )}
      </section>

      <aside className="rule-l overflow-y-auto px-5 pb-10 pt-5" aria-label="Notes and report">
        {type === "gap" && gap && <p className="mb-4 text-xs" style={{ color: "var(--unc)" }}>{gap.note}</p>}
        {type === "envelope" && grid && <p className="mb-4 text-xs text-ink-2">Model: {grid.label}. Other features fixed at {Object.entries(grid.fixed).filter(([k]) => k !== grid.x && k !== grid.y).map(([k, v]) => `${vmeta(k).short ?? k}=${typeof v === "number" ? (+v.toPrecision(3)) : v}`).join(", ")}. The black line is p = 0.5; dashed lines bound 0.25–0.75.</p>}
        {type === "advisor" && adv && (
          <div className="mb-6">
            <p className="eyebrow">Suggested tests · {adv.criterion}</p>
            {adv.suggestions.map((s: any, i: number) => (
              <div key={i} className="rule-b py-2 text-xs">
                <span className="mono text-ink">#{i + 1} · O₂ {(s.conditions.o2_frac * 100).toFixed(1)}% · {s.conditions.pressure_kpa.toFixed(1)} kPa{s.conditions.flow_cm_s ? ` · ${s.conditions.flow_cm_s.toFixed(1)} cm/s` : ""}</span>
                <p className="mt-0.5 text-ink-3">{s.rationale}</p>
              </div>
            ))}
            <p className="mt-2 text-2xs" style={{ color: "var(--warn)" }}>{adv.note}</p>
          </div>
        )}
        <p className="eyebrow">Report · {report.length}</p>
        <p className="mt-1 text-xs text-ink-3">Charts and findings added from the Studio and the Answer Engine. Exports one HTML page with references; print it to PDF.</p>
        <div className="mt-3 space-y-2">
          {report.map((r) => (
            <div key={r.id} className="rule flex items-start gap-2 rounded-sm p-2 text-xs">
              <span className="eyebrow mt-0.5">{r.kind}</span><span className="flex-1">{r.title}</span>
              <button className="text-ink-3 hover:text-ink" onClick={() => removeReport(r.id)} aria-label="Remove">✕</button>
            </div>
          ))}
        </div>
        {report.length > 0 && <div className="mt-3 flex gap-2"><button className="btn primary h-7 text-xs" onClick={exportReport}>Export report (HTML)</button><button className="btn ghost h-7 text-xs" onClick={clearReport}>Clear</button></div>}
      </aside>
    </div>
  );
}

function ScatterInSvg(p: { rows: any[]; all: any[]; x: string; y: string; color: string; logX: boolean; logY: boolean; w: number; h: number; palette: PaletteName }) {
  // shared domains across panels so small multiples compare honestly
  const ext = (k: string) => { const v = p.all.map((r) => r[k]).filter((v) => v != null && (!(k === p.x ? p.logX : p.logY) || v > 0)); return [Math.min(...v), Math.max(...v)] as [number, number]; };
  return <Scatter rows={p.rows} x={p.x} y={p.y} color={p.color} logX={p.logX} logY={p.logY} width={p.w} height={p.h} mini xDomain={ext(p.x)} yDomain={ext(p.y)} palette={p.palette} />;
}

export default function Page() { return <Suspense fallback={null}><StudioInner /></Suspense>; }
