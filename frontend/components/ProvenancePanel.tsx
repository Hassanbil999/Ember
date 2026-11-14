"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import { get } from "@/lib/api";
import { fmtVar, vmeta } from "@/lib/format";
import { useUI } from "@/lib/store";

/* Three levels of detail (progressive disclosure):
   1  every value, readable, with a status chip; flagged values first, each with its reason
   2  click a row: where the value comes from, in plain words, with a link to the source row
   3  "Technical trail": raw string, parse and conversion steps, file path, variable name */

const GROUPS: [string, string][] = [["conditions", "Conditions"], ["results", "Results"], ["metadata", "About this test"]];
const OP_WORDS: Record<string, string> = { count: "number", count_true: "number that burned", share: "share that burned", min: "range", max: "range", median: "median", mean: "average" };
const CHIP: Record<string, string> = { measured: "Measured", derived: "Derived", assumed: "Assumed (dataset setting)", flagged: "Flagged", image: "Measured from images", blank: "No value" };

function recompute(op: string, vals: (number | null)[]) {
  const v = vals.filter((x): x is number => x != null && !Number.isNaN(x));
  if (op === "count") return vals.length;
  if (!v.length) return null;
  const s = [...v].sort((a, b) => a - b);
  switch (op) {
    case "min": return s[0];
    case "max": return s[s.length - 1];
    case "median": return s.length % 2 ? s[(s.length - 1) / 2] : (s[s.length / 2 - 1] + s[s.length / 2]) / 2;
    case "mean": case "share": return v.reduce((a, b) => a + b, 0) / v.length;
    case "count_true": return v.filter(Boolean).length;
  }
  return null;
}

function Row({ f, open, onToggle, trail, testId }: { f: any; open: boolean; onToggle: () => void; trail: boolean; testId: string }) {
  const openSourceRow = useUI((s) => s.openSourceRow);
  const openProv = useUI((s) => s.openProv);
  const cls = f.status === "image" ? "measured" : f.status;
  return (
    <li className="rule-b" data-prov-row={f.var} data-status={f.status}>
      <button className="flex w-full items-start gap-3 py-3 text-left hover:bg-surface-2" onClick={onToggle} aria-expanded={open}>
        <span className="w-[38%] shrink-0 text-sm text-ink-2">{f.label}</span>
        <span className="min-w-0 flex-1">
          {f.value != null ? (
            <span data-value className={`text-base ${f.status === "assumed" ? "italic text-ink-2" : "text-ink"}`}>
              <span className={f.unit || /^[\d.]/.test(f.value) ? "mono" : ""}>{f.value}</span>{f.unit && <span className="ml-1 text-sm text-ink-3">{f.unit}</span>}
            </span>
          ) : (
            <span className="text-sm" style={{ color: f.status === "flagged" ? "var(--warn)" : "var(--nodata)" }}>{f.note}</span>
          )}
        </span>
        <span className={`status ${cls} shrink-0`}>{CHIP[f.status]}</span>
      </button>
      {(open || trail) && (
        <div className="pb-3.5 pl-[38%] pr-2 text-sm">
          {open && (
            <div className="rise space-y-1.5 pl-3 text-ink-2">
              {f.note && f.value != null && <p>{f.note}</p>}
              <p><span className="text-ink-3">Source: </span>{f.source.text}</p>
              {f.source.kind === "table" && (
                <button className="underline decoration-dotted underline-offset-4 hover:text-ink" data-open-source
                  onClick={() => openSourceRow({ dataset: f.source.dataset, row: f.source.row, column: f.source.column })}>Open the source table at this row</button>
              )}
              {f.source.kind === "images" && <Link className="underline decoration-dotted underline-offset-4 hover:text-ink" href={`/image?test=${testId}`} onClick={() => openProv(null)}>Open the images</Link>}
            </div>
          )}
          {trail && (
            <dl className="mono mt-2 grid grid-cols-[84px_1fr] gap-x-3 gap-y-1 rounded p-3 text-xs text-ink-2" style={{ background: "var(--surface-2)" }} data-trail>
              <dt className="text-ink-3">variable</dt><dd>{f.trail.variable}</dd>
              <dt className="text-ink-3">raw</dt><dd>{f.trail.raw == null ? "(empty cell)" : `“${f.trail.raw}”`}</dd>
              <dt className="text-ink-3">file</dt><dd className="break-all">{f.trail.file}</dd>
              <dt className="text-ink-3">where</dt><dd>{f.trail.locator}{f.trail.column ? `, column “${f.trail.column}”` : ""}</dd>
              {f.trail.steps.map((s: any, i: number) => (<span key={i} className="contents"><dt className="text-ink-3">{s.op}</dt><dd>{s.detail}</dd></span>))}
              {f.trail.steps.length === 0 && (<><dt className="text-ink-3">steps</dt><dd>none: stored as read</dd></>)}
            </dl>
          )}
        </div>
      )}
    </li>
  );
}

function TestRecord({ id }: { id: string }) {
  const [rec, setRec] = useState<any>(null);
  const [open, setOpen] = useState<string | null>(null);
  const [trail, setTrail] = useState(false);
  useEffect(() => { setRec(null); setOpen(null); get(`/test/${encodeURIComponent(id)}`).then(setRec).catch(() => setRec({ error: true })); }, [id]);
  if (!rec) return <p className="text-sm text-ink-3">Loading…</p>;
  if (rec.error) return <p className="text-sm text-ink-3">No record found for this test.</p>;
  const flagged = rec.fields.filter((f: any) => f.status === "flagged");
  const rest = rec.fields.filter((f: any) => f.status !== "flagged");
  const row = (f: any) => <Row key={f.var} f={f} testId={rec.test_id} trail={trail} open={open === f.var} onToggle={() => setOpen(open === f.var ? null : f.var)} />;
  return (
    <div data-ready="provenance" data-prov-test={rec.test_id}>
      <div className="flex items-end justify-between gap-4">
        <div>
          <p className="mono text-[26px] leading-8 text-ink">{rec.test_id}</p>
          <p className="mt-1 text-sm text-ink-2">{rec.dataset_title}{rec.investigation ? `, ${rec.investigation}` : ""}, source row {rec.source_row}</p>
        </div>
        <label className="flex shrink-0 cursor-pointer items-center gap-2 text-sm text-ink-2">
          <input type="checkbox" className="h-4 w-4 accent-[var(--flame)]" checked={trail} onChange={(e) => setTrail(e.target.checked)} data-trail-toggle />
          Technical trail
        </label>
      </div>
      {rec.demo && <p className="mt-3 text-sm" style={{ color: "var(--warn)" }}>Demo row: synthetic, not a NASA result.</p>}

      {(rec.notices.length > 0 || rec.excluded) && (
        <div className="mt-4 rounded-md p-4" style={{ border: "1px solid var(--warn)", background: "var(--warn-soft)" }} data-notices>
          {rec.excluded && <p className="text-sm font-medium text-ink">This test is excluded from every chart, statistic and model.</p>}
          <ul className={`space-y-2 ${rec.excluded ? "mt-2" : ""}`}>
            {rec.notices.map((n: any, i: number) => (
              <li key={i} className="text-sm text-ink-2"><span className="font-medium text-ink">{n.title}. </span>{n.reason}</li>
            ))}
          </ul>
        </div>
      )}

      {flagged.length > 0 && (
        <section className="mt-6">
          <h3 className="eyebrow" style={{ color: "var(--warn)" }}>Flagged values</h3>
          <ul className="rule-t mt-2">{flagged.map(row)}</ul>
        </section>
      )}
      {GROUPS.map(([g, title]) => {
        const fs = rest.filter((f: any) => f.group === g);
        return fs.length ? (<section key={g} className="mt-6"><h3 className="eyebrow">{title}</h3><ul className="rule-t mt-2">{fs.map(row)}</ul></section>) : null;
      })}
      <p className="mt-5 text-sm text-ink-3">Select any row to see where its value comes from.</p>
      {rec.media.length > 0 && (
        <p className="mt-2 text-sm text-ink-2">This test has an image sequence ({rec.media[0].kind === "test_pattern" ? "synthetic test pattern" : "footage"}). <Link className="underline decoration-dotted underline-offset-4" href={`/image?test=${rec.test_id}`}>Open the images</Link></p>
      )}
    </div>
  );
}

function SourceRowViewer() {
  const { sourceRow, openSourceRow } = useUI();
  const [d, setD] = useState<any>(null);
  useEffect(() => { setD(null); if (sourceRow) get(`/source/${sourceRow.dataset}/row/${sourceRow.row}`).then(setD); }, [sourceRow]);
  if (!sourceRow) return null;
  return (
    <div className="fixed inset-0 z-[60] flex items-center justify-center bg-black/60 p-8" onMouseDown={() => openSourceRow(null)} role="dialog" aria-label="Source table">
      <div className="card flex max-h-full w-full max-w-[1100px] flex-col overflow-hidden" onMouseDown={(e) => e.stopPropagation()} data-ready="source-row">
        <div className="rule-b flex items-center gap-3 px-5 py-3">
          <div className="min-w-0">
            <p className="truncate text-base text-ink">{d?.title ?? "Source table"}</p>
            <p className="text-sm text-ink-3">The file exactly as loaded: <span className="mono">{d?.file}</span>, row {sourceRow.row}{sourceRow.column ? `, column “${sourceRow.column}”` : ""}{d?.demo ? " (demo file)" : ""}</p>
          </div>
          <button className="btn ghost ml-auto h-9 w-9 justify-center p-0" onClick={() => openSourceRow(null)} aria-label="Close">✕</button>
        </div>
        <div className="overflow-auto p-5">
          {d && (
            <table className="mono w-max min-w-full border-collapse text-xs">
              <thead><tr><th className="rule-b px-2 py-2 text-left font-normal text-ink-3">row</th>
                {d.columns.map((c: string) => <th key={c} className="rule-b px-3 py-2 text-left font-normal" style={{ color: c === sourceRow.column ? "var(--flame)" : "var(--text-3)" }}>{c}</th>)}</tr></thead>
              <tbody>
                {d.rows.map((r: any) => {
                  const hit = r.n === sourceRow.row;
                  return (
                    <tr key={r.n} style={hit ? { background: "var(--highlight)" } : undefined}>
                      <td className="rule-b px-2 py-2 text-ink-3">{r.n}</td>
                      {r.cells.map((c: string, i: number) => (
                        <td key={i} className="rule-b whitespace-nowrap px-3 py-2" style={hit && d.columns[i] === sourceRow.column ? { outline: "2px solid var(--flame)", outlineOffset: -2, color: "var(--text)" } : { color: hit ? "var(--text)" : "var(--text-2)" }}>{c || "(empty)"}</td>
                      ))}
                    </tr>
                  );
                })}
              </tbody>
            </table>
          )}
        </div>
      </div>
    </div>
  );
}

export default function ProvenancePanel() {
  const { prov, openProv, openSource } = useUI();
  const [rows, setRows] = useState<any[] | null>(null);
  const c = prov?.citation;
  const testId = prov?.testId ?? (c?.kind === "row" ? c.target : undefined);

  useEffect(() => {
    setRows(null);
    if (!prov || testId) return;
    if (c?.kind === "aggregate") get(`/tests?include_excluded=true&ids=${encodeURIComponent(c.rows.slice(0, 400).join(","))}`).then(setRows);
    else if (c?.kind === "chunk") { openProv(null); openSource({ doc: c.target.split("#")[0], page: c.page ?? 1, spans: c.span ? [c.span] : [], chunk: c.target }); }
  }, [prov, c, testId, openProv, openSource]);
  useEffect(() => {
    // Escape closes one layer at a time: the source table first, then the panel
    const k = (e: KeyboardEvent) => {
      if (e.key !== "Escape") return;
      const st = useUI.getState();
      if (st.sourceRow) st.openSourceRow(null); else if (!st.source) openProv(null);
    };
    window.addEventListener("keydown", k);
    return () => window.removeEventListener("keydown", k);
  }, [openProv]);

  return (
    <>
      {prov && (
        <aside className="fixed bottom-0 right-0 top-14 z-40 flex w-[600px] max-w-full flex-col bg-surface rule-l" style={{ boxShadow: "var(--shadow)" }} aria-label="Where this comes from" role="dialog">
          <div className="rule-b flex h-12 shrink-0 items-center gap-3 px-6">
            <span className="text-sm font-medium text-ink">Where this comes from</span>
            {testId && c?.kind === "aggregate" && <button className="btn ghost h-8 px-2 text-sm" onClick={() => openProv({ citation: c, label: prov.label })}>Back to the list</button>}
            <button className="btn ghost ml-auto h-9 w-9 justify-center p-0" onClick={() => openProv(null)} aria-label="Close">✕</button>
          </div>
          <div className="min-h-0 flex-1 overflow-y-auto px-6 py-5">
            {c?.kind === "query" && <p className="text-sm text-ink-2">This restates the conditions you asked about (“{c.text}”). It is your input, not a claim from the data.</p>}
            {testId && <TestRecord id={testId} />}
            {!testId && c?.kind === "aggregate" && (
              <div data-ready="provenance-list">
                <p className="text-base text-ink">
                  {c.field === "test_id" ? `These are the ${c.rows.length} tests behind this number.` : `This is the ${OP_WORDS[c.op] ?? c.op} of “${vmeta(c.field).label}” across ${c.rows.length} tests.`}
                  {rows && c.field !== "test_id" && c.field !== "burned" && <span className="text-ink-2"> Recomputed here: <span className="mono text-ink">{fmtVar(c.field, recompute(c.op, rows.map((r) => r[c.field])) as number, 4)}</span>.</span>}
                </p>
                <p className="mt-1 text-sm text-ink-3">Select a test to read its full record.</p>
                <ul className="rule-t mt-4">
                  {(rows ?? []).map((r) => (
                    <li key={r.test_id} className="rule-b">
                      <button className="flex w-full items-center gap-4 py-2.5 text-left hover:bg-surface-2" onClick={() => openProv({ ...prov, testId: r.test_id })}>
                        <span className="mono w-28 shrink-0 text-sm text-ink">{r.test_id}</span>
                        <span className="min-w-0 flex-1 text-sm text-ink-2">{c.field === "test_id" || c.field === "burned" ? r.outcome ?? "Outcome not recorded" : fmtVar(c.field, r[c.field], 4)}</span>
                        {r.excluded ? <span className="status flagged">Excluded</span> : (r.flags?.length ?? 0) > 0 ? <span className="status flagged">Warning</span> : null}
                      </button>
                    </li>
                  ))}
                </ul>
                {!rows && <p className="mt-4 text-sm text-ink-3">Loading…</p>}
              </div>
            )}
          </div>
        </aside>
      )}
      <SourceRowViewer />
    </>
  );
}
