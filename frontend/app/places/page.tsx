"use client";
import Link from "next/link";
import { Suspense, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import { get } from "@/lib/api";
import { useUI } from "@/lib/store";
import FlameScene from "@/components/lab/FlameScene";

/* Rank the experiments for one place people live or will live. One flame (the simulator's own
   scene, set to that place), one sentence, one ranked table. The score is four parts of 0-3 and
   each part states its reason, so a reader can check the ranking instead of trusting it. */

const PLACES = [
  { id: "iss", label: "ISS today" }, { id: "spacecraft", label: "Crew spacecraft" }, { id: "moon_base", label: "Moon base" },
  { id: "rover", label: "Pressurized rover" }, { id: "mars", label: "Mars base" }, { id: "earth", label: "Back on Earth" },
];

function Pips({ part, label }: { part: any; label: string }) {
  const word = part.unknown ? "not known" : part.demo ? "demo data" : `${part.score} of 3`;
  return (
    <span className="inline-flex items-center gap-1" role="img" aria-label={`${label}: ${word}`} title={part.why}>
      {[0, 1, 2].map((i) => (
        <span key={i} className="h-3 w-3 rounded-[2px]" style={i < part.score
          ? { background: part.unknown || part.demo ? "transparent" : "var(--text)", border: part.unknown || part.demo ? "1.5px dashed var(--text-3)" : "1.5px solid var(--text)" }
          : { border: "1.5px solid var(--line-strong)" }} />
      ))}
    </span>
  );
}

function Source({ s }: { s: any }) {
  if (!s) return null;
  return <a href={s.url} target="_blank" rel="noreferrer" className="text-ink-3 underline decoration-dotted underline-offset-4 hover:text-ink">{s.label}</a>;
}

function Places() {
  const params = useSearchParams();
  const openProv = useUI((s) => s.openProv);
  const [pid, setPid] = useState(params.get("place") && PLACES.some((p) => p.id === params.get("place")) ? params.get("place")! : "moon_base");
  const [d, setD] = useState<any>(null);
  const [open, setOpen] = useState<string | null>(null);
  const [all, setAll] = useState(false);
  useEffect(() => { get(`/places/${pid}`).then(setD).catch(() => {}); }, [pid]);
  // the other places are one click away: fetch them before they are asked for
  useEffect(() => { const t = setTimeout(() => PLACES.forEach((p) => get(`/places/${p.id}`).catch(() => {})), 200); return () => clearTimeout(t); }, []);
  const pick = (id: string) => { setPid(id); setOpen(null); window.history.replaceState(null, "", `/places?place=${id}`); };
  if (!d) return <div className="mx-auto max-w-[1240px] px-8 py-10 text-ink-3">Loading…</div>;
  const rows = all ? d.rows : d.rows.slice(0, 7);
  return (
    <div className="mx-auto max-w-[1240px] px-8 pb-16 pt-6" data-ready="places" data-place={d.id}>
      <div className="flex flex-wrap items-center gap-2.5" role="group" aria-label="Choose a place">
        <span className="mr-1 text-sm text-ink-3">Which experiments matter for</span>
        {PLACES.map((p) => <button key={p.id} className="chip" aria-pressed={pid === p.id} data-place-chip={p.id} onClick={() => pick(p.id)}>{p.label}</button>)}
      </div>

      <div className="mt-6 grid grid-cols-1 gap-x-10 gap-y-8 lg:grid-cols-[minmax(0,5fr)_minmax(0,8fr)]">
        <div className="min-w-0">
          <figure className="relative h-[280px] overflow-hidden rounded-md" data-theme="void" style={{ background: "#04060B", border: "1px solid var(--line)" }}>
            <div className="absolute inset-0"><FlameScene state={d.flame} /></div>
            <figcaption className="absolute inset-x-0 bottom-0 p-4 text-sm text-ink-2" style={{ background: "linear-gradient(transparent, rgba(4,6,11,.88) 60%)" }}>
              <span className="text-ink">{d.air.text}</span>{d.air.assumed ? " (assumed)" : ""}, {d.gravity.toLowerCase().startsWith("micro") ? "microgravity" : d.gravity}. <span className="text-ink-3">Illustration.</span>
            </figcaption>
          </figure>
          {d.air.note && <p className="mt-2 text-sm text-ink-3">Air: {d.air.note}. <Source s={d.air.source} /></p>}
          <Link href={`/lab?preset=${d.preset}`} className="btn mt-3 h-9">Simulate a fire here</Link>

          {d.history.length > 0 && (
            <section className="mt-7" data-history>
              <h2 className="text-lg font-semibold text-ink">What has already gone wrong</h2>
              {d.history.map((h: any) => (
                <div key={h.title} className="rule-t mt-3 pt-3">
                  <h3 className="text-base font-semibold text-ink">{h.title}</h3>
                  <p className="mt-1 text-sm text-ink-2">{h.text}</p>
                  <p className="mt-1.5 text-sm text-ink">{h.lesson}</p>
                  <p className="mt-1 text-sm"><Source s={h.source} /></p>
                </div>
              ))}
            </section>
          )}
          {d.spinoffs.length > 0 && (
            <section className="mt-7" data-spinoffs>
              <h2 className="text-lg font-semibold text-ink">What has already come home</h2>
              {d.spinoffs.map((h: any) => (
                <div key={h.title} className="rule-t mt-3 pt-3">
                  <h3 className="text-base font-semibold text-ink">{h.title}</h3>
                  <p className="mt-1 text-sm text-ink-2">{h.text}</p>
                  <p className="mt-1 text-sm"><Source s={h.source} /></p>
                </div>
              ))}
            </section>
          )}
        </div>

        <div className="min-w-0">
          <h1 className="title max-w-[36ch]" style={{ fontSize: 24 }} data-reading>{d.reading}</h1>
          <p className="mt-3 flex flex-wrap gap-x-6 gap-y-1 text-sm text-ink-2">
            {d.best.map((b: any) => <span key={b.goal}>Best for {b.goal}: <button className="font-semibold text-ink underline decoration-dotted underline-offset-4" onClick={() => setOpen(d.rows.find((r: any) => r.label === b.label)?.id)}>{b.label}</button></span>)}
          </p>

          <div className="mt-5 overflow-x-auto">
            <table className="w-full min-w-[640px] border-collapse text-sm" data-rank-table>
              <thead>
                <tr className="text-left text-ink-3">
                  <th className="rule-b w-8 py-2 font-normal" scope="col"><span className="sr-only">Rank</span></th>
                  <th className="rule-b py-2 font-normal" scope="col">Experiment</th>
                  {d.parts.map((p: any) => <th key={p.key} className="rule-b whitespace-nowrap px-2 py-2 font-normal" scope="col">{p.label}</th>)}
                  <th className="rule-b whitespace-nowrap py-2 text-right font-normal" scope="col">Score</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((r: any) => {
                  const on = open === r.id;
                  return [
                    <tr key={r.id} data-rank-row={r.label} className="cursor-pointer hover:bg-surface-2" onClick={() => setOpen(on ? null : r.id)}>
                      <td className="rule-b num py-2.5 text-ink-3">{r.rank}</td>
                      <td className="rule-b py-2.5 pr-3">
                        <button className="text-left" aria-expanded={on}><span className="text-base font-semibold text-ink">{r.label}</span><span className="block text-ink-3">{r.burns}</span></button>
                      </td>
                      {d.parts.map((p: any) => <td key={p.key} className="rule-b px-2 py-2.5"><Pips part={r.parts[p.key]} label={p.label} /></td>)}
                      <td className="rule-b num py-2.5 text-right text-base text-ink">{r.score}<span className="text-ink-3"> / {d.max}</span></td>
                    </tr>,
                    on && (
                      <tr key={r.id + "-why"} data-rank-why>
                        <td className="rule-b" />
                        <td className="rule-b pb-4 pt-1" colSpan={d.parts.length + 2}>
                          <p className="text-ink-2">{r.name}. {r.objectives}</p>
                          <dl className="mt-3 grid grid-cols-[120px_1fr] gap-x-4 gap-y-2">
                            {d.parts.map((p: any) => {
                              const part = r.parts[p.key];
                              return [
                                <dt key={p.key} className="text-ink-3">{p.label}</dt>,
                                <dd key={p.key + "d"} className="text-ink">{part.why}{part.source && <> <Source s={part.source} /></>}
                                  {p.key === "air" && r.near_ids.length > 0 && <> <button className="text-ink-3 underline decoration-dotted underline-offset-4 hover:text-ink" onClick={() => openProv({ citation: { kind: "aggregate", op: "count", field: "burned", rows: r.near_ids }, label: `${r.label} tests in ${d.label} air` })}>see the tests</button></>}
                                </dd>,
                              ];
                            })}
                          </dl>
                          <Link href={`/explore?open=${encodeURIComponent(r.id)}`} className="btn mt-3 h-9">Open {r.label} in Explore</Link>
                        </td>
                      </tr>
                    ),
                  ];
                })}
              </tbody>
            </table>
          </div>
          {d.rows.length > 7 && <button className="btn ghost mt-2 h-9" onClick={() => setAll(!all)} data-rank-all>{all ? "Show the top 7" : `Show all ${d.rows.length}`}</button>}
          <p className="mt-3 max-w-[70ch] text-sm text-ink-3">Each column is scored 0 to 3 by a written rule, not by a model. Dashed boxes mean the atlas does not know or holds only demo data. Select a row for the reasons.</p>

          <section className="mt-7" data-gaps>
            <h2 className="text-lg font-semibold text-ink">What was never tested for this place</h2>
            <ul className="mt-2 space-y-2">
              {d.gaps.map((g: any, i: number) => (
                <li key={i} className="flex gap-2.5 text-sm text-ink">
                  <span className="mt-[7px] h-2 w-2 shrink-0 rounded-full" style={{ background: "var(--warn)" }} />
                  <span>{g.text}{g.source && <> <Source s={g.source} /></>}{g.citation && <> <button className="text-ink-3 underline decoration-dotted underline-offset-4 hover:text-ink" onClick={() => openProv({ citation: g.citation, label: `Tests in ${d.label} air` })}>see the tests</button></>}</span>
                </li>
              ))}
              {d.gaps.length === 0 && <li className="text-sm text-ink-3">Nothing to list.</li>}
            </ul>
          </section>
        </div>
      </div>
    </div>
  );
}

export default function Page() {
  return <Suspense fallback={null}><Places /></Suspense>;
}
