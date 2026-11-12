"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import { get } from "@/lib/api";
import { useUI } from "@/lib/store";
import { Visual } from "@/components/Viz";

/* Insights: a short feed of findings. Each is one sentence + one visual + where it comes from.
   Nothing to configure before learning something; the chart builder is one click further for those who want it. */
export default function InsightsPage() {
  const [d, setD] = useState<any>(null);
  const openProv = useUI((s) => s.openProv);
  useEffect(() => { get("/insights").then(setD); }, []);
  return (
    <div className="mx-auto max-w-[1180px] px-8 pb-16 pt-8" data-ready={d ? "insights" : undefined}>
      <h1 className="title">What the data says</h1>
      <p className="mt-2 max-w-[70ch] text-base text-ink-2">
        {d ? `${d.insights.length} findings, each recomputed from the loaded tests every time the data changes.` : "Loading…"}
        {d?.demo && <span style={{ color: "var(--warn)" }}> The loaded data is a synthetic demo set, so read these as examples of the method, not as NASA results.</span>}
      </p>
      <div className="mt-8 space-y-5">
        {(d?.insights ?? []).map((x: any, i: number) => (
          <article key={x.id} className="card grid grid-cols-1 gap-x-10 gap-y-5 p-7 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.1fr)]" data-insight={x.id}>
            <div className="flex flex-col">
              <p className="eyebrow"><span className="mono mr-2 text-ink-3">{i + 1}</span>{x.tag}</p>
              <h2 className="mt-2 text-[22px] font-medium leading-snug tracking-tight text-ink">{x.sentence}</h2>
              <div className="mt-auto flex flex-wrap items-center gap-x-5 gap-y-2 pt-5 text-sm">
                <span className="text-ink-3">Source: {x.source}</span>
                {x.citation && <button className="underline decoration-dotted underline-offset-4 text-ink-2 hover:text-ink" onClick={() => openProv({ citation: x.citation, label: x.tag })}>See the {x.citation.rows.length} tests</button>}
                <Link href={x.studio} className="text-ink-2 underline decoration-dotted underline-offset-4 hover:text-ink">{x.studio.startsWith("/studio") ? "Open in Studio" : x.studio === "/lab" ? "Open the simulator" : "Open the data"}</Link>
              </div>
            </div>
            <div className="flex items-center"><Visual v={x.visual} /></div>
          </article>
        ))}
      </div>
      {d && (
        <div className="mt-10 flex flex-wrap items-center gap-3">
          <Link href="/studio" className="btn h-11 px-5">Build your own chart in Studio</Link>
          <span className="text-sm text-ink-3">Choose the variables, style the chart, export it with its citation.</span>
        </div>
      )}
    </div>
  );
}
