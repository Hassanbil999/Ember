"use client";
import { useMemo } from "react";
import { useUI } from "@/lib/store";

/** A quoted source passage with the cited sentences highlighted; the button opens the page itself. */
export default function Passage({ p }: { p: any }) {
  const openSource = useUI((s) => s.openSource);
  const parts = useMemo(() => {
    let segs: { t: string; hl: boolean }[] = [{ t: p.text, hl: false }];
    for (const h of p.highlights ?? []) {
      const next: typeof segs = [];
      for (const s of segs) {
        const i = s.hl ? -1 : s.t.indexOf(h);
        if (i < 0) { next.push(s); continue; }
        next.push({ t: s.t.slice(0, i), hl: false }, { t: h, hl: true }, { t: s.t.slice(i + h.length), hl: false });
      }
      segs = next;
    }
    return segs;
  }, [p]);
  return (
    <figure className="pl-4" style={{ borderLeft: "2px solid var(--line-strong)" }}>
      <blockquote className="text-sm leading-relaxed text-ink-2">
        {parts.map((s, i) => (s.hl ? <mark key={i} className="src text-ink">{s.t}</mark> : <span key={i}>{s.t}</span>))}
      </blockquote>
      <figcaption className="mt-2">
        <button className="text-left text-xs text-ink-3 underline decoration-dotted underline-offset-4 hover:text-ink"
          onClick={() => openSource({ doc: p.doc_id, page: p.page, spans: p.highlights?.length ? p.highlights : [p.text.slice(0, 80)], chunk: p.chunk_id })}>
          {p.doc_title}, page {p.page}{p.demo ? " (demo report)" : ""}. Open the page
        </button>
      </figcaption>
    </figure>
  );
}
