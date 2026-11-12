"use client";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { get } from "@/lib/api";
import { FlameGlyph } from "@/components/Viz";
import TopicAnswer from "@/components/TopicAnswer";

/* Home: one sentence, one input, four starting points (Hick: few choices; one focal point). */

function MoonArt() {
  return (
    <svg viewBox="0 0 200 120" className="h-full w-full" aria-hidden>
      <defs>
        <radialGradient id="moon" cx="38%" cy="34%"><stop offset="0%" stopColor="#D9DEE8" /><stop offset="100%" stopColor="#5B6577" /></radialGradient>
        <radialGradient id="mglow"><stop offset="0%" stopColor="#FFB04A" stopOpacity=".9" /><stop offset="100%" stopColor="#FF7A1A" stopOpacity="0" /></radialGradient>
      </defs>
      <circle cx="100" cy="150" r="118" fill="url(#moon)" />
      <circle cx="62" cy="86" r="11" fill="#000" opacity=".16" /><circle cx="128" cy="62" r="7" fill="#000" opacity=".14" /><circle cx="150" cy="98" r="14" fill="#000" opacity=".12" />
      <path d="M82 44 a18 18 0 0 1 36 0 v0 h-36 z" fill="var(--surface-3)" stroke="var(--text-3)" strokeWidth="1.5" />
      <circle cx="100" cy="36" r="13" fill="url(#mglow)" /><circle cx="100" cy="36" r="3" fill="#FFF3D6" />
    </svg>
  );
}
function CabinArt() {
  return (
    <svg viewBox="0 0 200 120" className="h-full w-full" aria-hidden>
      <rect x="22" y="22" width="156" height="76" rx="38" fill="var(--surface-3)" stroke="var(--text-3)" strokeWidth="1.5" />
      {[44, 60, 76].map((y) => <path key={y} d={`M40 ${y} C 70 ${y - 8}, 96 ${y + 8}, 150 ${y}`} fill="none" stroke="var(--ext)" strokeWidth="1.5" strokeDasharray="2 7" strokeLinecap="round" opacity=".8" />)}
      <path d="M150 54 l10 6 -10 6" fill="none" stroke="var(--ext)" strokeWidth="1.5" strokeLinecap="round" />
      <g transform="translate(70 30) scale(.5)"><FlameGlyph kind="micro" lively={false} /></g>
    </svg>
  );
}
function PairArt() {
  return (
    <div className="flex h-full items-center justify-center gap-2">
      <FlameGlyph kind="earth" size={92} /><span className="text-xl text-ink-3">vs</span><FlameGlyph kind="micro" size={92} />
    </div>
  );
}
function GapArt() {
  const dots = [];
  for (let r = 0; r < 5; r++) for (let c = 0; c < 9; c++) dots.push({ r, c, gap: c >= 5 && r <= 2 });
  return (
    <svg viewBox="0 0 200 120" className="h-full w-full" aria-hidden>
      {dots.map((d) => d.gap ? null : <circle key={`${d.r}-${d.c}`} cx={28 + d.c * 18} cy={24 + d.r * 18} r={(d.r * 7 + d.c * 3) % 5 === 0 ? 2.5 : 4.5} fill="var(--text-2)" />)}
      <rect x="109" y="13" width="74" height="58" rx="6" fill="var(--warn-soft)" stroke="var(--warn)" strokeWidth="1.5" strokeDasharray="5 4" className="gap-glow" />
      <text x="146" y="52" textAnchor="middle" fontSize="30" fontWeight="600" fill="var(--warn)">?</text>
    </svg>
  );
}

const STARTS = [
  { id: "moon-base", title: "Moon base fire risk", text: "Would a fire keep burning in the air planned for a lunar habitat?", art: <MoonArt /> },
  { id: "iss-cabin", title: "ISS cabin", text: "How materials burn in the air astronauts breathe today.", art: <CabinArt /> },
  { id: "microgravity", title: "How fire behaves in microgravity", text: "What changes when a flame has no up.", art: <PairArt /> },
  { id: "untested", title: "What NASA hasn't tested yet", text: "Where the experiments stop and the guessing starts.", art: <GapArt /> },
];

export default function Home() {
  const router = useRouter();
  const input = useRef<HTMLInputElement>(null);
  // A start card shows its answer in the same frame (code and data are already loaded); the route
  // change follows in the background and lands on the identical screen.
  const [picked, setPicked] = useState<string | null>(null);
  // warm the four answer screens while the reader is still reading (prefetch the next likely view)
  useEffect(() => {
    const t = setTimeout(() => { STARTS.forEach((s) => { get(`/topic/${s.id}`).catch(() => {}); router.prefetch(`/answer?topic=${s.id}`); }); }, 150);
    return () => clearTimeout(t);
  }, [router]);
  const ask = (e: React.FormEvent) => {
    e.preventDefault();
    const q = input.current?.value.trim();
    if (q) router.push(`/answer?q=${encodeURIComponent(q)}`);
  };
  if (picked) return <TopicAnswer id={picked} material={null} />;
  return (
    <div className="mx-auto flex min-h-full max-w-[1240px] flex-col justify-center px-8 py-8" data-ready="home">
      <h1 className="display max-w-[24ch]" style={{ fontSize: "clamp(32px, 3.6vw, 46px)" }}>What NASA knows about <span className="text-flame">fire in space</span>, and what it doesn't.</h1>
      <p className="lead mt-3 max-w-[62ch] text-ink-2">NASA's microgravity combustion experiments in one place: ask a question, see the evidence, and see exactly where the data ends.</p>

      <form onSubmit={ask} role="search" className="field mt-6 flex h-14 max-w-[820px] items-center gap-3 rounded-md pl-5 pr-2" style={{ background: "var(--surface)", border: "1px solid var(--line-strong)" }}>
        <svg width="22" height="22" viewBox="0 0 16 16" aria-hidden className="shrink-0 text-ink-3"><circle cx="7" cy="7" r="5" fill="none" stroke="currentColor" strokeWidth="1.4" /><path d="M11 11l3.5 3.5" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" /></svg>
        <input ref={input} type="search" autoFocus aria-label="Ask a question" placeholder="Ask anything, for example: is PMMA flammable at 30% oxygen?"
          className="bare h-full min-w-0 flex-1 text-ink placeholder:text-ink-3" style={{ fontSize: 18 }} />
        <button type="submit" className="btn primary h-10 px-6 text-base">Ask</button>
      </form>

      <p className="eyebrow mt-6">Or start here</p>
      <div className="mt-3 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {STARTS.map((s) => (
          <Link key={s.id} href={`/answer?topic=${s.id}`} data-start={s.id} className="card card-hover group flex flex-col overflow-hidden"
            onClick={(e) => { if (e.metaKey || e.ctrlKey || e.shiftKey || e.button !== 0) return; e.preventDefault(); setPicked(s.id); router.push(`/answer?topic=${s.id}`); }}>
            <div className="h-[104px] p-3" style={{ background: "var(--surface-2)" }}>{s.art}</div>
            <div className="flex flex-1 flex-col p-4">
              <h2 className="text-xl font-semibold leading-snug tracking-tight text-ink">{s.title}</h2>
              <p className="mt-1.5 flex-1 text-sm text-ink-2">{s.text}</p>
              <span className="mt-3 text-sm font-medium text-flame">See the answer <span aria-hidden className="inline-block transition-transform group-hover:translate-x-1">→</span></span>
            </div>
          </Link>
        ))}
      </div>

      <Link href="/trade" data-start="trade" className="card card-hover group mt-4 flex flex-wrap items-center gap-x-8 gap-y-2 px-6 py-4" style={{ borderColor: "var(--flame)" }}>
        <div className="min-w-0 flex-1">
          <h2 className="text-xl font-semibold tracking-tight text-ink">What air should the crew breathe?</h2>
          <p className="mt-1 text-sm text-ink-2">Thin, oxygen-rich air saves hours before every spacewalk and feeds every fire. See breathing, spacewalks and flammability on one map, and where the tests run out.</p>
        </div>
        <span className="text-sm font-medium text-flame">Open the atmosphere trade <span aria-hidden className="inline-block transition-transform group-hover:translate-x-1">→</span></span>
      </Link>
    </div>
  );
}
