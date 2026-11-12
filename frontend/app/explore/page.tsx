"use client";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useMemo, useState } from "react";
import { get } from "@/lib/api";
import { useSize } from "@/lib/chart";
import { useUI } from "@/lib/store";
import Passage from "@/components/Passage";

/* Explore: at most ~15 nodes on screen. Experiments with test data are always shown; the rest are
   folded into one cluster per group that opens on click. Positions come from a slot grid, so two
   labels can never share space, and nothing is simulated or recomputed while the pointer moves. */

type Inv = { id: string; label: string; name: string; pillars: string[]; burns: string; fuel_phase: string; platform: string; hardware: string; years: number[] | null; n_tests: number; objectives: string };
type Node = { id: string; kind: "inv" | "cluster"; label: string; sub: string; group: string; r: number; inv?: Inv; members?: string[]; x: number; y: number };
type Grouping = "burns" | "goal" | "era";

const GOAL_COLOR: Record<string, string> = { prevention: "var(--prevention)", detection: "var(--detection)", suppression: "var(--suppression)" };
const GOAL_WORD: Record<string, string> = { prevention: "Preventing fire", detection: "Detecting fire", suppression: "Putting fire out" };
const VIEWS: [Grouping, string][] = [["burns", "What burns"], ["goal", "Safety goal"], ["era", "When"]];
const CELL_W = 176, CELL_H = 196, HEAD = 64, MAX_NODES = 15;

function layout(data: any, grouping: Grouping, open: string | null, W: number, H: number) {
  const byId: Record<string, Inv> = Object.fromEntries(data.investigations.map((i: Inv) => [i.id, i]));
  const maxTests = Math.max(1, ...data.investigations.map((i: Inv) => i.n_tests));
  // one home group per experiment (an experiment with two safety goals lives under its first)
  const groups = data.groupings[grouping].map((g: any) => ({
    ...g, members: g.members.filter((id: string) => grouping !== "goal" || `goal:${byId[id].pillars[0]}` === g.id),
  })).filter((g: any) => g.members.length);
  const build = (collapseData: boolean) => groups.map((g: any) => {
    const nodes: Omit<Node, "x" | "y">[] = [];
    const inv = (id: string) => {
      const i = byId[id];
      nodes.push({ id, kind: "inv", label: i.label, sub: i.n_tests ? `${i.n_tests} tests` : "no test data yet", group: g.id, inv: i, r: i.n_tests ? 34 + 30 * Math.sqrt(i.n_tests / maxTests) : 24 });
    };
    if (g.id === open) g.members.forEach(inv);
    else {
      const shown = collapseData ? [] : g.members.filter((id: string) => byId[id].n_tests > 0);
      const rest = g.members.filter((id: string) => !shown.includes(id));
      shown.forEach(inv);
      if (rest.length === 1) inv(rest[0]);
      else if (rest.length > 1) nodes.push({ id: `cluster:${g.id}`, kind: "cluster", label: `${rest.length} ${shown.length ? "more" : "experiments"}`, sub: "select to open", group: g.id, members: rest, r: 36 });
    }
    return { ...g, nodes };
  });
  let bands = build(false);
  if (bands.reduce((n: number, b: any) => n + b.nodes.length, 0) > MAX_NODES) bands = build(true);

  const total = bands.reduce((n: number, b: any) => n + b.nodes.length, 0);
  const totalCols = Math.max(bands.length, Math.floor(W / CELL_W));
  let cols = bands.map((b: any) => Math.max(1, Math.round((b.nodes.length / total) * totalCols)));
  while (cols.reduce((a: number, b: number) => a + b, 0) > totalCols) cols[cols.indexOf(Math.max(...cols))]--;
  const used = cols.reduce((a: number, b: number) => a + b, 0);
  const cw = W / used;                                    // widen cells to fill the screen
  const rowsMax = Math.max(...bands.map((b: any, i: number) => Math.ceil(b.nodes.length / cols[i])));
  const ch = Math.max(CELL_H, Math.min(240, (H - HEAD) / rowsMax));
  const height = Math.max(H, HEAD + rowsMax * ch);
  const nodes: Node[] = [];
  const heads: { id: string; label: string; x: number; w: number; n: number }[] = [];
  let x0 = 0;
  bands.forEach((b: any, bi: number) => {
    const bw = cols[bi] * cw, rows = Math.ceil(b.nodes.length / cols[bi]);
    const top = HEAD + ((height - HEAD) - rows * ch) / 2;
    b.nodes.forEach((n: any, i: number) => {
      const r = Math.floor(i / cols[bi]), inRow = Math.min(cols[bi], b.nodes.length - r * cols[bi]);
      const c = i % cols[bi];
      nodes.push({ ...n, x: x0 + (bw - inRow * cw) / 2 + (c + 0.5) * cw, y: top + r * ch + ch * 0.42 });
    });
    heads.push({ id: b.id, label: b.label, x: x0, w: bw, n: b.members.length });
    x0 += bw;
  });
  return { nodes, heads, height, byId };
}

function Detail({ id, data, onSelect }: { id: string; data: any; onSelect: (id: string) => void }) {
  const openProv = useUI((s) => s.openProv);
  const [d, setD] = useState<any>(null);
  const inv: Inv = data.investigations.find((i: Inv) => i.id === id);
  useEffect(() => { setD(null); get(`/node/${encodeURIComponent(id)}`).then(setD).catch(() => {}); }, [id]);
  const links = data.links[id] ?? [];
  const label = (nid: string) => data.investigations.find((i: Inv) => i.id === nid)?.label ?? nid;
  return (
    <div className="rise" data-ready="detail">
      <p className="eyebrow">{inv.pillars.map((p) => GOAL_WORD[p]).join(" and ")}</p>
      <h2 className="title mt-1">{inv.label}</h2>
      <p className="mt-1 text-base text-ink-2">{inv.name}</p>
      <p className="mt-4 text-sm leading-relaxed text-ink">{inv.objectives}</p>
      <dl className="mt-5 grid grid-cols-[110px_1fr] gap-y-2 text-sm">
        <dt className="text-ink-3">Burns</dt><dd className="text-ink">{inv.burns}</dd>
        <dt className="text-ink-3">Where</dt><dd className="text-ink">{inv.platform}</dd>
        {inv.years && <><dt className="text-ink-3">Years</dt><dd className="mono text-ink">{inv.years[0]}{inv.years[1] !== inv.years[0] ? `–${inv.years[1]}` : ""}</dd></>}
        <dt className="text-ink-3">Test data</dt>
        <dd className="text-ink">{inv.n_tests ? `${inv.n_tests} tests loaded` : "None loaded. This entry is a catalogue record only."}</dd>
      </dl>

      {inv.n_tests > 0 && d?.numbers && (
        <div className="mt-5 grid grid-cols-2 gap-3">
          {d.numbers.filter((x: any) => !x.nodata && x.label !== "tests").slice(0, 4).map((x: any) => (
            <button key={x.label} className="card card-hover p-3 text-left" onClick={() => x.citation && openProv({ citation: x.citation, label: x.label })} title="Select to see the tests behind this number">
              <span className="block text-xs text-ink-3">{x.label[0].toUpperCase() + x.label.slice(1)}</span>
              <span className="mono mt-0.5 block text-xl text-ink">{x.value}<span className="ml-1 text-xs text-ink-3">{x.unit}</span></span>
            </button>
          ))}
        </div>
      )}
      {inv.n_tests > 0 && (
        <div className="mt-5 flex flex-wrap gap-2.5">
          <Link className="btn primary" href={`/lab?mode=${inv.fuel_phase === "solid" ? "solid" : "droplet"}`}>Simulate it</Link>
          <Link className="btn" href={`/data?dataset=${inv.fuel_phase === "solid" ? "bass2_demo" : "flex"}`}>Open its tests</Link>
        </div>
      )}

      {links.length > 0 && (
        <section className="mt-7">
          <p className="eyebrow">Closest relatives</p>
          <ul className="mt-2 space-y-1">
            {links.map((l: any) => (
              <li key={l.to}>
                <button className="w-full rounded px-2 py-1.5 text-left hover:bg-surface-2" onClick={() => onSelect(l.to)}>
                  <span className="text-sm font-medium text-ink">{label(l.to)}</span>
                  <span className="block text-sm text-ink-2">{l.why[0].toUpperCase() + l.why.slice(1)}</span>
                </button>
              </li>
            ))}
          </ul>
        </section>
      )}
      {d?.passages?.length > 0 && (
        <section className="mt-7"><p className="eyebrow">From the reports</p><div className="mt-3 space-y-5">{d.passages.slice(0, 2).map((p: any) => <Passage key={p.chunk_id} p={p} />)}</div></section>
      )}
    </div>
  );
}

function Intro({ data }: { data: any }) {
  const openSource = useUI((s) => s.openSource);
  const [idea, setIdea] = useState<string | null>(null);
  const withData = data.investigations.filter((i: Inv) => i.n_tests > 0).length;
  return (
    <div>
      <h2 className="title">{data.investigations.length} experiments</h2>
      <p className="mt-2 text-base text-ink-2">{withData} have test data loaded. Select a circle to read about it, or open a group to see the rest.</p>
      <details className="mt-7 group" open>
        <summary className="eyebrow cursor-pointer">Key ideas ({data.ideas.length})</summary>
        <ul className="mt-2">
          {data.ideas.map((c: any) => (
            <li key={c.id} className="rule-b">
              <button className="w-full py-2 text-left text-sm text-ink hover:text-flame" aria-expanded={idea === c.id} onClick={() => setIdea(idea === c.id ? null : c.id)}>{c.label}</button>
              {idea === c.id && <p className="rise pb-3 text-sm leading-relaxed text-ink-2">{c.plain}</p>}
            </li>
          ))}
        </ul>
      </details>
      <details className="mt-6">
        <summary className="eyebrow cursor-pointer">Reports ({data.reports.length})</summary>
        <ul className="mt-2">
          {data.reports.map((r: any) => (
            <li key={r.id} className="rule-b"><button className="w-full py-2 text-left text-sm text-ink hover:text-flame" onClick={() => openSource({ doc: r.id.slice(4), page: 1 })}>{r.label}<span className="ml-2 text-ink-3">{r.pages} pages{r.demo ? ", demo" : ""}</span></button></li>
          ))}
        </ul>
      </details>
    </div>
  );
}

function Inner() {
  const sp = useSearchParams();
  const router = useRouter();
  const [data, setData] = useState<any>(null);
  const [grouping, setGrouping] = useState<Grouping>((sp.get("group") as Grouping) || "burns");
  const [open, setOpen] = useState<string | null>(null);
  const [sel, setSel] = useState<string | null>(sp.get("open"));
  const [hover, setHover] = useState<string | null>(null);
  const [ref, size] = useSize<HTMLDivElement>();
  useEffect(() => { get("/explore").then(setData); }, []);

  const groupOf = (id: string, g: Grouping) => {
    if (!data) return null;
    const inv = data.investigations.find((i: Inv) => i.id === id);
    return data.groupings[g].find((x: any) => x.members.includes(id) && (g !== "goal" || x.id === `goal:${inv.pillars[0]}`))?.id ?? null;
  };
  const L = useMemo(() => (data && size.w > 0 ? layout(data, grouping, open, size.w, size.h) : null), [data, grouping, open, size.w, size.h]);

  // a selected experiment hidden inside a cluster opens its group
  useEffect(() => {
    if (!L || !sel || L.nodes.some((n) => n.id === sel)) return;
    setOpen(groupOf(sel, grouping));
  }, [sel, L, grouping]); // eslint-disable-line react-hooks/exhaustive-deps

  const select = (id: string | null) => { setSel(id); router.replace(id ? `/explore?open=${encodeURIComponent(id)}` : "/explore", { scroll: false }); };
  const focus = hover ?? sel;
  const links = useMemo(() => {
    if (!L || !focus || !data.links[focus]) return [];
    const at = (id: string) => L.nodes.find((n) => n.id === id) ?? L.nodes.find((n) => n.members?.includes(id));
    const from = at(focus);
    if (!from) return [];
    const seen = new Set<string>();
    return data.links[focus].map((l: any) => ({ l, to: at(l.to) })).filter(({ to }: any) => to && to.id !== from.id && !seen.has(to.id) && seen.add(to.id)).map(({ l, to }: any) => ({ from, to, strength: l.strength }));
  }, [L, focus, data]);
  const lit = new Set<string>(focus ? [focus, ...links.map((k: any) => k.to.id)] : []);

  return (
    <div className="flex h-full" data-ready={L ? "explore" : undefined}>
      <div className="flex min-w-0 flex-1 flex-col">
        <div className="flex shrink-0 flex-wrap items-center gap-x-6 gap-y-2 px-8 pb-2 pt-6">
          <h1 className="title">Explore the experiments</h1>
          <div className="flex items-center gap-3">
            <span className="text-sm text-ink-3">Group by</span>
            <div className="seg" role="group" aria-label="Group by">
              {VIEWS.map(([k, l]) => <button key={k} aria-pressed={grouping === k} data-view={k} onClick={() => { setGrouping(k); setOpen(null); }}>{l}</button>)}
            </div>
          </div>
          <p className="ml-auto flex flex-wrap items-center gap-x-4 gap-y-1 text-sm text-ink-2">
            <span>Bigger circle = more test data</span>
            {Object.entries(GOAL_WORD).map(([k, w]) => <span key={k} className="flex items-center gap-1.5"><span className="h-3 w-3 rounded-full" style={{ background: GOAL_COLOR[k] }} />{w}</span>)}
          </p>
        </div>
        <div ref={ref} className="relative min-h-0 flex-1 overflow-y-auto overflow-x-hidden" onClick={() => select(null)}>
          {L && (
            <div className="relative" style={{ height: L.height }}>
              {L.heads.map((h, i) => (
                <div key={h.id} className="absolute top-0 px-5 pt-4" style={{ left: h.x, width: h.w, height: L.height, borderLeft: i ? "1px solid var(--line)" : undefined }}>
                  <p className="text-lg font-semibold tracking-tight text-ink" data-label>{h.label}</p>
                  <p className="text-sm text-ink-3">{h.n} experiment{h.n === 1 ? "" : "s"}
                    {open === h.id && <button className="ml-3 underline decoration-dotted underline-offset-4 hover:text-ink" onClick={(e) => { e.stopPropagation(); setOpen(null); }}>fold</button>}
                  </p>
                </div>
              ))}
              <svg className="pointer-events-none absolute inset-0" width={size.w} height={L.height} aria-hidden>
                {links.map((k: any) => (
                  <line key={k.to.id} x1={k.from.x} y1={k.from.y} x2={k.to.x} y2={k.to.y} stroke="var(--flame)" strokeOpacity={0.35 + 0.1 * k.strength} strokeWidth={1 + k.strength * 0.5} strokeLinecap="round" />
                ))}
              </svg>
              {L.nodes.map((n) => {
                const color = n.inv ? GOAL_COLOR[n.inv.pillars[0]] : "var(--text-3)";
                const has = !!n.inv?.n_tests;
                const dim = focus && !lit.has(n.id);
                return (
                  <button key={n.id} data-node={n.id} data-kind={n.kind}
                    className="absolute flex w-[168px] -translate-x-1/2 flex-col items-center text-center transition-[left,top,opacity] duration-300 ease-out"
                    style={{ left: n.x, top: n.y - n.r, opacity: dim ? 0.32 : 1 }}
                    onMouseEnter={() => { if (n.inv) { setHover(n.id); get(`/node/${encodeURIComponent(n.id)}`).catch(() => {}); } }} onMouseLeave={() => setHover(null)}
                    onFocus={() => n.inv && setHover(n.id)} onBlur={() => setHover(null)}
                    onClick={(e) => { e.stopPropagation(); if (n.kind === "cluster") { setOpen(n.group); select(null); } else select(n.id); }}
                    aria-label={n.inv ? `${n.inv.label}: ${n.inv.name}. ${n.sub}` : `${n.label}, ${n.sub}`} aria-pressed={sel === n.id}>
                    <span className="flex items-center justify-center rounded-full transition-transform duration-150 hover:scale-105"
                      style={{ width: n.r * 2, height: n.r * 2,
                        background: n.kind === "cluster" ? "var(--surface-2)" : has ? color : "var(--bg)",
                        border: n.kind === "cluster" ? "2px dashed var(--text-3)" : `2.5px solid ${color}`,
                        boxShadow: sel === n.id ? "0 0 0 4px var(--bg), 0 0 0 6px var(--flame)" : has ? `0 0 28px -4px ${color}` : undefined }}>
                      {n.kind === "cluster" && <span className="mono text-base text-ink">+{n.members!.length}</span>}
                      {has && <span className="mono text-[15px] font-semibold" style={{ color: "#06080D" }}>{n.inv!.n_tests}</span>}
                    </span>
                    <span className="relative mt-2 rounded px-1.5 text-[15px] font-medium leading-tight text-ink" style={{ background: "var(--bg)" }} data-label>{n.label}</span>
                    <span className="relative rounded px-1.5 pb-0.5 text-[13px] leading-tight text-ink-3" style={{ background: "var(--bg)" }} data-label>{n.sub}</span>
                  </button>
                );
              })}
            </div>
          )}
        </div>
      </div>
      <aside className="rule-l w-[440px] shrink-0 overflow-y-auto px-7 py-7" style={{ background: "var(--surface)" }} aria-label="Details">
        {data && (sel && data.investigations.some((i: Inv) => i.id === sel) ? <Detail id={sel} data={data} onSelect={select} /> : <Intro data={data} />)}
      </aside>
    </div>
  );
}

export default function ExplorePage() {
  return <Suspense><Inner /></Suspense>;
}
