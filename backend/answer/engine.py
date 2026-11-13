"""Answer Engine: extractive first. Retrieve passages and rows → compose structured blocks
from them (template) → optional LLM rephrase → verify every sentence → grade or abstain."""
from __future__ import annotations

import re
import time

import numpy as np
import pandas as pd

from ..atlas import tests_near
from ..core import config
from ..core.store import get_store
from ..llm import get_llm
from ..search.index import search
from ..search.query_parser import parse
from ..search.text import tokens
from .verifier import verify_blocks

PASSAGE_MIN_SCORE = 0.022       # fused RRF score below which a passage is "not relevant"
MEASURED_D = 0.35
SENT_SPLIT = re.compile(r"(?<=[.!?])\s+(?=[A-Z])")


def _metric_for(q: str, ds: str) -> str:
    ql = q.lower()
    if ds == "flex":
        if re.search(r"extinction diameter|d_ext", ql):
            return "extinction_d_mm"
        if re.search(r"\brate\b|\bk\b|d2|d²|burning rate|how fast", ql):
            return "burn_rate_k_mm2_s"
    if ds == "solids" and re.search(r"spread|rate|how fast", ql):
        return "spread_rate_mm_s"
    return "burned"


# solid-material tests in orbit with an oxygen level (BASS-II, SAFFIRE); BASS has none and is only a run list
SOLID_DS = ["bass2", "saffire1", "saffire2", "saffire3"]
DATASETS = {"solids": SOLID_DS}


def _datasets_for(p, q: str) -> list[str]:
    ql = q.lower()
    out = []
    if "fuel" in p.categories or re.search(r"droplet|drop\b|liquid|fuel|flex|heptane|methanol|decane|ethanol|d2|d²", ql):
        out.append("flex")
    if "material" in p.categories or re.search(r"solid|material|spread|fabric|pmma|acrylic|bass|saffire|flow|ventilat|cotton|nomex|silicone|sibal", ql):
        out.append("solids")
    if re.search(r"\bgas\b|gaseous|burner|\bjet\b|ethylene|propane|butane|ethane|methane|cfi-?g|acme|cool flame", ql):
        out.append("cfig_normal")
    if not out and (p.conditions or p.categories):
        out = ["solids", "flex", "cfig_normal"]
    return out


# what each dataset's tests are called, and what burned = 1 means for them
DATASET_NOUN = {"flex": "droplet", "solids": "real solid-material", "cfig_normal": "gas-flame (CFI-G)"}
SUSTAINED = {"cfig_normal": "were still burning when the fuel flow was stopped (the rest went out by themselves)",
             "solids": "burned the whole sample"}


def _best_sentences(text: str, core: set[str], k: int = 2) -> list[str]:
    """Sentences sharing at least min(2, |core|) query terms (synonyms expanded on the sentence side)."""
    need = min(2, len(core)) or 1
    sents = [s.strip() for s in SENT_SPLIT.split(text) if len(s.strip()) > 20]
    scored = sorted(((len(core & set(tokens(s, expand=True))), -i, s) for i, s in enumerate(sents)), reverse=True)
    return [s for sc, _, s in scored[:k] if sc >= need]


def _fmt(v: float, var: str) -> str:
    meta = config.variables().get(var, {})
    if var == "o2_frac":
        return f"{v * 100:.1f}"
    if abs(v) >= 100:
        return f"{v:.0f}"
    return f"{v:.2f}"


def answer(q: str, role: str = "researcher") -> dict:
    t0 = time.perf_counter()
    st = get_store()
    p = parse(q)
    qtok = set(tokens(q))
    sr = search(q, k=30)
    passages = [r for r in sr["results"] if r["type"] == "passage"][:6]
    strong = [r for r in passages if r["score"] >= PASSAGE_MIN_SCORE and r["bm25"] > 0.5]

    sentences: list[dict] = []
    numbers: list[dict] = []
    data_blocks: list[dict] = []
    grade = "No data"
    chart = None
    tests = st.tests

    # ---------------- data evidence
    gaps: list[dict] = []
    for ds in _datasets_for(p, q):
        metric = _metric_for(q, ds)
        sel_ds = DATASETS.get(ds, ds)
        dst = st.usable_tests(sel_ds)
        cats = {k: v for k, v in p.categories.items() if k in dst.columns and (dst[k] == v).any()}
        conds = {k: v for k, v in p.conditions.items() if k in dst.columns and dst[k].notna().any() and k != "gravity_g"}
        if conds:
            near = tests_near(tests, conds, cats, k=40, dataset=sel_ds)
            close_d = config.models_cfg().get("applicability", {}).get("close_conditions_distance", 1.0)
            rows = [r for r in near if r["distance"] <= close_d]
            # a named material or fuel is a filter, not a preference: never count another one's tests for it
            rows = [r for r in rows if all(tests.loc[r["test_id"], k] == v for k, v in cats.items())]
            o2q = conds.get("o2_frac")
            if ds == "solids" and o2q is not None and not any(abs(tests.loc[r["test_id"], "o2_frac"] - o2q) <= 0.02 for r in rows):
                # no solid test at this oxygen level: say where solid testing stopped (a verified fact, not a refusal)
                pool = dst if not cats else dst[(dst[list(cats)] == pd.Series(cats)).all(axis=1)]
                pool = pool[pool.o2_frac.notna()]
                if len(pool):
                    who = " ".join(str(v) for v in cats.values()) or "solid material"
                    edge = "highest" if o2q > pool.o2_frac.max() else "lowest" if o2q < pool.o2_frac.min() else None
                    if edge:
                        val = pool.o2_frac.max() if edge == "highest" else pool.o2_frac.min()
                        ids = pool.test_id.tolist()
                        gaps.append({"text": f"No real {who} test in orbit was run near O₂ {o2q * 100:.0f}%: the {edge} oxygen level "
                                             f"among the {len(ids)} loaded {who} tests is {val * 100:.1f}%.",
                                     "citations": [{"kind": "aggregate", "op": "max" if edge == "highest" else "min", "field": "o2_frac",
                                                    "rows": ids, "display": f"{val * 100:.1f}"},
                                                   {"kind": "aggregate", "op": "count", "field": "o2_frac", "rows": ids, "display": str(len(ids))},
                                                   {"kind": "query", "text": f"O₂ {o2q * 100:.0f}%"}],
                                     "role": "key", "dataset": ds})
                rows = []
            sel_grade = "Measured" if rows and min(r["distance"] for r in rows) <= MEASURED_D else ("Close conditions" if rows else None)
            ids = [r["test_id"] for r in rows][:25]
        elif cats:
            sub = dst
            for k, v in cats.items():
                sub = sub[sub[k] == v]
            ids = sub["test_id"].tolist()
            sel_grade = "Measured" if ids else None
        else:
            continue
        if p.conditions.get("gravity_g") == 1.0 and "gravity_g" in dst.columns:
            ids = [i for i in ids if tests.loc[i, "gravity_g"] >= 0.5]
        if not ids:
            continue
        sub = tests.loc[ids]
        vals = sub[metric].dropna()
        ids_m = vals.index.tolist()
        if not ids_m:
            if ds == "solids":                       # real tests exist here, but their tables give no outcome
                sentences.append({"text": f"{len(ids)} {DATASET_NOUN[ds]} tests in orbit were run near "
                                          f"{', '.join(c['text'] for c in p.chips if c['var'] in conds or c['var'] in cats) or 'these conditions'}; "
                                          "their tables do not record whether the flame kept burning.",
                                  "citations": [{"kind": "aggregate", "op": "count", "field": "o2_frac", "rows": ids, "display": str(len(ids))},
                                                {"kind": "query", "text": q}],
                                  "role": "key", "dataset": ds})
                data_blocks.append({"dataset": ds, "metric": "test_id", "test_ids": ids, "grade": sel_grade, "demo": False})
                grade = sel_grade if grade == "No data" or sel_grade == "Measured" else grade
            continue
        cond_txt = ", ".join(c["text"] for c in p.chips if c["var"] in conds or c["var"] in cats)
        if p.environment:
            env = ", ".join(f"{config.variables()[k]['short']} {_fmt(v, k)}{'%' if k == 'o2_frac' else ' kPa'}"
                            for k, v in conds.items() if k in ("o2_frac", "pressure_kpa"))
            cond_txt = f"{p.environment} conditions ({env})" if env else f"{p.environment} conditions"
        cond_txt = cond_txt or "the matched conditions"
        qcite = {"kind": "query", "text": cond_txt + " " + q}
        dlabel = DATASET_NOUN.get(ds, "")
        if metric == "burned":
            nb = int(vals.sum())
            s = {"text": f"{nb} of {len(ids_m)} {dlabel} tests near {cond_txt} {SUSTAINED.get(ds, 'sustained burning')}.",
                 "citations": [{"kind": "aggregate", "op": "count_true", "field": "burned", "rows": ids_m, "display": str(nb)},
                               {"kind": "aggregate", "op": "count", "field": "burned", "rows": ids_m, "display": str(len(ids_m))}, qcite],
                 "role": "key", "dataset": ds}
            numbers.append({"label": "sustained burning", "value": f"{nb}/{len(ids_m)}", "unit": "tests", "var": "burned",
                            "citation": {"kind": "aggregate", "op": "share", "field": "burned", "rows": ids_m}})
        else:
            med = float(np.median(vals))
            unit = config.variables()[metric].get("unit", "")
            lab = config.variables()[metric]["label"]
            s = {"text": f"Median {lab.lower()} across {len(ids_m)} {dlabel} tests near {cond_txt} was {_fmt(med, metric)} {unit} "
                         f"(range {_fmt(vals.min(), metric)}–{_fmt(vals.max(), metric)}).",
                 "citations": [{"kind": "aggregate", "op": "count", "field": metric, "rows": ids_m, "display": str(len(ids_m))},
                               {"kind": "aggregate", "op": "median", "field": metric, "rows": ids_m, "display": _fmt(med, metric)},
                               {"kind": "aggregate", "op": "min", "field": metric, "rows": ids_m, "display": _fmt(vals.min(), metric)},
                               {"kind": "aggregate", "op": "max", "field": metric, "rows": ids_m, "display": _fmt(vals.max(), metric)}, qcite],
                 "role": "key", "dataset": ds}
            numbers.append({"label": lab, "value": _fmt(med, metric), "unit": unit, "var": metric, "note": "median",
                            "citation": {"kind": "aggregate", "op": "median", "field": metric, "rows": ids_m}})
        sentences.append(s)
        for v in ["o2_frac", "pressure_kpa", "flow_cm_s", "d0_mm"]:
            col = sub[v].dropna()
            if len(col) and col.nunique() > 1 and (v in conds or v in ("o2_frac", "pressure_kpa")):
                meta = config.variables()[v]
                numbers.append({"label": f"{meta['label']} span", "value": f"{_fmt(col.min(), v)}–{_fmt(col.max(), v)}",
                                "unit": meta.get("display_unit", meta.get("unit", "")), "var": v,
                                "citation": {"kind": "aggregate", "op": "min", "field": v, "rows": col.index.tolist()}})
        data_blocks.append({"dataset": ds, "metric": metric, "test_ids": ids_m, "grade": sel_grade,
                            "demo": bool(sub["demo"].any())})
        grade = sel_grade if grade == "No data" or sel_grade == "Measured" else grade
        if chart is None and ds != "solids":         # solid tables record no pressure: no oxygen–pressure chart for them
            xv = "o2_frac"
            yv = "pressure_kpa"
            chart = {"type": "scatter", "dataset": ds, "x": xv, "y": yv, "color": "burned" if metric == "burned" else metric,
                     "highlight": ids_m, "marker": {k: v for k, v in p.conditions.items() if k in (xv, yv)}}

    if gaps:
        sentences.extend(gaps)
        if grade == "No data":
            grade = "Not tested"

    # ---------------- passage evidence
    passage_blocks = []
    for r in strong[:4]:
        ch = st.chunks.loc[r["chunk_id"]]
        best = _best_sentences(ch.text, qtok, k=2)
        if not best:
            continue
        doc = st.documents.loc[ch.doc_id]
        passage_blocks.append({"chunk_id": ch.id, "doc_id": ch.doc_id, "doc_title": doc.title, "page": int(ch.page),
                               "section": ch.section, "text": ch.text, "highlights": best, "score": r["score"],
                               "demo": bool(doc.demo)})
        for b in best[:1]:
            sentences.append({"text": b, "citations": [{"kind": "chunk", "target": ch.id, "span": b, "page": int(ch.page)}],
                              "role": "source", "doc_id": ch.doc_id})
    if grade == "No data" and passage_blocks:
        grade = "Documented"

    # ---------------- optional rephrase (LLM), then verify
    llm = get_llm()
    if llm.name != "none":
        for s in sentences:
            if s["role"] == "key":
                try:
                    alt = llm.rephrase(s["text"], role)
                    s["template_text"] = s["text"]
                    s["text"] = alt
                except Exception:
                    pass
    kept, dropped = verify_blocks(sentences, st.chunks, tests)
    for d in dropped:   # fall back to template text when the rephrase failed verification
        if d.get("template_text"):
            d2 = {**d, "text": d["template_text"]}
            ok, _ = verify_blocks([d2], st.chunks, tests)
            if ok:
                kept += ok
    if not kept:
        grade = "No data"

    caveats = []
    if p.partial_gravity or (p.conditions.get("gravity_g") not in (None, 0.0, 1.0)):
        caveats.append({"kind": "partial_gravity",
                        "text": "No partial-gravity combustion data exist in PSI. Microgravity and 1g results only bound this case."})
    if any(b["demo"] for b in data_blocks):
        caveats.append({"kind": "demo", "text": "Evidence comes from the demo fixture (synthetic) — not NASA results."})
    elif any(pb["demo"] for pb in passage_blocks):
        caveats.append({"kind": "notes", "text": "Some quoted passages come from context notes compiled by the platform authors, not from NASA documents."})
    if re.search(r"rocket|propellant|thruster|engine", q.lower()):
        caveats.append({"kind": "scope", "text": "Rockets and propellants are out of scope for this platform."})

    abstain = grade == "No data"
    nearest = []
    if abstain:
        pool = sr["results"] or search(q, k=4, min_dense=-1.0)["results"]
        nearest = [{"id": r["id"], "type": r["type"], "title": r["title"], "node": r["node"]} for r in pool[:4]]
    return {"query": q, "parsed": p.as_dict(), "grade": grade, "abstain": abstain,
            "key": [s for s in kept if s["role"] == "key"], "sources": [s for s in kept if s["role"] == "source"],
            "numbers": numbers if not abstain else [], "passages": passage_blocks, "data": data_blocks, "chart": chart,
            "caveats": caveats, "dropped": [{"text": d["text"], "problems": d["problems"]} for d in dropped],
            "nearest": nearest, "llm": llm.name, "ms": round((time.perf_counter() - t0) * 1000, 1)}
