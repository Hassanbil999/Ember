"use client";
import { create } from "zustand";
import { persist } from "zustand/middleware";

export type Role = "student" | "researcher" | "engineer";

export type Citation =
  | { kind: "aggregate"; op: string; field: string; rows: string[]; display?: string }
  | { kind: "row"; target: string; fields?: string[] }
  | { kind: "chunk"; target: string; span?: string; page?: number }
  | { kind: "query"; text: string };

export interface ReportItem { id: string; title: string; svg?: string; caption?: string; kind: "chart" | "finding"; text?: string; cite?: string }

interface UI {
  role: Role; theme: "void" | "paper";
  setRole: (r: Role) => void; setTheme: (t: "void" | "paper") => void;
  // global overlays: the provenance panel and the source viewers
  prov: { citation?: Citation; testId?: string; label?: string } | null;
  openProv: (p: UI["prov"]) => void;
  source: { doc: string; page: number; spans?: string[]; chunk?: string } | null;
  openSource: (s: UI["source"]) => void;
  sourceRow: { dataset: string; row: number; column?: string | null } | null;
  openSourceRow: (s: UI["sourceRow"]) => void;
  report: ReportItem[]; addReport: (r: ReportItem) => void; removeReport: (id: string) => void; clearReport: () => void;
}

export const useUI = create<UI>()(
  persist(
    (set) => ({
      role: "researcher", theme: "void",
      setRole: (role) => set({ role }), setTheme: (theme) => set({ theme }),
      prov: null, openProv: (prov) => set({ prov }),
      source: null, openSource: (source) => set({ source }),
      sourceRow: null, openSourceRow: (sourceRow) => set({ sourceRow }),
      report: [], addReport: (r) => set((s) => ({ report: [...s.report.filter((x) => x.id !== r.id), r] })),
      removeReport: (id) => set((s) => ({ report: s.report.filter((r) => r.id !== id) })), clearReport: () => set({ report: [] }),
    }),
    { name: "freefall-atlas-2", partialize: (s) => ({ role: s.role, theme: s.theme, report: s.report }) },
  ),
);
