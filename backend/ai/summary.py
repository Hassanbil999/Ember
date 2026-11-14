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


SYSTEM = """You summarize NASA microgravity combustion sources for spacecraft and habitat fire-safety engineers.
Use only the sources given. Each source has a label like [S3].
Write one or two plain sentences (no markdown, no lists) that name the most useful sources for the environment
and say briefly what each offers. End every sentence with the label(s) of the source(s) it relies on, e.g. [S1] or [S1, S4].
Use only numbers that appear in the sources. Do not mention gaps or missing data: those are added separately.
Prefer sources with higher credibility; never present a placeholder as evidence."""
PROMPT_VERSION = "summary-v1"


def _source_text(r: dict, c) -> str:
    pts = [c.points[x] for x in r["_codes"] if x in c.points]
    o2 = [p["o2_pct"] for p in pts if p.get("o2_pct") is not None]
    kpa = [p["pressure_kpa"] for p in pts if p.get("pressure_kpa") is not None]
    inv = ", ".join(c.inv[i]["name"] for i in r["investigations"] if i in c.inv)
    cr = r["credibility"]
    lines = [f"Title: {r['title']}", f"Type: {r['type']}; investigation: {inv}; publisher: {r['publisher']}; year: {r['year'] or 'n/a'}",
             f"Credibility: {cr['label']}" + (f" ({cr['score']})" if cr["score"] is not None else "") + ("; PLACEHOLDER, no source link" if r["placeholder"] else ""),
             f"Description: {r['description'] or ''}"]
    if pts:
        lines.append(f"Test points: {len(pts)}" + (f"; oxygen {min(o2):g}–{max(o2):g}%" if o2 else "") + (f"; pressure {min(kpa):.0f}–{max(kpa):.0f} kPa" if kpa else ""))
    return "\n".join(lines)


def ai_summary(filters: dict, sort: str, sim: dict) -> dict:
    from . import cache, llm
    from .cite import Source, check
    ctx = context(filters, sort, sim)
    items, preset, c = ctx["items"], ctx["preset"], ctx["catalog"]
    if not items:
        return template(filters, sort, sim)
    top = [r for r in items if not r["placeholder"]][:12] or items[:12]
    sources = [Source(f"S{i + 1}", r["id"], None, r["title"], _source_text(r, c)) for i, r in enumerate(top)]
    user = (f"Environment: {preset['label']} ({preset['g']} g, {preset['o2']}% O2, {preset['psi']} psi, airflow {preset['u']} cm/s). "
            "Sources are listed most relevant first.\n\n" + "\n\n".join(f"[{s.label}]\n{s.text}" for s in sources))
    k = cache.key(PROMPT_VERSION, llm.model_name(), SYSTEM, user, ctx["gaps"])
    hit = cache.get(k)
    if hit:
        return {**hit, "cached": True}
    out = llm.complete(SYSTEM, user, max_tokens=2048)
    if out.refused:
        raise llm.AIUnavailable("The AI declined this request.")
    checked = check(out.text, sources, extra_context=user)
    if checked is None:
        raise llm.AIUnavailable("The AI answer had no valid citations.")
    text = (checked.text + " " + " ".join(ctx["gaps"])).strip()
    res = {"text": text, "citations": [x["resource_id"] for x in checked.citations], "source": "ai", "model": out.model,
           "dropped": len(checked.dropped)}
    cache.put(k, res)
    return res


def summarize(filters: dict, sort: str, sim: dict) -> dict:
    """AI summary with citations when a key is set; otherwise, or if the AI fails or cites nothing, the template."""
    from . import llm
    if llm.enabled():
        try:
            return ai_summary(filters, sort, sim)
        except llm.AIUnavailable as e:
            return {**template(filters, sort, sim), "note": f"{e} Showing the template instead."}
    return template(filters, sort, sim)
