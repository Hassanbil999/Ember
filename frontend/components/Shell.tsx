"use client";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { get } from "@/lib/api";
import { useUI } from "@/lib/store";
import { useMeta } from "@/lib/meta";
import ProvenancePanel from "./ProvenancePanel";
import SourceViewer from "./SourceViewer";

const NAV = [
  { href: "/explore", label: "Explore" },
  { href: "/lab", label: "Simulate", also: ["/trade"] },
  { href: "/insights", label: "Insights", also: ["/studio"] },
  { href: "/data", label: "Data", also: ["/image"] },
];
const DEPTH = [
  { id: "student", label: "Plain language" },
  { id: "researcher", label: "Research detail" },
  { id: "engineer", label: "Engineering margins" },
] as const;

export function DemoBadge() {
  const meta = useMeta();
  if (meta && !meta.demo) return null;
  const mixed = !!meta && meta.loaded.real.length > 0;
  return (
    <span className="inline-flex h-7 shrink-0 items-center gap-2 whitespace-nowrap rounded-full px-3 text-xs text-ink-2"
      style={{ border: "1px dashed var(--warn)" }} role="status"
      title={mixed
        ? `Real NASA data: ${meta!.loaded.real.join("; ")}. Synthetic demo data: ${meta!.loaded.demo.join("; ")}, and the demo reports. Each screen says which it is using.`
        : "Every table, report and chart in this build comes from a synthetic demo fixture, not from NASA."}>
      <span className="h-1.5 w-1.5 rounded-full" style={{ background: "var(--warn)" }} />
      {mixed ? "Solid-material tests are demo data" : "Demo data, not NASA results"}
    </span>
  );
}

function Logo() {
  // a fuel droplet inside its spherical microgravity flame
  return (
    <svg width="26" height="26" viewBox="0 0 26 26" aria-hidden>
      <defs><radialGradient id="lg"><stop offset="55%" stopColor="var(--flame)" stopOpacity="0" /><stop offset="100%" stopColor="var(--flame)" stopOpacity=".55" /></radialGradient></defs>
      <circle cx="13" cy="13" r="12" fill="url(#lg)" />
      <circle cx="13" cy="13" r="11" fill="none" stroke="var(--flame)" strokeWidth="1.5" />
      <circle cx="13" cy="13" r="3.6" fill="var(--text)" />
    </svg>
  );
}

function Menu() {
  const { theme, setTheme, role, setRole } = useUI();
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!open) return;
    const off = (e: MouseEvent) => { if (!ref.current?.contains(e.target as Node)) setOpen(false); };
    const esc = (e: KeyboardEvent) => { if (e.key === "Escape") setOpen(false); };
    window.addEventListener("mousedown", off); window.addEventListener("keydown", esc);
    return () => { window.removeEventListener("mousedown", off); window.removeEventListener("keydown", esc); };
  }, [open]);
  return (
    <div className="relative shrink-0" ref={ref}>
      <button className="btn ghost h-9 w-9 justify-center p-0" aria-label="Display settings" aria-expanded={open} onClick={() => setOpen(!open)}>
        <svg width="18" height="18" viewBox="0 0 18 18" aria-hidden><path d="M2 5h14M2 9h14M2 13h14" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" /><circle cx="6" cy="5" r="2" fill="var(--bg)" stroke="currentColor" strokeWidth="1.6" /><circle cx="12" cy="9" r="2" fill="var(--bg)" stroke="currentColor" strokeWidth="1.6" /><circle cx="7" cy="13" r="2" fill="var(--bg)" stroke="currentColor" strokeWidth="1.6" /></svg>
      </button>
      {open && (
        <div className="card absolute right-0 top-11 z-50 w-64 p-4" style={{ boxShadow: "var(--shadow)" }} role="menu">
          <p className="eyebrow">Explanations</p>
          <div className="mt-2 space-y-1">
            {DEPTH.map((d) => (
              <button key={d.id} role="menuitemradio" aria-checked={role === d.id} onClick={() => setRole(d.id)}
                className={`flex h-9 w-full items-center gap-2.5 rounded px-2 text-left text-sm hover:bg-surface-2 ${role === d.id ? "text-ink" : "text-ink-2"}`}>
                <span className="h-2.5 w-2.5 rounded-full" style={{ background: role === d.id ? "var(--flame)" : "transparent", border: "1.5px solid var(--text-3)" }} />{d.label}
              </button>
            ))}
          </div>
          <p className="eyebrow mt-4">Appearance</p>
          <div className="seg mt-2 w-full">
            {(["void", "paper"] as const).map((t) => (
              <button key={t} className="flex-1" aria-pressed={theme === t} onClick={() => setTheme(t)}>{t === "void" ? "Dark" : "Light"}</button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

export default function Shell({ children }: { children: React.ReactNode }) {
  const path = usePathname();
  const router = useRouter();
  const theme = useUI((s) => s.theme);
  const input = useRef<HTMLInputElement>(null);

  useEffect(() => { document.documentElement.dataset.theme = theme; }, [theme]);
  // Once the current screen is up, load the code and data of the screens one click away, so the
  // first click on each is as fast as a repeat visit (measured: 182 ms → under 90 ms for home → answer).
  useEffect(() => {
    const t = setTimeout(() => {
      import("@/app/answer/page"); import("@/app/explore/page"); import("@/app/lab/page"); import("@/app/insights/page"); import("@/app/data/page"); import("@/app/trade/page");
      ["/explore", "/insights", "/refinery", "/lab/items", "/atmosphere", "/lab/grid?mode=gas&item=30%25%20butane&gravity=0&diluent=N2"].forEach((u) => get(u).catch(() => {}));
    }, 900);
    return () => clearTimeout(t);
  }, []);
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const t = e.target as HTMLElement;
      const typing = t && (t.tagName === "INPUT" || t.tagName === "TEXTAREA" || t.isContentEditable);
      if (((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") || (!typing && e.key === "/")) { e.preventDefault(); input.current?.focus(); }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  const ask = (e: React.FormEvent) => {
    e.preventDefault();
    const q = input.current?.value.trim();
    if (q) { router.push(`/answer?q=${encodeURIComponent(q)}`); input.current!.blur(); }
  };

  return (
    <div className="flex h-screen flex-col">
      <a href="#main" className="sr-only focus:not-sr-only focus:absolute focus:left-2 focus:top-2 focus:z-50">Skip to content</a>
      <header className="rule-b z-30 flex h-14 shrink-0 items-center gap-6 px-6" style={{ background: "var(--bg)" }}>
        <Link href="/" className="flex shrink-0 items-center gap-2.5 whitespace-nowrap text-[17px] font-semibold" style={{ fontStretch: "118%" }} aria-label="Freefall Atlas home">
          <Logo /> Freefall Atlas
        </Link>
        <nav aria-label="Primary" className="flex h-full shrink-0 items-stretch gap-1">
          {NAV.map((n) => {
            const active = path.startsWith(n.href) || (n.also ?? []).some((a) => path.startsWith(a));
            return (
              <Link key={n.href} href={n.href} aria-current={active ? "page" : undefined}
                className={`relative flex items-center whitespace-nowrap px-3 text-[15px] transition-colors ${active ? "text-ink" : "text-ink-3 hover:text-ink"}`}>
                {n.label}
                {active && <span className="absolute inset-x-3 -bottom-px h-0.5 rounded bg-flame" />}
              </Link>
            );
          })}
        </nav>
        {path !== "/" && (
          <form onSubmit={ask} role="search" className="field ml-auto flex h-9 min-w-0 max-w-[340px] flex-1 items-center gap-2 rounded px-3 text-ink-3 focus-within:text-ink" style={{ border: "1px solid var(--line-strong)", background: "var(--surface)" }}>
            <svg width="15" height="15" viewBox="0 0 16 16" aria-hidden className="shrink-0"><circle cx="7" cy="7" r="5" fill="none" stroke="currentColor" strokeWidth="1.5" /><path d="M11 11l3.5 3.5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" /></svg>
            <input ref={input} type="search" name="q" placeholder="Ask a question" aria-label="Ask a question (press / to focus)"
              className="bare h-full min-w-0 flex-1 text-sm text-ink placeholder:text-ink-3" />
          </form>
        )}
        <div className={`flex shrink-0 items-center gap-3 ${path === "/" ? "ml-auto" : ""}`}>
          <DemoBadge />
          <Menu />
        </div>
      </header>
      <main id="main" className="relative min-h-0 flex-1 overflow-y-auto">{children}</main>
      <ProvenancePanel />
      <SourceViewer />
    </div>
  );
}
