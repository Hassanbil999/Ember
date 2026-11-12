"""Payload builders for the Atlas: node focus views (Concept View) and next-path chips."""
from __future__ import annotations

import json
from functools import lru_cache

import numpy as np
import pandas as pd

from ..atlas import group_tests
from ..core import config
from ..core.config import ARTIFACTS
from ..core.store import get_store
from ..search.index import search


@lru_cache(maxsize=1)
def atlas() -> dict:
    return json.loads((ARTIFACTS / "atlas.json").read_text(encoding="utf-8"))


def node(nid: str) -> dict | None:
    return next((n for n in atlas()["nodes"] if n["id"] == nid), None)


def neighbors(nid: str) -> list[str]:
    out = []
    for e in atlas()["edges"]:
        if e["source"] == nid:
            out.append(e["target"])
        elif e["target"] == nid:
            out.append(e["source"])
    return out


def _cite_rows(ids: list[str], field: str, op: str) -> dict:
    return {"kind": "aggregate", "op": op, "field": field, "rows": ids}


def key_numbers(t: pd.DataFrame) -> list[dict]:
    vm = config.variables()
    out = [{"label": "tests", "value": str(len(t)), "unit": "", "citation": _cite_rows(t.test_id.tolist(), "test_id", "count")}]
    if t.empty:
        return [{"label": "tests", "value": "no data", "unit": "", "nodata": True}]
    clean = t[t["flags"].map(len) == 0] if "flags" in t.columns else t
    nflag = len(t) - len(clean)
    if nflag:
        out.append({"label": "flagged", "value": str(nflag), "unit": "rows", "flagged": True,
                    "citation": _cite_rows(t[t["flags"].map(len) > 0].test_id.tolist(), "test_id", "count")})
    for v in ["o2_frac", "pressure_kpa", "flow_cm_s", "d0_mm"]:
        col = clean[v].dropna()
        if len(col) and col.nunique() > 1:
            sc = vm[v].get("display_scale", 1)
            out.append({"label": vm[v]["label"], "value": f"{col.min() * sc:.3g}–{col.max() * sc:.3g}",
                        "unit": vm[v].get("display_unit", vm[v].get("unit", "")), "var": v,
                        "citation": _cite_rows(col.index.tolist(), v, "min")})
    b = t["burned"].dropna()
    if len(b):
        out.append({"label": "sustained burning", "value": f"{int(b.sum())}/{len(b)}", "unit": "tests", "var": "burned",
                    "citation": _cite_rows(b.index.tolist(), "burned", "share")})
    for v in ["burn_rate_k_mm2_s", "spread_rate_mm_s"]:
        col = t[v].dropna()
        if len(col):
            out.append({"label": f"median {vm[v]['label'].lower()}", "value": f"{col.median():.3g}", "unit": vm[v]["unit"],
                        "var": v, "citation": _cite_rows(col.index.tolist(), v, "median")})
    return out


def passages_for(terms: str, investigation: str | None = None, k: int = 3) -> list[dict]:
    st = get_store()
    res = search(terms, k=12, types=["passage"], investigation=investigation)["results"]
    out = []
    for r in res[:k]:
        ch = st.chunks.loc[r["chunk_id"]]
        doc = st.documents.loc[ch.doc_id]
        words = [w.lower() for w in terms.replace("—", " ").split() if len(w) > 2]
        sents = [s.strip() for s in ch.text.replace("  ", " ").split(". ") if s.strip()]
        hl = [s if s.endswith(".") else s + "." for s in sents if any(w in s.lower() for w in words)][:2]
        out.append({"chunk_id": ch.id, "doc_id": ch.doc_id, "doc_title": doc.title, "page": int(ch.page),
                    "section": ch.section, "text": ch.text, "highlights": hl, "demo": bool(doc.demo)})
    return out


def compare_strip(focus: dict, others: list[dict]) -> dict:
    attrs = [("pillars", "Pillar"), ("hardware", "Hardware"), ("fuel_phase", "Fuel phase"), ("platform", "Platform"),
             ("years", "Years"), ("o2_frac", "O₂ range"), ("pressure_kpa", "Pressure range"), ("flow_cm_s", "Flow range"),
             ("n_tests", "Tests in corpus")]

    def val(n, a):
        if a in ("o2_frac", "pressure_kpa", "flow_cm_s"):
            s = n.get("stats", {}).get(a)
            if not s:
                return None
            sc = 100 if a == "o2_frac" else 1
            return f"{s[0] * sc:.3g}–{s[2] * sc:.3g}"
        if a == "n_tests":
            return str(n.get("stats", {}).get("n_tests", 0)) or None
        if a == "years":
            y = n.get("years")
            return f"{y[0]}–{y[1]}" if y else None
        if a == "pillars":
            return ", ".join(n.get("pillars", []))
        return n.get(a)
    rows = []
    for a, label in attrs:
        fv = val(focus, a)
        cells = [{"id": o["label"], "value": val(o, a)} for o in others]
        same = all(c["value"] == fv for c in cells) if cells else True
        rows.append({"attr": a, "label": label, "focus": fv, "others": cells,
                     "status": "held constant" if same and fv is not None else "varied"})
    return {"focus": focus["label"], "others": [o["label"] for o in others], "rows": rows}


def next_paths(nid: str, parsed: dict | None = None) -> list[dict]:
    n = node(nid)
    if not n:
        return []
    chips = []
    conds = (parsed or {}).get("conditions") or {}
    if n["type"] == "investigation":
        sibs = [node(x) for x in neighbors(nid)]
        same = [o for o in atlas()["nodes"] if o["type"] == "investigation" and o["id"] != nid and
                (o["fuel_phase"] == n["fuel_phase"] or o["hardware"] == n["hardware"])]
        same.sort(key=lambda o: (o["fuel_phase"] != n["fuel_phase"], o["label"]))
        for o in same[:2]:
            chips.append({"label": f"compare with {o['label']}", "kind": "compare", "node": o["id"], "with": nid})
        if n.get("datasets"):
            if "o2_frac" in conds:
                chips.append({"label": f"tests near {conds['o2_frac'] * 100:.0f}% O₂", "kind": "node",
                              "node": f"ds:{n['datasets'][0]}", "conditions": conds})
            else:
                chips.append({"label": "tests in this dataset", "kind": "node", "node": f"ds:{n['datasets'][0]}"})
            chips.append({"label": "what-if in Scenario Lab", "kind": "route",
                          "href": f"/lab?mode={'droplet' if 'flex' in n['datasets'][0] else 'solid'}"})
        for p in n["pillars"]:
            rel = [o for o in atlas()["nodes"] if o["type"] == "investigation" and p in o["pillars"] and o["id"] != nid]
            if rel:
                chips.append({"label": f"related {p} studies", "kind": "lens", "lens": "pillar", "focus": [r["id"] for r in rel]})
                break
        ps = passages_for(n["label"], n["label"], k=1)
        if ps:
            chips.append({"label": f"source {ps[0]['section'].split(' ')[0]} p.{ps[0]['page']}", "kind": "source",
                          "chunk": ps[0]["chunk_id"], "doc": ps[0]["doc_id"], "page": ps[0]["page"]})
        for s in sibs:
            if s and s["type"] == "concept":
                chips.append({"label": f"concept: {s['label']}", "kind": "node", "node": s["id"]})
                break
    elif n["type"] == "concept":
        for i in n["investigations"][:3]:
            chips.append({"label": i, "kind": "node", "node": f"inv:{i}"})
        ps = passages_for(n["label"], k=1)
        if ps:
            chips.append({"label": f"source p.{ps[0]['page']}", "kind": "source", "chunk": ps[0]["chunk_id"],
                          "doc": ps[0]["doc_id"], "page": ps[0]["page"]})
        if n["id"] in ("concept:exploration-atmosphere", "concept:partial-gravity-gap", "concept:o2-partial-pressure"):
            chips.append({"label": "gap map vs Moon base", "kind": "route", "href": "/studio?chart=gap"})
    elif n["type"] == "dataset":
        ds = nid.split(":", 1)[1]
        chips.append({"label": "chart in Insight Studio", "kind": "route", "href": f"/studio?dataset={ds}"})
        chips.append({"label": "cleaning pipeline", "kind": "route", "href": f"/refinery?dataset={ds}"})
        chips.append({"label": "relationships", "kind": "lens", "lens": "relationships", "dataset": ds})
        for i in n["investigations"][:2]:
            chips.append({"label": i, "kind": "node", "node": f"inv:{i}"})
    elif n["type"] == "cluster":
        chips.append({"label": "parent dataset", "kind": "node", "node": f"ds:{n['dataset']}"})
        sib = [o for o in atlas()["nodes"] if o["type"] == "cluster" and o.get("dataset") == n["dataset"] and o["id"] != nid]
        if sib:
            chips.append({"label": "neighbouring group", "kind": "node", "node": sib[0]["id"]})
        chips.append({"label": "plot these tests", "kind": "route", "href": f"/studio?dataset={n['dataset']}&group={nid}"})
    elif n["type"] == "document":
        for i in n["investigations"][:3]:
            chips.append({"label": i, "kind": "node", "node": f"inv:{i}"})
    return chips


def focus_view(nid: str, role: str = "researcher") -> dict:
    st = get_store()
    n = node(nid)
    if not n:
        return {"error": "unknown node"}
    out = {"node": n, "paths": next_paths(nid), "role": role}
    if n["type"] == "investigation":
        inv = st.investigations.loc[n["label"]]
        t = st.usable_tests()
        t = t[t.investigation_id == n["label"]]
        out["definition"] = inv.objectives
        out["meta"] = {"PSI id": inv.psi_id or "to be filled from PSI", "DOI": inv.doi or "to be filled from PSI",
                       "platform": inv.platform, "hardware": inv.hardware, "years": json.loads(inv.years),
                       "license": inv.license, "source": json.loads(inv.source_urls)}
        out["numbers"] = key_numbers(t)
        out["visual"] = ("envelope" if n["fuel_phase"] == "solid" else "d2" if n["fuel_phase"] == "liquid droplet"
                         else "sensor" if n["fuel_phase"] in ("smoke", "dust") else "gasflame")
        if out["visual"] == "envelope" and len(t):
            out["visual_data"] = t[["test_id", "o2_frac", "flow_cm_s", "burned", "gravity_g"]].dropna(subset=["burned"]).to_dict("records")
        if out["visual"] == "d2" and len(t):
            sub = t.dropna(subset=["burn_rate_k_mm2_s", "d0_mm"]).sort_values("burn_rate_k_mm2_s")
            pick = sub.iloc[np.linspace(0, len(sub) - 1, min(7, len(sub))).astype(int)] if len(sub) else sub
            out["visual_data"] = pick[["test_id", "d0_mm", "burn_rate_k_mm2_s", "o2_frac", "fuel", "diluent"]].to_dict("records")
        sims = [node(f"inv:{o['label']}") for o in atlas()["nodes"] if o["type"] == "investigation" and o["id"] != nid
                and (o["fuel_phase"] == n["fuel_phase"] or o["hardware"] == n["hardware"])][:3]
        out["compare"] = compare_strip(n, [s for s in sims if s])
        out["passages"] = passages_for(f"{n['label']} {n['name']}", n["label"], k=3)
        if not t.empty and n.get("datasets"):
            out["groups"] = group_tests(st.tests.reset_index(drop=True), n["datasets"][0])
    elif n["type"] == "concept":
        c = st.concepts.set_index("id").loc[nid.split(":", 1)[1]]
        out["definition"] = c.definition
        out["plain"] = c.plain
        out["passages"] = passages_for(f"{c['name']} {' '.join(json.loads(c.terms)[:3])}", k=3)
        out["numbers"] = []
        out["visual"] = "concept"
    elif n["type"] == "dataset":
        ds = nid.split(":", 1)[1]
        cfg = config.datasets()[ds]
        t = st.usable_tests(ds)
        out["definition"] = cfg["title"]
        out["meta"] = {"adapter": cfg["adapter"], "license": cfg.get("license"), "files": cfg["files"], "demo": cfg.get("demo")}
        out["numbers"] = key_numbers(t)
        out["groups"] = group_tests(st.tests.reset_index(drop=True), ds)
        out["groups_campaign"] = group_tests(st.tests.reset_index(drop=True), ds, mode="campaign")
        out["visual"] = "groups"
    elif n["type"] == "cluster":
        ds = n["dataset"]
        g = next((g for g in group_tests(st.tests.reset_index(drop=True), ds) if g["id"] == nid), None)
        out["definition"] = f"Auto-group in {ds}: {n['label']}"
        out["group"] = g
        if g:
            t = st.tests.loc[g["test_ids"]]
            out["numbers"] = key_numbers(t)
            out["tests"] = json.loads(t.drop(columns=["flags", "image_derived"]).to_json(orient="records"))
        out["visual"] = "tests"
    elif n["type"] == "document":
        d = st.documents.loc[nid.split(":", 1)[1]]
        ch = st.chunks[st.chunks.doc_id == d.id]
        out["definition"] = d.citation
        out["sections"] = [{"chunk_id": r.id, "section": r.section, "page": int(r.page), "text": r.text} for _, r in ch.iterrows()]
        out["numbers"] = [{"label": "pages", "value": str(int(d.pages)), "unit": ""}]
        out["visual"] = "document"
    return out
