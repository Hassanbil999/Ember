"""`python -m backend.ingest extract` (SPEC §6.6): Claude proposes test points from passages that look like
test matrices. Needs ANTHROPIC_API_KEY and costs API credits, so it is not part of `ingest all`; run it on
purpose, then review the results on /admin/verify.

Rules (enforced here, not just asked for):
- every row carries `source_page` and a verbatim `source_quote` (≤ 30 words) that contains its numbers;
  a row whose quote is not found in the passage text, or whose numbers are not in its quote, is dropped
- values outside physical ranges are dropped (O₂ 0–100 %, pressure 0–200 kPa, flow 0–100 cm/s, gravity 0–1.2 g)
- rows are written to data/curation/ai_extracted.json with extraction=ai, verified=false; `ingest curate`
  adds them to Ember, and only a person can verify them
"""
from __future__ import annotations

import json
import re

from ..answer.verifier import _matches, numbers_in
from ..catalog.build import read
from ..catalog.curate import AI_FILE, CURATION
from . import llm

MAX_PASSAGES = 40
RANGES = {"o2_pct": (0, 100), "pressure_kpa": (0, 200), "flow_cm_s": (0, 100), "gravity_g": (0, 1.2), "spread_mm_s": (0, 1000)}
MATERIALS = ["fabric", "pmma", "droplet", "gas", "other"]
OUTCOMES = ["burned", "went_out", "cool_flame", "flame", "measured"]
NUM = {"type": ["number", "null"]}
SCHEMA = {
    "type": "object",
    "properties": {"points": {"type": "array", "items": {
        "type": "object",
        "properties": {"material": {"type": "string", "enum": MATERIALS}, "sample_desc": {"type": "string"},
                       "gravity_g": NUM, "o2_pct": NUM, "pressure_kpa": NUM, "flow_cm_s": NUM, "spread_mm_s": NUM,
                       "flow_direction": {"type": ["string", "null"], "enum": ["opposed", "concurrent", "none", None]},
                       "outcome": {"type": "string", "enum": OUTCOMES}, "source_quote": {"type": "string"}},
        "required": ["material", "sample_desc", "gravity_g", "o2_pct", "pressure_kpa", "flow_cm_s", "spread_mm_s",
                     "flow_direction", "outcome", "source_quote"],
        "additionalProperties": False}}},
    "required": ["points"], "additionalProperties": False,
}
SYSTEM = """You extract measured combustion test conditions from one page of a NASA document.
Return only tests whose numbers are stated on this page. For each test give the values in these units:
gravity in Earth g (microgravity = 0), oxygen in % by volume, pressure in kPa, forced airflow in cm/s, flame spread
rate in mm/s; use null for anything the page does not state. Never estimate or convert from memory.
source_quote must be copied exactly from the page, at most 30 words, and must contain the numbers you report.
If the page states no individual test conditions, return {"points": []}."""
HINT = re.compile(r"(\d+(?:\.\d+)?\s*%\s*(?:O2|O₂|oxygen))|(oxygen[^.]{0,40}\d+(?:\.\d+)?\s*%)", re.I)
FLOWISH = re.compile(r"\d+(?:\.\d+)?\s*(?:cm/s|mm/s|kPa|atm|psi)", re.I)


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip().lower()


def candidate_passages(chunks, limit: int = MAX_PASSAGES) -> list[dict]:
    scored = []
    for c in chunks.itertuples():
        t = c.text or ""
        score = len(HINT.findall(t)) * 2 + len(FLOWISH.findall(t))
        if HINT.search(t) and FLOWISH.search(t):
            scored.append((score, {"id": c.id, "resource_id": c.resource_id, "page": int(c.page), "text": t}))
    scored.sort(key=lambda x: -x[0])
    return [p for _, p in scored[:limit]]


def validate(row: dict, passage: str) -> str | None:
    """Reason to drop the row, or None if it may be kept (unverified)."""
    q = row.get("source_quote") or ""
    if not q or len(q.split()) > 30:
        return "quote missing or longer than 30 words"
    if _norm(q) not in _norm(passage):
        return "quote not found verbatim on the page"
    qnums = [float(n) for n in numbers_in(q)]
    for k, (lo, hi) in RANGES.items():
        v = row.get(k)
        if v is None:
            continue
        if not lo <= v <= hi:
            return f"{k}={v} outside {lo}–{hi}"
        if k != "gravity_g" and not any(_matches(str(v), n) or _matches(str(n), v) for n in qnums):
            return f"{k}={v} is not in the quote"
    if row.get("o2_pct") is None:
        return "no oxygen value"
    return None


def run(complete=None) -> dict:
    if complete is None:
        if not llm.enabled():
            print("extract: skipped, no ANTHROPIC_API_KEY (this step calls Claude and costs API credits).")
            return {"skipped": True}
        complete = llm.complete
    chunks, res = read("atlas_chunks"), read("atlas_resources").set_index("id")
    existing = {p["code"]: p for p in (json.loads(AI_FILE.read_text(encoding="utf-8")) if AI_FILE.exists() else [])}
    kept, dropped = 0, []
    for p in candidate_passages(chunks):
        out = complete(SYSTEM, f"Page {p['page']} of “{res.loc[p['resource_id'], 'title']}”:\n\n{p['text']}", 4096, SCHEMA)
        if out.refused:
            continue
        try:
            rows = json.loads(out.text).get("points", [])
        except json.JSONDecodeError:
            dropped.append(f"{p['id']}: not JSON")
            continue
        for n, row in enumerate(rows):
            why = validate(row, p["text"])
            if why:
                dropped.append(f"{p['id']} #{n}: {why}")
                continue
            r = res.loc[p["resource_id"]]
            code = f"AI-{p['resource_id'].removeprefix('ntrs-').removeprefix('doc-')[:24]}-P{p['page']}-{n + 1}"
            existing[code] = {
                "code": code, "investigation": r["investigation"], "investigation_detail": r.get("investigation_detail"),
                "source_resource_id": p["resource_id"], "material": row["material"], "sample_desc": row["sample_desc"],
                "geometry": None, "gravity_g": row["gravity_g"], "o2_pct": row["o2_pct"], "pressure_kpa": row["pressure_kpa"],
                "flow_cm_s": row["flow_cm_s"], "flow_direction": row["flow_direction"], "diluent": None, "outcome": row["outcome"],
                "spread_mm_s": row["spread_mm_s"], "notes": None, "source_file": r.get("url"), "source_page": f"p. {p['page']}",
                "source_quote": row["source_quote"], "extraction": "ai", "verified": False, "dataset": None, "model": out.model,
            }
            kept += 1
    CURATION.mkdir(parents=True, exist_ok=True)
    AI_FILE.write_text(json.dumps(sorted(existing.values(), key=lambda x: x["code"]), indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"extract: {kept} points kept (unverified), {len(dropped)} dropped → {AI_FILE}. Review them on /admin/verify.")
    return {"kept": kept, "dropped": dropped}
