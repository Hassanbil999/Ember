"use client";
import { forwardRef, useEffect, useState } from "react";
import { fmt } from "@/lib/format";

export type Feature = "droplet" | "flame" | "standoff" | "state";
export const ALL_FEATURES: Feature[] = ["droplet", "flame", "standoff", "state"];

const PLAIN: Record<Feature, string> = { droplet: "Fuel droplet", flame: "Flame edge", standoff: "Gap: flame / droplet", state: "Burn state" };
const EXPERT: Record<Feature, string> = { droplet: "droplet_diameter_mm", flame: "flame_diameter_mm", standoff: "standoff_ratio", state: "state" };
const GLOSS: Record<Feature, string> = {
  droplet: "Equivalent-circle diameter of the dark blob in the backlit view.",
  flame: "Outer diameter of the luminous region in the flame view.",
  standoff: "Standoff ratio = flame diameter ÷ droplet diameter.",
  state: "Burning, extinguished or disrupted — from the event detector.",
};

export function useDataUrl(src: string | null) {
  const [url, setUrl] = useState<string | null>(null);
  useEffect(() => {
    if (!src) return;
    let alive = true;
    fetch(src).then((r) => r.blob()).then((b) => new Promise<string>((res) => { const fr = new FileReader(); fr.onload = () => res(fr.result as string); fr.readAsDataURL(b); }))
      .then((u) => alive && setUrl(u)).catch(() => {});
    return () => { alive = false; };
  }, [src]);
  return url;
}

interface Callout { f: Feature; ax: number; ay: number; side: "l" | "r"; text: string; sub: string; ly?: number }

/** place labels in two columns beside the image; resolve vertical collisions; elbow leaders */
function layout(cs: Callout[], top: number, bottom: number, gap = 34) {
  for (const side of ["l", "r"] as const) {
    const col = cs.filter((c) => c.side === side).sort((a, b) => a.ay - b.ay);
    let y = top;
    for (const c of col) { c.ly = Math.max(c.ay, y); y = c.ly + gap; }
    const over = (col.at(-1)?.ly ?? 0) - bottom;
    if (over > 0) for (const c of col) c.ly! -= over;
  }
  return cs;
}

const AnnotatedFrame = forwardRef<SVGSVGElement, {
  testId: string; frame: any; meta: { px_per_mm: number; size: [number, number]; kind: string; fps?: number; path?: string; extractor?: string; version?: string };
  role: string; width: number; features?: Feature[]; view?: "backlit" | "flame"; caption?: string; onPick?: (f: Feature) => void; animate?: boolean;
}>(function AnnotatedFrame({ testId, frame, meta, role, width, features = ALL_FEATURES, view = "backlit", caption, onPick, animate }, ref) {
  const [hover, setHover] = useState<Feature | null>(null);
  const href = useDataUrl(`/api/vision/${testId}/frame/${frame.frame}.png?view=${view}`);
  const [ih, iw] = meta.size ?? [128, 128];
  const side = 170;
  const imgW = Math.min(width - side * 2, 420);
  const s = imgW / iw;
  const H = ih * s + (caption ? 44 : 16);
  const ox = side, oy = 8;
  const expert = role !== "student";
  const d = frame.droplet, fl = frame.flame;
  const cs: Callout[] = [];
  if (d && features.includes("droplet")) {
    const r = (d.d_px / 2) * s;
    cs.push({ f: "droplet", ax: ox + d.cx * s + r * 0.7, ay: oy + d.cy * s - r * 0.7, side: "r",
      text: expert ? `d = ${fmt(d.droplet_diameter_mm, 4)} mm` : `${PLAIN.droplet} · ${fmt(d.droplet_diameter_mm, 3)} mm`,
      sub: expert ? `${EXPERT.droplet} · conf ${d.confidence.toFixed(2)}` : `across · confidence ${d.confidence.toFixed(2)}` });
  }
  if (fl?.lit && features.includes("flame")) {
    const r = (fl.flame_diameter_mm * meta.px_per_mm / 2) * s;
    cs.push({ f: "flame", ax: ox + fl.cx * s - r * 0.72, ay: oy + fl.cy * s - r * 0.7, side: "l",
      text: expert ? `d_f = ${fmt(fl.flame_diameter_mm, 4)} mm` : `${PLAIN.flame} · ${fmt(fl.flame_diameter_mm, 3)} mm`,
      sub: expert ? `peak ${fmt(fl.peak_intensity, 3)} · R/B ${fl.red_blue_ratio ? fl.red_blue_ratio.toFixed(2) : "—"}` : "outer edge of the glow" });
  }
  if (frame.standoff_ratio && d && fl?.lit && features.includes("standoff")) {
    const rd = (d.d_px / 2) * s, rf = (fl.flame_diameter_mm * meta.px_per_mm / 2) * s;
    cs.push({ f: "standoff", ax: ox + d.cx * s, ay: oy + d.cy * s + (rd + rf) / 2, side: "r",
      text: expert ? `standoff = ${frame.standoff_ratio.toFixed(2)}` : `Flame ${frame.standoff_ratio.toFixed(1)}× droplet`,
      sub: expert ? "d_f ÷ d" : "gap between flame and fuel" });
  }
  if (features.includes("state")) {
    cs.push({ f: "state", ax: ox + 10, ay: oy + ih * s - 12, side: "l",
      text: expert ? frame.state : `${PLAIN.state}: ${frame.state}`, sub: `t = ${frame.t.toFixed(2)} s · frame ${frame.frame}` });
  }
  layout(cs, oy + 10, oy + ih * s - 10);
  const W = width;
  const tr = animate ? "all 320ms cubic-bezier(.2,.7,.2,1)" : undefined;
  return (
    <svg ref={ref} width={W} height={H} role="img" aria-label={`Annotated frame ${frame.frame} of test ${testId}: ${cs.map((c) => c.text).join("; ")}`} style={{ display: "block" }}>
      {href ? <image href={href} x={ox} y={oy} width={iw * s} height={ih * s} style={{ imageRendering: "pixelated" }} /> : <rect x={ox} y={oy} width={iw * s} height={ih * s} fill="var(--surface-2)" />}
      <rect x={ox} y={oy} width={iw * s} height={ih * s} fill="none" stroke="var(--line-strong)" />
      {d && features.includes("droplet") && <polygon points={d.contour.map((p: number[]) => `${ox + p[0] * s},${oy + p[1] * s}`).join(" ")} fill="none" stroke="#5FA0DC" strokeWidth={1.4} style={{ transition: tr }} />}
      {fl?.lit && fl.contour && features.includes("flame") && <polygon points={fl.contour.map((p: number[]) => `${ox + p[0] * s},${oy + p[1] * s}`).join(" ")} fill="none" stroke="#EE8A3C" strokeWidth={1.2} strokeDasharray="4 3" style={{ transition: tr }} />}
      {cs.map((c) => {
        const lx = c.side === "l" ? side - 10 : ox + iw * s + 10;
        const tx = c.side === "l" ? lx - 4 : lx + 4;
        const on = hover === c.f;
        const col = c.f === "droplet" ? "#5FA0DC" : c.f === "flame" ? "#EE8A3C" : "var(--text-2)";
        return (
          <g key={c.f} style={{ cursor: "pointer", transition: tr }} onPointerEnter={() => setHover(c.f)} onPointerLeave={() => setHover(null)} onClick={() => onPick?.(c.f)}>
            <polyline points={`${c.ax},${c.ay} ${c.side === "l" ? ox - 4 : ox + iw * s + 4},${c.ly} ${lx},${c.ly}`} fill="none" stroke={on ? "var(--text)" : col} strokeWidth={on ? 1.2 : 0.9} />
            <circle cx={c.ax} cy={c.ay} r={2.4} fill={col} stroke="var(--bg)" strokeWidth={0.8} />
            <text x={tx} y={c.ly! - 3} fontSize={13} textAnchor={c.side === "l" ? "end" : "start"} fill="var(--text)" className={expert ? "mono" : ""}>{c.text}</text>
            <text x={tx} y={c.ly! + 11} fontSize={13} textAnchor={c.side === "l" ? "end" : "start"} fill="var(--text-3)" className="mono">{c.sub}</text>
            <title>{GLOSS[c.f]}</title>
          </g>
        );
      })}
      <text x={ox + 6} y={oy + 14} fontSize={13} className="mono" fill="#EE8A3C" style={{ paintOrder: "stroke", stroke: "#000", strokeWidth: 3 }}>
        {meta.kind === "test_pattern" ? "TEST PATTERN · synthetic shape, not a flame" : "real footage"}
      </text>
      {caption && <text x={8} y={H - 22} fontSize={13} fill="var(--text-2)">{caption}</text>}
      {caption && <text x={8} y={H - 8} fontSize={13} className="mono" fill="var(--text-3)">{`${meta.path ?? ""} · frame ${frame.frame} · ${meta.extractor ?? ""} v${meta.version ?? ""}`}</text>}
    </svg>
  );
});

export default AnnotatedFrame;
