"use client";
import { useEffect, useState } from "react";
import { get } from "./api";
import { setVars } from "./format";

export interface Meta {
  demo: boolean;
  loaded: { real: string[]; demo: string[] };
  counts: Record<string, number>;
  variables: Record<string, any>;
  glossary: Record<string, string>;
  concepts: { id: string; name: string; definition: string; plain: string; terms: string; investigations: string }[];
  presets: { presets: any[]; targets: any[] };
  models: Record<string, any>;
  categories: Record<string, string[]>;
  datasets: Record<string, { title: string; demo: boolean; adapter: string; enabled: boolean }>;
}

let cached: Meta | null = null;
let pending: Promise<Meta> | null = null;

export function loadMeta(): Promise<Meta> {
  if (cached) return Promise.resolve(cached);
  if (!pending) pending = get<Meta>("/meta").then((m) => { cached = m; setVars(m.variables); return m; });
  return pending;
}

export function useMeta(): Meta | null {
  const [m, setM] = useState<Meta | null>(null);   // never read the cache during render: SSR must match
  useEffect(() => { loadMeta().then(setM).catch(() => {}); }, []);
  return m;
}

/** glossary lookup: glossary entries + concept terms */
export function define(meta: Meta | null, term: string): { title: string; text: string } | null {
  if (!meta) return null;
  const k = term.toLowerCase();
  for (const [g, t] of Object.entries(meta.glossary)) if (g.toLowerCase() === k) return { title: g, text: t };
  for (const c of meta.concepts) {
    const terms: string[] = JSON.parse(c.terms || "[]");
    if (c.name.toLowerCase() === k || terms.includes(k)) return { title: c.name, text: c.definition };
  }
  return null;
}
