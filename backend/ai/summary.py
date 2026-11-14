"""POST /api/ai/summary: 2–3 sentences on the filtered set, citing resource ids, naming gaps.

The template (the prototype's aiSummary, with gaps computed from the data) is always available and is the
fallback when no ANTHROPIC_API_KEY is set. Citations are `[resource_id]` markers in the text.
"""
from __future__ import annotations

from ..catalog.query import catalog

SOLIDS = {"fabric", "pmma", "other"}


def lower_label(label: str) -> str:
    """'Moon base' → 'moon base', but 'ISS cabin' stays 'ISS cabin'."""
    return " ".join(w if w.isupper() else w.lower() for w in label.split(" "))


def context(filters: dict, sort: str, sim: dict) -> dict:
    """The filtered, sorted resources and the facts the summary may use."""
    c = catalog()
    res = c.query(filters, sort, sim, 1, 500)
    items = [c.res[i["id"]] for i in res["items"]]
    preset = c.preset_by_key.get(sort[4:] if sort.startswith("fit:") else "moon") or c.presets[0]
    pts = [c.points[code] for r in items for code in r["_codes"] if code in c.points]
    partial_g = [p for p in pts if p.get("gravity_g") is not None and 0.02 < p["gravity_g"] < 0.95]
    low_p_solid = [p for p in pts if p.get("material") in SOLIDS and p.get("pressure_kpa") is not None and p["pressure_kpa"] < 90]
    gaps = []
    if preset["env"] == "partial" and not partial_g:
        gaps.append("No source here measures flames at partial gravity yet.")
    if preset["psi"] < 14 and not low_p_solid:
        gaps.append("None of these sources has a solid-material test below sea-level pressure.")
    return {"items": items, "preset": preset, "gaps": gaps, "total": res["total"], "catalog": c}


def template(filters: dict, sort: str, sim: dict) -> dict:
    ctx = context(filters, sort, sim)
    items, preset, c = ctx["items"], ctx["preset"], ctx["catalog"]
    if not items:
        return {"text": "No sources match these filters.", "citations": [], "source": "template", "model": None}
    scored = [r for r in items if r["credibility"]["score"] is not None]
    top = scored if sort.startswith("fit:") else sorted(scored, key=lambda r: -c.fit(r, preset))
    top = top[:2]
    if top:
        text = f"For the {lower_label(preset['label'])}, start with " + " and ".join(f"“{r['title']}” [{r['id']}]" for r in top) + ". "
    else:
        text = "Only unverified placeholders match. "
    text += " ".join(ctx["gaps"])
    return {"text": text.strip(), "citations": [r["id"] for r in top], "source": "template", "model": None}


def summarize(filters: dict, sort: str, sim: dict) -> dict:
    return template(filters, sort, sim)
