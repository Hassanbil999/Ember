"use client";
import { useEffect, useState } from "react";
import { get, post } from "@/lib/api";
import { useUI } from "@/lib/store";

/** Source viewer: the original PDF page rendered server-side, with the cited passages
 *  highlighted at their exact location on the page. */
export default function SourceViewer() {
  const { source, openSource } = useUI();
  const [hl, setHl] = useState<any>(null);
  const [page, setPage] = useState(1);
  const [cite, setCite] = useState<string>("");

  useEffect(() => { if (source) setPage(source.page || 1); }, [source]);
  useEffect(() => {
    if (!source) return;
    const spans = (source.spans ?? []).join("||");
    get(`/doc/${source.doc}/page/${page}/highlights?spans=${encodeURIComponent(page === source.page ? spans : "")}`, { cache: true }).then(setHl);
    if (source.chunk) post("/export/citations", { chunks: [source.chunk] }).then((r: any) => setCite(r.text));
  }, [source, page]);
  useEffect(() => {
    const k = (e: KeyboardEvent) => {
      if (!source) return;
      if (e.key === "Escape") openSource(null);
      if (e.key === "ArrowRight" && hl && page < hl.pages) setPage(page + 1);
      if (e.key === "ArrowLeft" && page > 1) setPage(page - 1);
    };
    window.addEventListener("keydown", k);
    return () => window.removeEventListener("keydown", k);
  }, [source, openSource, hl, page]);

  if (!source) return null;
  return (
    <div className="fixed inset-0 z-50 flex items-stretch justify-center bg-black/50" onMouseDown={() => openSource(null)} role="dialog" aria-label="Source document">
      <div className="my-6 flex w-[860px] flex-col overflow-hidden rounded-md bg-surface" style={{ border: "1px solid var(--line-strong)" }} onMouseDown={(e) => e.stopPropagation()}>
        <div className="rule-b flex items-center gap-3 px-4 py-2.5">
          <span className="eyebrow">Source</span>
          <span className="truncate text-sm">{hl?.title}</span>
          {hl?.demo && <span className="mono text-2xs" style={{ color: "var(--warn)" }}>demo fixture</span>}
          <div className="ml-auto flex items-center gap-1">
            <button className="btn ghost h-7 px-2" disabled={page <= 1} onClick={() => setPage(page - 1)} aria-label="Previous page">←</button>
            <span className="mono w-16 text-center text-xs">p. {page} / {hl?.pages ?? "…"}</span>
            <button className="btn ghost h-7 px-2" disabled={!hl || page >= hl.pages} onClick={() => setPage(page + 1)} aria-label="Next page">→</button>
            <a className="btn ghost h-7" href={`/api/doc/${source.doc}/file#page=${page}`} target="_blank" rel="noreferrer">Open PDF ↗</a>
            <button className="btn ghost h-7 w-7 justify-center p-0" onClick={() => openSource(null)} aria-label="Close">✕</button>
          </div>
        </div>
        <div className="min-h-0 flex-1 overflow-auto bg-surface-2 p-6">
          <div className="relative mx-auto w-fit" style={{ boxShadow: "var(--shadow)" }}>
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img src={`/api/doc/${source.doc}/page/${page}.png`} alt={`Page ${page} of ${hl?.title ?? "document"}`} className="block max-w-[780px]" />
            {(hl?.rects ?? []).map((r: any, i: number) => (
              <span key={i} className="absolute" style={{ left: `${r.x * 100}%`, top: `${r.y * 100}%`, width: `${r.w * 100}%`, height: `${r.h * 100}%`, background: "rgba(238,138,60,0.28)", borderBottom: "1.5px solid #EE8A3C", mixBlendMode: "multiply" }} />
            ))}
          </div>
        </div>
        {cite && (
          <div className="rule-t flex items-center gap-3 px-4 py-2 text-xs text-ink-2">
            <span className="eyebrow">Cite</span><span className="mono truncate">{cite}</span>
            <button className="btn ml-auto h-6 text-xs" onClick={() => navigator.clipboard.writeText(cite)}>Copy</button>
          </div>
        )}
      </div>
    </div>
  );
}
