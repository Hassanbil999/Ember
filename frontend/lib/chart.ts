"use client";
import { useEffect, useRef, useState } from "react";
import palettes from "./palettes.json";

export function useSize<T extends HTMLElement>() {
  const ref = useRef<T>(null);
  const [size, setSize] = useState({ w: 0, h: 0 });
  useEffect(() => {
    if (!ref.current) return;
    const ro = new ResizeObserver(([e]) => setSize({ w: Math.max(120, e.contentRect.width), h: Math.max(80, e.contentRect.height) }));
    ro.observe(ref.current);
    return () => ro.disconnect();
  }, []);
  return [ref, size] as const;
}

export type PaletteName = "default" | "colorblind";
export const PALETTES = palettes as Record<PaletteName, string[]>;

/** outcome colours are semantic and fixed: burning = flame, extinction = ext */
export function outcomeColor(v: any) {
  if (v == null || Number.isNaN(v)) return "var(--nodata)";
  return v ? "var(--flame)" : "var(--ext)";
}

function cssVarsResolved(svg: SVGSVGElement) {
  const cs = getComputedStyle(document.documentElement);
  const clone = svg.cloneNode(true) as SVGSVGElement;
  const resolve = (s: string) => s.replace(/var\(--([a-z0-9-]+)\)/g, (_, n) => cs.getPropertyValue(`--${n}`).trim() || "#888");
  clone.querySelectorAll("*").forEach((el) => {
    for (const a of ["fill", "stroke", "style", "stop-color", "color"]) {
      const v = el.getAttribute(a);
      if (v && v.includes("var(")) el.setAttribute(a, resolve(v));
    }
  });
  clone.setAttribute("xmlns", "http://www.w3.org/2000/svg");
  const bg = cs.getPropertyValue("--bg").trim();
  const font = getComputedStyle(document.body).fontFamily;
  clone.setAttribute("style", `background:${bg};font-family:${font}`);
  return clone;
}

export function svgString(svg: SVGSVGElement, caption?: string) {
  const c = cssVarsResolved(svg);
  if (caption) {
    const h = Number(svg.getAttribute("height") || svg.getBoundingClientRect().height);
    const w = Number(svg.getAttribute("width") || svg.getBoundingClientRect().width);
    c.setAttribute("height", String(h + 34));
    c.setAttribute("viewBox", `0 0 ${w} ${h + 34}`);
    const t = document.createElementNS("http://www.w3.org/2000/svg", "text");
    t.setAttribute("x", "8"); t.setAttribute("y", String(h + 22));
    t.setAttribute("font-size", "10.5"); t.setAttribute("fill", getComputedStyle(document.documentElement).getPropertyValue("--text-2"));
    t.textContent = caption;
    c.appendChild(t);
  }
  return new XMLSerializer().serializeToString(c);
}

export async function svgToPng(svg: SVGSVGElement, caption?: string, scale = 2): Promise<Blob> {
  const s = svgString(svg, caption);
  const img = new Image();
  const url = URL.createObjectURL(new Blob([s], { type: "image/svg+xml" }));
  await new Promise((res, rej) => { img.onload = res; img.onerror = rej; img.src = url; });
  const canvas = document.createElement("canvas");
  canvas.width = img.width * scale; canvas.height = img.height * scale;
  const ctx = canvas.getContext("2d")!;
  ctx.scale(scale, scale);
  ctx.drawImage(img, 0, 0);
  URL.revokeObjectURL(url);
  return new Promise((res) => canvas.toBlob((b) => res(b!), "image/png"));
}
