"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import { get } from "@/lib/api";
import { useUI } from "@/lib/store";
import Passage from "@/components/Passage";
import { Visual } from "@/components/Viz";

/* Answer screen: key finding, one visual, evidence grade, sources; then three columns that are
   never blended: measured / inferred / never tested. Deeper tools are offered last, as next steps. */

export const TONE: Record<string, string> = { flame: "var(--flame)", ext: "var(--ext)", unc: "var(--unc)", warn: "var(--warn)", nodata: "var(--nodata)", text: "var(--text)", "text-2": "var(--text-2)" };
export const GRADE_WHY: Record<string, { tone: string; why: string }> = {
  Measured: { tone: "text", why: "Real test data at these conditions." },
  "Close conditions": { tone: "warn", why: "The nearest real tests, not the exact conditions asked about." },
  Documented: { tone: "text-2", why: "Report text only; no matching test rows." },
  "Not tested": { tone: "warn", why: "No real test was run at these conditions. The answer says where testing stopped." },
  "No data": { tone: "nodata", why: "Not covered by the loaded data." },
};

export function Grade({ label, tone, why }: { label: string; tone: string; why: string }) {
  return (
    <p className="mt-5 flex flex-wrap items-center gap-x-3 gap-y-1 text-sm" data-grade={label}>
      <span className="text-ink-3">Evidence</span>
      <span className="inline-flex h-7 items-center rounded-full px-3 text-sm font-semibold" style={{ color: TONE[tone], border: `1.5px solid ${TONE[tone]}` }}>{label}</span>
      <span className="text-ink-2">{why}</span>
    </p>
  );
}

function Column({ title, tone, block, k }: { title: string; tone: string; block: any; k: string }) {
  const openProv = useUI((s) => s.openProv);
  return (
    <section className="card p-5" style={{ borderTop: `3px solid ${TONE[tone]}` }} data-column={k}>
      <h2 className="text-lg font-semibold tracking-tight text-ink">{title}</h2>
      <p className="mt-1 text-sm text-ink-2">{block.summary}</p>
      <ul className="mt-3 space-y-2.5">
        {block.items.map((it: any, i: number) => (
          <li key={i} className="flex gap-2.5 text-sm text-ink">
            <span className="mt-[7px] h-2 w-2 shrink-0 rounded-full" style={{ background: TONE[it.tone ?? tone] }} />
            <span>{it.text}{it.citation && <> <button className="text-ink-3 underline decoration-dotted underline-offset-4 hover:text-ink" onClick={() => openProv({ citation: it.citation, label: it.text })}>see the tests</button></>}</span>
          </li>
        ))}
        {block.items.length === 0 && <li className="text-sm text-ink-3">Nothing to list.</li>}
      </ul>
    </section>
  );
}

/* Evidence from outside NASA: its own card, dashed and labelled, never merged with the NASA columns or the grade. */
function Outside({ o }: { o: any }) {
  return (
    <section className="card mt-6 p-5" style={{ border: "1.5px dashed var(--text-2)" }} data-outside>
      <p className="eyebrow">Outside NASA · {o.label}</p>
      <p className="mt-2 text-base font-medium text-ink">{o.finding}</p>
      <p className="mt-1 text-sm text-ink-2">{o.summary}</p>
      <div className="mt-4 overflow-x-auto">
        <table className="text-sm">
          <caption className="sr-only">Measured flame-spread rates over {o.material}</caption>
          <thead><tr className="text-left text-ink-3">
            <th className="pb-1 pr-6 font-normal">Test</th><th className="pb-1 pr-6 font-normal">Oxygen</th>
            <th className="pb-1 pr-6 font-normal">Pressure</th><th className="pb-1 pr-6 font-normal">Air against the flame</th>
            <th className="pb-1 font-normal">Flame spread</th>
          </tr></thead>
          <tbody>{o.points.map((p: any) => (
            <tr key={p.id} className={p.id === o.near_id ? "font-semibold text-ink" : "text-ink-2"}>
              <td className="mono pr-6">{p.id}</td><td className="mono pr-6">{(p.o2_frac * 100).toFixed(1)}%</td>
              <td className="mono pr-6">{p.pressure_kpa.toFixed(0)} kPa</td><td className="mono pr-6">{(p.flow_mm_s / 10).toFixed(0)} cm/s</td>
              <td className="mono">{p.spread_mm_s.toFixed(2)} ± {p.spread_std.toFixed(2)} mm/s</td>
            </tr>))}
          </tbody>
        </table>
      </div>
      <ul className="mt-4 space-y-1.5">{o.limits.map((l: string) => <li key={l} className="flex gap-2.5 text-sm text-ink-2"><span className="mt-[7px] h-2 w-2 shrink-0 rounded-full" style={{ background: TONE.warn }} />{l}</li>)}</ul>
      <p className="mt-4 text-xs text-ink-3">
        {o.citation} Funded by the {o.funding}. Data: <a className="underline" href={o.url} target="_blank" rel="noreferrer">doi:{o.doi}</a>,{" "}
        paper: <a className="underline" href={`https://doi.org/${o.paper_doi}`} target="_blank" rel="noreferrer">doi:{o.paper_doi}</a>. License {o.license}.
      </p>
    </section>
  );
}

export function Next({ items }: { items: { label: string; href: string }[] }) {
  return (
    <section className="mt-10">
      <p className="eyebrow">Go deeper</p>
      <div className="mt-3 flex flex-wrap gap-3">{items.map((n, i) => <Link key={n.href + i} href={n.href} className={`btn h-11 px-5 ${i === 0 ? "primary" : ""}`}>{n.label}</Link>)}</div>
    </section>
  );
}

export default function TopicAnswer({ id, material: initial }: { id: string; material: string | null }) {
  // the chosen material is local state: switching it must not wait for a route change
  const [material, setMaterial] = useState<string | null>(initial);
  const [t, setT] = useState<any>(null);
  useEffect(() => { get(`/topic/${id}${material ? `?material=${encodeURIComponent(material)}` : ""}`).then(setT).catch(() => setT({ error: true })); }, [id, material]);
  // the per-material answers are one click away: fetch them before they are asked for
  useEffect(() => { (t?.materials ?? []).forEach((m: any) => get(`/topic/${id}?material=${encodeURIComponent(m.material)}`).catch(() => {})); }, [t?.id, id]); // eslint-disable-line react-hooks/exhaustive-deps
  if (!t) return <div className="mx-auto max-w-[1240px] px-8 py-10 text-ink-3">Loading…</div>;
  if (t.error) return <div className="mx-auto max-w-[1240px] px-8 py-10">This starting point does not exist. <Link className="underline" href="/">Back to start</Link></div>;
  const pick = (m: string | null) => {
    setMaterial(m);
    window.history.replaceState(null, "", `/answer?topic=${id}${m ? `&material=${encodeURIComponent(m)}` : ""}`);
  };
  return (
    <div className="mx-auto max-w-[1240px] px-8 pb-16 pt-8" data-ready="answer" data-topic={id} data-material-shown={t.material ?? ""}>
      <Link href="/" className="text-sm text-ink-3 hover:text-ink">← Start</Link>
      <p className="eyebrow mt-4">{t.question}</p>
      <h1 className="title mt-2 max-w-[40ch]" data-finding>{t.finding}</h1>
      <Grade {...t.grade} />

      {t.materials.length > 0 && (
        <div className="mt-6 flex flex-wrap items-center gap-2.5" role="group" aria-label="Choose a material">
          <span className="mr-1 text-sm text-ink-3">Material</span>
          <button className="chip" aria-pressed={!t.material} onClick={() => pick(null)}>All tested</button>
          {t.materials.map((m: any) => (
            <button key={m.material} className="chip" aria-pressed={t.material === m.material} data-material={m.material} onClick={() => pick(m.material)}>
              <span className="h-2.5 w-2.5 rounded-full" style={{ background: TONE[m.tone] }} />{m.material}
            </button>
          ))}
        </div>
      )}

      <div className="mt-6 grid grid-cols-1 gap-6 lg:grid-cols-[minmax(0,1.25fr)_minmax(0,1fr)]">
        <figure className="card p-6">
          <Visual v={t.visual} />
          {t.visual.caption && <figcaption className="mt-3 text-sm text-ink-2">{t.visual.caption}</figcaption>}
        </figure>
        <div className="space-y-4">
          <Column k="measured" title="What NASA measured" tone="text" block={t.measured} />
          <Column k="inferred" title="What the model infers" tone="unc" block={t.inferred} />
          <Column k="untested" title="What was never tested" tone="warn" block={t.untested} />
        </div>
      </div>

      {t.outside && <Outside o={t.outside} />}

      {t.sources.length > 0 && (
        <section className="mt-10">
          <p className="eyebrow">Sources</p>
          <div className="mt-3 grid grid-cols-1 gap-6 md:grid-cols-2">{t.sources.map((p: any) => <Passage key={p.chunk_id} p={p} />)}</div>
        </section>
      )}
      <Next items={t.next} />
    </div>
  );
}

