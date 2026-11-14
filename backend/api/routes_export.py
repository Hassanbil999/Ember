"""POST /api/export: the selected resources as a downloadable CSV (test points, a source on every row),
JSON (resources with credibility and test points) or BibTeX."""
from __future__ import annotations

import csv
import io
import json
import re
from datetime import date

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel

from ..catalog.query import catalog, public

router = APIRouter(prefix="/api", tags=["export"])

CSV_COLUMNS = ["test_id", "investigation", "investigation_detail", "sample", "material", "gravity_g", "o2_percent",
               "pressure_kpa", "flow_cm_s", "flow_direction", "diluent", "outcome", "spread_mm_s", "verified",
               "extraction", "origin", "source", "source_url", "source_location", "source_quote", "credibility"]
MIME = {"csv": "text/csv; charset=utf-8", "json": "application/json", "bibtex": "application/x-bibtex; charset=utf-8"}
EXT = {"csv": "csv", "json": "json", "bibtex": "bib"}


class ExportReq(BaseModel):
    resource_ids: list[str]
    format: str = "csv"


def _rows(ids: list[str]) -> list[dict]:
    c = catalog()
    seen, rows = set(), []
    for rid in ids:
        r = c.res[rid]
        for code in r["_codes"]:
            if code in seen or code not in c.points:
                continue
            seen.add(code)
            p = c.points[code]
            src = c.res.get(p.get("source_resource_id") or "") or r
            placeholder = p["placeholder"] and not p.get("source_resource_id")
            location = " ".join(x for x in [p.get("source_file"), p.get("source_page")] if x)
            rows.append({
                "test_id": code, "investigation": c.inv.get(p.get("investigation") or "", {}).get("name", p.get("investigation")),
                "investigation_detail": p.get("investigation_detail"), "sample": p.get("sample_desc"), "material": p.get("material"),
                "gravity_g": p.get("gravity_g"), "o2_percent": p.get("o2_pct"), "pressure_kpa": p.get("pressure_kpa"),
                "flow_cm_s": p.get("flow_cm_s"), "flow_direction": p.get("flow_direction"), "diluent": p.get("diluent"),
                "outcome": p.get("outcome"), "spread_mm_s": p.get("spread_mm_s"), "verified": "yes" if p["verified"] else "no",
                "extraction": p.get("extraction"), "origin": "NASA PSI table" if p.get("origin") == "psi" else "seed starter row (placeholder)",
                "source": "placeholder: no source yet" if placeholder else src["title"],
                "source_url": None if placeholder else src.get("url"), "source_location": location or None,
                "source_quote": p.get("source_quote"), "credibility": "unverified" if placeholder else src["credibility"]["label"],
            })
    return rows


def _csv(ids: list[str]) -> str:
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=CSV_COLUMNS, lineterminator="\n")
    w.writeheader()
    rows = _rows(ids)
    for r in rows:
        w.writerow({k: "" if v is None else v for k, v in r.items()})
    if not rows:
        buf.write("# The selected items have no test points. Choose an experiment-data item or a paper with tests.\n")
    return buf.getvalue()


def _json(ids: list[str]) -> str:
    c = catalog()
    out = []
    for rid in ids:
        r = c.res[rid]
        pts = [c.points[x] for x in r["_codes"] if x in c.points]
        out.append({**{k: v for k, v in public(r).items() if k not in ("sim_point",)}, "test_points": pts})
    return json.dumps({"exported": date.today().isoformat(), "generator": "Freefall Atlas", "resources": out}, ensure_ascii=False, indent=2, default=str)


def _bib_escape(s) -> str:
    return str(s or "").replace("{", "\\{").replace("}", "\\}").replace("&", "\\&").replace("%", "\\%")


def _bibtex(ids: list[str]) -> str:
    c = catalog()
    kind = {"paper": "article", "report": "techreport", "slides": "misc", "data": "misc", "video": "misc", "image": "misc", "news": "misc"}
    entries = []
    for rid in ids:
        r = c.res[rid]
        key = re.sub(r"[^A-Za-z0-9]+", "_", rid).strip("_")
        fields = [("title", r["title"])]
        if r["type"] == "paper":
            fields.append(("journal", r.get("publisher")))
        elif r["type"] == "report":
            fields.append(("institution", r.get("publisher")))
        else:
            fields.append(("howpublished", "NASA Physical Sciences Informatics" if r.get("origin") == "psi" else r.get("publisher")))
        fields += [("year", r.get("year")), ("doi", r.get("doi")), ("url", r.get("url"))]
        note = f"{r['type']}; credibility {r['credibility']['label']}" + (f" ({r['credibility']['score']})" if r["credibility"]["score"] is not None else "")
        if r["placeholder"]:
            note += "; placeholder, no source link yet"
        if r.get("origin") == "seed" and not r["placeholder"]:
            note += "; starter entry, check the title against the source"
        fields += [("note", note), ("urldate", date.today().isoformat())]
        body = ",\n".join(f"  {k} = {{{_bib_escape(v)}}}" for k, v in fields if v not in (None, ""))
        entries.append(f"@{kind.get(r['type'], 'misc')}{{{key},\n{body}\n}}")
    return "\n\n".join(entries) + "\n"


@router.post("/export")
def export(body: ExportReq):
    if body.format not in MIME:
        raise HTTPException(422, "format must be csv, json or bibtex")
    c = catalog()
    missing = [i for i in body.resource_ids if i not in c.res]
    if missing:
        raise HTTPException(404, f"Unknown resource ids: {', '.join(missing)}")
    if not body.resource_ids:
        raise HTTPException(422, "Select at least one resource")
    text = {"csv": _csv, "json": _json, "bibtex": _bibtex}[body.format](body.resource_ids)
    name = f"freefall-atlas-{date.today().isoformat()}.{EXT[body.format]}"
    return Response(text, media_type=MIME[body.format], headers={"Content-Disposition": f'attachment; filename="{name}"'})
