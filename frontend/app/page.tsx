"use client";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { get } from "@/lib/api";
import FlameScene from "@/components/lab/FlameScene";
import type { FlameState } from "@/components/lab/HeroFlame";
import TopicAnswer from "@/components/TopicAnswer";

/* Home: one sentence, one input, four starting points, and one flame.
   The flame is the simulator's own scene. Pointing at a starting point sets the flame to that
   place, so the list is illustrated by the subject itself instead of by four separate drawings. */

type Scene = { state: FlameState; note: string };
const REST: Scene = {
  state: { mode: "droplet", p: 1, heat: 0.55, o2: 0.21, flow: 0, gravity: 0, known: true, drop: 0.7 },
  note: "A fuel droplet burning in microgravity. With no up, the flame is a sphere.",
};
const SCENES: Record<string, Scene> = {
  "moon-base": {
    state: { mode: "solid", p: 0.9, heat: 0.6, o2: 0.34, flow: 0.08, gravity: 0.165, known: true },
    note: "Lunar gravity pulls a flame part-way upright. No test in this atlas has burned there.",
  },
  "iss-cabin": {
    state: { mode: "solid", p: 0.8, heat: 0.4, o2: 0.21, flow: 0.3, gravity: 0, known: true },
    note: "On the station, a flame on a solid is a low dome that leans with the cabin airflow.",
  },
  microgravity: {
    state: { mode: "solid", p: 1, heat: 0.7, o2: 0.21, flow: 0, gravity: 1, known: true },
    note: "On Earth, hot gas rises and stretches the flame upward. Take gravity away and it stops.",
  },
  untested: {
    state: { mode: "solid", p: 0, heat: 0.2, o2: 0.21, flow: 0, gravity: 0, known: false },
    note: "Where no test has been run, the atlas draws no flame.",
  },
  trade: {
    state: { mode: "solid", p: 1, heat: 0.85, o2: 0.34, flow: 0.12, gravity: 0, known: true },
    note: "Thinner air with more oxygen shortens spacewalk preparation and feeds a stronger flame.",
  },
};

const STARTS = [
  { id: "moon-base", title: "Moon base fire risk", text: "Would a fire keep burning in the air planned for a lunar habitat?" },
  { id: "iss-cabin", title: "ISS cabin", text: "How materials burn in the air astronauts breathe today." },
  { id: "microgravity", title: "How fire behaves in microgravity", text: "What changes when a flame has no up." },
  { id: "untested", title: "What NASA hasn't tested yet", text: "Where the experiments stop and the guessing starts." },
];

export default function Home() {
  const router = useRouter();
  const input = useRef<HTMLInputElement>(null);
  // A start shows its answer in the same frame (code and data are already loaded); the route
  // change follows in the background and lands on the identical screen.
  const [picked, setPicked] = useState<string | null>(null);
  const [at, setAt] = useState<string | null>(null);
  // the flame is mounted after the words have painted, so it never delays the first screen
  const [lit, setLit] = useState(false);
  useEffect(() => {
    const a = setTimeout(() => setLit(true), 60);
    // warm the four answer screens while the reader is still reading (prefetch the next likely view)
    const b = setTimeout(() => { STARTS.forEach((s) => { get(`/topic/${s.id}`).catch(() => {}); router.prefetch(`/answer?topic=${s.id}`); }); }, 150);
    return () => { clearTimeout(a); clearTimeout(b); };
  }, [router]);
  const ask = (e: React.FormEvent) => {
    e.preventDefault();
    const q = input.current?.value.trim();
    if (q) router.push(`/answer?q=${encodeURIComponent(q)}`);
  };
  if (picked) return <TopicAnswer id={picked} material={null} />;
  const scene = (at && SCENES[at]) || REST;
  const point = (id: string) => ({ onMouseEnter: () => setAt(id), onMouseLeave: () => setAt(null), onFocus: () => setAt(id), onBlur: () => setAt(null) });
  return (
    <div className="mx-auto flex min-h-full max-w-[1240px] flex-col justify-center px-8 py-5" data-ready="home">
      <div className="grid items-stretch gap-x-12 gap-y-6 lg:grid-cols-[minmax(0,11fr)_minmax(0,9fr)]">
        <div className="flex min-w-0 flex-col">
          <h1 className="display" style={{ fontSize: "clamp(30px, 2.7vw, 42px)" }}>What NASA knows about fire in space, and what it doesn't.</h1>
          <p className="lead mt-3 text-ink-2">Ask a question, see the evidence, and see exactly where the data ends.</p>

          <form onSubmit={ask} role="search" className="field mt-5 flex h-14 items-center gap-3 rounded-md pl-5 pr-2" style={{ background: "var(--surface)", border: "1px solid var(--line-strong)" }}>
            <svg width="22" height="22" viewBox="0 0 16 16" aria-hidden className="shrink-0 text-ink-3"><circle cx="7" cy="7" r="5" fill="none" stroke="currentColor" strokeWidth="1.4" /><path d="M11 11l3.5 3.5" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" /></svg>
            <input ref={input} type="search" autoFocus aria-label="Ask a question" placeholder="Is PMMA flammable at 30% oxygen?"
              className="bare h-full min-w-0 flex-1 text-ink placeholder:text-ink-3" style={{ fontSize: 18 }} />
            <button type="submit" className="btn primary h-10 px-6 text-base">Ask</button>
          </form>

          <ul className="mt-4 rule-b">
            {STARTS.map((s) => (
              <li key={s.id}>
                <Link href={`/answer?topic=${s.id}`} data-start={s.id} {...point(s.id)} className="start rule-t block py-2.5"
                  onClick={(e) => { if (e.metaKey || e.ctrlKey || e.shiftKey || e.button !== 0) return; e.preventDefault(); setPicked(s.id); router.push(`/answer?topic=${s.id}`); }}>
                  <h2 className="text-xl font-semibold leading-snug text-ink">{s.title}</h2>
                  <p className="mt-0.5 text-sm text-ink-2">{s.text}</p>
                </Link>
              </li>
            ))}
          </ul>
        </div>

        <div className="flex min-w-0 flex-col">
          <figure className="relative min-h-[300px] flex-1 overflow-hidden rounded-md" data-theme="void" data-home-flame style={{ background: "#04060B", border: "1px solid var(--line)" }}>
            <div className="absolute inset-0">{lit && <FlameScene state={scene.state} />}</div>
            <figcaption className="absolute inset-x-0 bottom-0 flex flex-wrap items-end justify-between gap-x-6 gap-y-3 p-5" style={{ background: "linear-gradient(transparent, rgba(4,6,11,.88) 55%)" }}>
              <p className="max-w-[40ch] text-sm text-ink-2" data-home-note>{scene.note} <span className="text-ink-3">Illustration.</span></p>
              <Link href="/lab" className="btn h-9" style={{ background: "rgba(5,7,12,.6)" }}>Set the conditions yourself</Link>
            </figcaption>
          </figure>
          <Link href="/trade" data-start="trade" {...point("trade")} className="start rule-b block py-3">
            <h2 className="text-xl font-semibold leading-snug text-ink">What air should the crew breathe?</h2>
            <p className="mt-0.5 text-sm text-ink-2">Breathing, spacewalks and flammability on one map, and where the tests run out.</p>
          </Link>
        </div>
      </div>
    </div>
  );
}
