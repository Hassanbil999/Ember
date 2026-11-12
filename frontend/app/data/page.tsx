"use client";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useEffect, useMemo, useState } from "react";
import { get } from "@/lib/api";
import { fmtVar } from "@/lib/format";
import { useUI } from "@/lib/store";

/* Data: what is loaded, what was set aside and why, and every test one click from its full record. */

const RULE: Record<string, string> = {
  impossible_value: "Impossible value", implausible: "Unusual value", duplicate: "Duplicate row",
  missing_outcome: "No burn-or-extinguish outcome", rate_without_burn: "Spread rate reported for an extinguished sample",
  fractions_do_not_sum: "Gas fractions do not add up", extinction_larger_than_start: "Extinction diameter larger than the start",
};
const PAGE = 25;
type Filter = "all" | "warn" | "excluded";

function Inner() {
  const sp = useSearchParams();
  const openProv = useUI((s) => s.openProv);
  const [ref, setRef] = useState<any>(null);
  const [ds, setDs] = useState(sp.get("dataset") || "flex");
  const [rows, setRows] = useState<any[]>([]);
  const [filter, setFilter] = useState<Filter>("all");
  const [page, setPage] = useState(0);

  useEffect(() => { get("/refinery").then(setRef); }, []);
  useEffect(() => { setRows([]); setPage(0); get(`/tests?dataset=${ds}&include_excluded=true`).then(setRows); }, [ds]);
  useEffect(() => {
    const t = sp.get("test");
    if (t) openProv({ testId: t, label: t });
  }, [sp, openProv]);

  const warm = (id: string) => { get(`/test/${encodeURIComponent(id)}`).catch(() => {}); };   // record ready before the click lands
  const tables = (ref?.datasets ?? []).filter((d: any) => d.kind === "table");
  const cur = tables.find((d: any) => d.id === ds);
  const solid = rows.some((r) => r.material != null);
  const shown = useMemo(() => rows.filter((r) => filter === "all" || (filter === "excluded" ? r.excluded : !r.excluded && r.flags.length > 0)), [rows, filter]);
  const pages = Math.max(1, Math.ceil(shown.length / PAGE));
  const byRule: Record<string, any[]> = {};
  for (const e of cur?.log ?? []) (byRule[e.rule] ||= []).push(e);
  useEffect(() => {
    if (!cur) return;
    const t = setTimeout(() => cur.log.slice(0, 30).forEach((e: any) => warm(e.test_id)), 300);
    return () => clearTimeout(t);
  }, [cur]); // eslint-disable-line react-hooks/exhaustive-deps
  const cell = (r: any, v: string) => r.invalid?.[v] ? <span style={{ color: "var(--warn)" }}>Flagged</span> : r[v] == null ? <span className="text-ink-3">not reported</span> : <span className="mono">{fmtVar(v, r[v], 4)}</span>;
  const total = cur ? cur.quality.kept + cur.quality.flagged + cur.quality.excluded : 0;

  return (
    <div className="mx-auto max-w-[1240px] px-8 pb-16 pt-8" data-ready={cur && rows.length ? "data" : undefined}>
      <div className="flex flex-wrap items-end gap-x-6 gap-y-3">
        <h1 className="title">Data</h1>
        <div className="seg" role="group" aria-label="Data set">
          {tables.map((d: any) => <button key={d.id} aria-pressed={ds === d.id} onClick={() => setDs(d.id)}>{d.title.split(" (")[0]}</button>)}
        </div>
      </div>
      {cur && (
        <>
          <p className="mt-3 text-base text-ink-2">{cur.title}. {cur.demo ? <span style={{ color: "var(--warn)" }}>Synthetic demo file, not NASA data.</span> : <span>Real NASA data, loaded as published.</span>}</p>

          <section className="card mt-6 p-6" aria-label="Data quality">
            <h2 className="text-lg font-semibold tracking-tight">Data quality</h2>
            <div className="mt-3 flex h-4 overflow-hidden rounded-full" role="img" aria-label={`${cur.quality.kept} used, ${cur.quality.flagged} used with a warning, ${cur.quality.excluded} excluded`}>
              <span style={{ width: `${(cur.quality.kept / total) * 100}%`, background: "var(--text-2)" }} />
              <span style={{ width: `${(cur.quality.flagged / total) * 100}%`, background: "var(--warn)" }} />
              <span style={{ width: `${(cur.quality.excluded / total) * 100}%`, minWidth: cur.quality.excluded ? 6 : 0, background: "var(--nodata)" }} />
            </div>
            <p className="mt-3 flex flex-wrap gap-x-8 gap-y-1 text-sm text-ink-2">
              <span><span className="mono text-lg text-ink">{cur.quality.kept}</span> rows used as they are</span>
              <span><span className="mono text-lg" style={{ color: "var(--warn)" }}>{cur.quality.flagged}</span> used, with a warning</span>
              <span><span className="mono text-lg text-ink">{cur.quality.excluded}</span> excluded from every chart and model</span>
            </p>
            <p className="mt-4 text-sm text-ink-3">How the file is processed: {cur.stages.map((s: any) => `${s.label.toLowerCase()} (${s.rows} rows)`).join(" → ")}. Values are checked before any unit conversion; nothing is silently fixed.</p>
          </section>

          {Object.keys(byRule).length > 0 && (
            <section className="mt-8">
              <h2 className="text-lg font-semibold tracking-tight">Set aside or marked</h2>
              <div className="mt-3 grid grid-cols-1 gap-4 md:grid-cols-2">
                {Object.entries(byRule).map(([rule, es]) => (
                  <div key={rule} className="card p-5" data-rule={rule}>
                    <p className="flex items-center gap-3"><span className="text-base font-medium text-ink">{RULE[rule] ?? rule}</span>
                      <span className={`status ${es[0].action === "exclude" ? "flagged" : "blank"}`}>{es[0].action === "exclude" ? "Excluded" : "Kept with a warning"}</span></p>
                    <p className="mt-1.5 text-sm text-ink-2">{es[0].reason}</p>
                    <div className="mt-3 flex flex-wrap gap-2">
                      {es.map((e: any, i: number) => <button key={i} className="mono rounded px-2.5 py-1 text-sm text-ink hover:bg-surface-3" style={{ background: "var(--surface-2)" }} data-test={e.test_id} onMouseEnter={() => warm(e.test_id)} onFocus={() => warm(e.test_id)} onClick={() => openProv({ testId: e.test_id, label: e.test_id })}>{e.test_id}</button>)}
                    </div>
                  </div>
                ))}
              </div>
            </section>
          )}

          <section className="mt-8">
            <div className="flex flex-wrap items-center gap-4">
              <h2 className="text-lg font-semibold tracking-tight">All tests</h2>
              <div className="seg" role="group" aria-label="Show">
                {([["all", "All"], ["warn", "With a warning"], ["excluded", "Excluded"]] as [Filter, string][]).map(([k, l]) => <button key={k} aria-pressed={filter === k} onClick={() => { setFilter(k); setPage(0); }}>{l}</button>)}
              </div>
              <span className="text-sm text-ink-3">{shown.length} tests. Select one to read its full record.</span>
            </div>
            <div className="card mt-3 overflow-x-auto">
              <table className="w-full text-sm">
                <thead><tr className="rule-b text-left text-ink-3">
                  {["Test", solid ? "Material" : "Fuel", "Oxygen", "Pressure", solid ? "Airflow" : "Droplet size", "Gravity", "Outcome", ""].map((h) => <th key={h} className="whitespace-nowrap px-4 py-3 font-normal">{h}</th>)}
                </tr></thead>
                <tbody>
                  {shown.slice(page * PAGE, (page + 1) * PAGE).map((r) => (
                    <tr key={r.test_id} className="rule-b cursor-pointer hover:bg-surface-2" tabIndex={0} data-row={r.test_id} onMouseEnter={() => warm(r.test_id)}
                      onClick={() => openProv({ testId: r.test_id, label: r.test_id })} onKeyDown={(e) => { if (e.key === "Enter") openProv({ testId: r.test_id, label: r.test_id }); }}>
                      <td className="mono whitespace-nowrap px-4 py-2.5 text-ink">{r.test_id}</td>
                      <td className="px-4 py-2.5 text-ink">{(solid ? r.material : r.fuel) ?? <span className="text-ink-3">not reported</span>}</td>
                      <td className="whitespace-nowrap px-4 py-2.5">{cell(r, "o2_frac")}</td>
                      <td className="whitespace-nowrap px-4 py-2.5">{cell(r, "pressure_kpa")}</td>
                      <td className="whitespace-nowrap px-4 py-2.5">{cell(r, solid ? "flow_cm_s" : "d0_mm")}</td>
                      <td className="whitespace-nowrap px-4 py-2.5 text-ink-2">{r.gravity ?? "not reported"}</td>
                      <td className="whitespace-nowrap px-4 py-2.5" style={{ color: r.burned == null ? "var(--nodata)" : r.burned ? "var(--flame)" : "var(--ext)" }}>{r.outcome ?? "Not recorded"}</td>
                      <td className="whitespace-nowrap px-4 py-2.5 text-right">{r.excluded ? <span className="status flagged">Excluded</span> : r.flags.length ? <span className="status blank">Warning</span> : null}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className="mt-3 flex items-center gap-3 text-sm text-ink-2">
              <button className="btn h-9" disabled={page === 0} onClick={() => setPage(page - 1)}>Previous</button>
              <span>Page {page + 1} of {pages}</span>
              <button className="btn h-9" disabled={page >= pages - 1} onClick={() => setPage(page + 1)}>Next</button>
            </div>
          </section>

          <section className="mt-10 flex flex-wrap gap-3">
            <Link href={`/studio?dataset=${ds}`} className="btn h-11 px-5">Chart this data in Studio</Link>
            <Link href="/image" className="btn h-11 px-5">Flame image measurements</Link>
          </section>
        </>
      )}
      {!cur && <p className="mt-6 text-ink-3">Loading…</p>}
    </div>
  );
}

export default function DataPage() {
  return <Suspense><Inner /></Suspense>;
}
