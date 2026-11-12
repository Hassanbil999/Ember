"use client";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";
import { get } from "@/lib/api";
import { useUI } from "@/lib/store";
import Passage from "@/components/Passage";
import TopicAnswer, { Grade, GRADE_WHY, Next } from "@/components/TopicAnswer";

function Sentence({ s }: { s: any }) {
  const { openProv, openSource } = useUI();
  const cites = s.citations.filter((c: any) => c.kind !== "query");
  return (
    <p className="lead text-ink">
      {s.text}{" "}
      {cites.map((c: any, i: number) => (
        <button key={i} className="ml-1 align-baseline text-sm text-ink-3 underline decoration-dotted underline-offset-4 hover:text-ink"
          onClick={() => c.kind === "chunk" ? openSource({ doc: c.target.split("#")[0], page: c.page, spans: [c.span], chunk: c.target }) : openProv({ citation: c, label: s.text })}>
          {c.kind === "aggregate" ? `${c.rows.length} tests` : `page ${c.page}`}
        </button>
      ))}
    </p>
  );
}

function Asked({ q }: { q: string }) {
  const role = useUI((s) => s.role);
  const openProv = useUI((s) => s.openProv);
  const [a, setA] = useState<any>(null);
  useEffect(() => { setA(null); get(`/answer?q=${encodeURIComponent(q)}&role=${role}`).then(setA).catch(() => setA({ error: true })); }, [q, role]);
  if (!a) return <div className="mx-auto max-w-[980px] px-8 py-10 text-ink-3">Looking through the evidence…</div>;
  if (a.error) return <div className="mx-auto max-w-[980px] px-8 py-10">The question could not be answered right now.</div>;
  const g = GRADE_WHY[a.grade] ?? GRADE_WHY["No data"];
  return (
    <div className="mx-auto max-w-[980px] px-8 pb-16 pt-8" data-ready="answer">
      <Link href="/" className="text-sm text-ink-3 hover:text-ink">← Start</Link>
      <p className="eyebrow mt-4">You asked</p>
      <h1 className="title mt-2">{a.query}</h1>
      <Grade label={a.grade} tone={g.tone} why={g.why} />
      {a.abstain ? (
        <div className="card mt-6 p-6">
          <p className="lead text-ink">Not covered by available NASA data.</p>
          <p className="mt-2 text-sm text-ink-2">The loaded experiments and reports contain nothing that answers this, so no answer is given.</p>
        </div>
      ) : (
        <>
          <section className="card mt-6 space-y-3 p-6">
            {a.key.map((s: any, i: number) => <Sentence key={i} s={s} />)}
            {a.key.length === 0 && a.sources.slice(0, 1).map((s: any, i: number) => <Sentence key={i} s={s} />)}
          </section>
          {a.numbers.length > 0 && (
            <section className="mt-6 grid grid-cols-2 gap-4 md:grid-cols-3">
              {a.numbers.slice(0, 6).map((x: any, i: number) => (
                <button key={i} className="card card-hover p-4 text-left" onClick={() => x.citation && openProv({ citation: x.citation, label: x.label })} title="Select to see the tests behind this number">
                  <span className="block text-sm text-ink-3">{x.label}</span>
                  <span className="mono mt-1 block text-[26px] leading-8 text-ink">{x.value}<span className="ml-1.5 text-sm text-ink-3">{x.unit}</span></span>
                </button>
              ))}
            </section>
          )}
          {a.passages.length > 0 && (
            <section className="mt-10"><p className="eyebrow">Sources</p>
              <div className="mt-3 grid grid-cols-1 gap-6 md:grid-cols-2">{a.passages.map((p: any) => <Passage key={p.chunk_id} p={p} />)}</div>
            </section>
          )}
        </>
      )}
      {a.caveats.length > 0 && (
        <section className="mt-8 space-y-2">
          {a.caveats.map((c: any) => <p key={c.kind} className="text-sm" style={{ color: c.kind === "partial_gravity" ? "var(--unc)" : c.kind === "demo" ? "var(--warn)" : "var(--text-2)" }}>{c.text}</p>)}
        </section>
      )}
      {a.dropped.length > 0 && <p className="mt-4 text-sm text-ink-3">{a.dropped.length} sentence(s) were removed because their citation could not be verified.</p>}
      <Next items={[{ label: "Test it in the simulator", href: "/lab" }, { label: "Browse the experiments", href: "/explore" }, { label: "More findings", href: "/insights" }]} />
    </div>
  );
}

function Inner() {
  const sp = useSearchParams();
  const topic = sp.get("topic"), q = sp.get("q");
  if (topic) return <TopicAnswer key={topic} id={topic} material={sp.get("material")} />;
  if (q) return <Asked q={q} />;
  return <div className="mx-auto max-w-[980px] px-8 py-10">Ask a question from the <Link className="underline" href="/">start page</Link>.</div>;
}

export default function AnswerPage() {
  return <Suspense><Inner /></Suspense>;
}
