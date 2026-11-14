"""NASA Technical Reports Server (SPEC §6.3).

    python -m backend.ingest ntrs --fetch   network: query NTRS for every investigation, write the snapshot
                                            data/raw/ntrs/ntrs_records.json (commit it, like the PSI tables)
    python -m backend.ingest ntrs           offline: register the snapshot's records as resources

Endpoint checked 2026-11-14: GET https://ntrs.nasa.gov/api/citations/search?q=...&page.size=N returns
{"stats": {...}, "results": [{id, title, abstract, stiType, stiTypeDetails, authorAffiliations, publications,
downloads, downloadsAvailable, onlyAbstract, keywords, distributionDate, ...}]}; citation pages are
https://ntrs.nasa.gov/citations/<id>.
A record is kept for an investigation only if its title, abstract or keywords name that investigation
(its acronym as a whole word, or its full name).
"""
from __future__ import annotations

import json
import re
import time
from datetime import datetime, timezone

import pandas as pd
import yaml

from ..core.config import CONFIG, RAW
from .build import read, write
from .groups import MEMBER_TO_GROUP

API = "https://ntrs.nasa.gov/api/citations/search"
SNAPSHOT = RAW / "ntrs" / "ntrs_records.json"
PER_INVESTIGATION = 12
TYPE = {"JOURNAL_ARTICLE": "paper", "CONFERENCE_PAPER": "paper", "PRESENTATION": "slides", "POSTER": "slides",
        "TECHNICAL_MEMORANDUM": "report", "TECHNICAL_REPORT": "report", "CONTRACTOR_REPORT": "report",
        "TECHNICAL_PUBLICATION": "report", "CONFERENCE_PUBLICATION": "report", "OTHER": "report"}
# §7 factors: NTRS publisher 0.85; review 1.0 peer-reviewed journal, 0.8 NTRS technical review, 0.6 presentation;
# traceability 0.8 when the full text (numbers and methods) is downloadable, 0.6 for an abstract only.
REVIEW = {"paper_journal": 1.0, "paper": 0.8, "report": 0.8, "slides": 0.6}


def _names() -> list[dict]:
    inv = yaml.safe_load((CONFIG / "investigations.yaml").read_text(encoding="utf-8"))["investigations"]
    return [{"id": i["id"], "name": i["name"]} for i in inv if i["id"] in MEMBER_TO_GROUP]


def _mentions(rec: dict, inv: dict) -> bool:
    hay = " ".join([rec.get("title") or "", rec.get("abstract") or "", " ".join(rec.get("keywords") or [])])
    if inv["name"].lower() in hay.lower():
        return True
    acr = re.escape(inv["id"])
    return re.search(rf"(?<![A-Za-z0-9-]){acr}(?![A-Za-z0-9-])", hay) is not None


def _trim(r: dict) -> dict:
    pdf = next((d["links"]["pdf"] for d in r.get("downloads") or [] if d.get("links", {}).get("pdf")), None)
    date = next((p.get("publicationDate") for p in r.get("publications") or [] if p.get("publicationDate")), None) or r.get("distributionDate")
    return {"id": str(r["id"]), "title": r.get("title"), "abstract": (r.get("abstract") or "")[:2000],
            "stiType": r.get("stiType"), "stiTypeDetails": r.get("stiTypeDetails"),
            "authors": [a["meta"]["author"]["name"] for a in r.get("authorAffiliations") or [] if a.get("meta", {}).get("author")][:8],
            "date": (date or "")[:10] or None, "pdf": f"https://ntrs.nasa.gov{pdf}" if pdf else None,
            "downloadsAvailable": bool(r.get("downloadsAvailable")), "onlyAbstract": bool(r.get("onlyAbstract")),
            "keywords": r.get("keywords") or [], "publications": [p.get("publicationName") for p in r.get("publications") or [] if p.get("publicationName")]}


def fetch(get=None) -> dict:
    """Network step. `get(url, params) -> dict` can be injected for tests."""
    if get is None:
        import httpx

        def get(url, params):
            r = httpx.get(url, params=params, timeout=30, headers={"User-Agent": "freefall-atlas-ingest/1.0"})
            r.raise_for_status()
            return r.json()
    records: dict[str, dict] = {}
    queries = []
    for inv in _names():
        kept = 0
        for q in (f'"{inv["name"]}"', f'"{inv["id"]}" microgravity combustion'):
            data = get(API, {"q": q, "page.size": 25})
            queries.append({"investigation": inv["id"], "q": q, "total": data.get("stats", {}).get("total")})
            for r in data.get("results", []):
                t = _trim(r)
                if not _mentions(t, inv):
                    continue
                rec = records.setdefault(t["id"], {**t, "investigations": []})
                if inv["id"] not in rec["investigations"] and kept < PER_INVESTIGATION:
                    rec["investigations"].append(inv["id"])
                    kept += 1
            time.sleep(0.3)
    snap = {"retrieved_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "endpoint": API, "queries": queries,
            "records": sorted((r for r in records.values() if r["investigations"]), key=lambda r: r["id"])}
    SNAPSHOT.parent.mkdir(parents=True, exist_ok=True)
    SNAPSHOT.write_text(json.dumps(snap, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"ntrs --fetch: {len(snap['records'])} records for {len(_names())} investigations → {SNAPSHOT}")
    return {"records": len(snap["records"])}


def resources_from(snapshot: dict) -> pd.DataFrame:
    rows = []
    for r in snapshot.get("records", []):
        typ = TYPE.get(r.get("stiType") or "OTHER", "report")
        journal = r.get("stiType") == "JOURNAL_ARTICLE"
        groups = list(dict.fromkeys(MEMBER_TO_GROUP[i] for i in r["investigations"] if i in MEMBER_TO_GROUP))
        full = r.get("downloadsAvailable") and not r.get("onlyAbstract")
        authors = r.get("authors") or []
        byline = (authors[0] + (" et al." if len(authors) > 1 else "")) if authors else None
        rows.append({
            "id": f"ntrs-{r['id']}", "investigation": groups[0] if groups else None, "investigations": json.dumps(groups),
            "investigation_detail": ", ".join(r["investigations"]), "type": typ, "title": r["title"],
            "publisher": "NASA NTRS" + (f" · {r['publications'][0]}" if journal and r.get("publications") else ""),
            "year": int(r["date"][:4]) if r.get("date") else None, "format": "PDF" if full else "Abstract",
            "url": f"https://ntrs.nasa.gov/citations/{r['id']}", "s3_key": None, "doi": None, "psi_id": None,
            "description": ((byline + ". ") if byline else "") + (r.get("abstract") or r.get("stiTypeDetails") or "")[:600],
            "cred_publisher": 1.0 if journal else 0.85, "cred_review": REVIEW["paper_journal"] if journal else REVIEW[typ],
            "cred_trace": 0.8 if full else 0.6, "status": "published", "envs_override": None,
            "origin": "ntrs", "dataset": None, "doc_id": None, "pdf_url": r.get("pdf"),
        })
    return pd.DataFrame(rows)


def run() -> dict:
    res = read("atlas_resources")
    if res.empty:
        raise SystemExit("Run `python -m backend.ingest existing` first.")
    # Seed rows are dropped here and re-added by `ingest seed`, which runs next and skips any seed row that an
    # NTRS record now covers: a real record must never lose to its seed stand-in.
    res = res[~res.origin.isin(["ntrs", "seed"])]
    if not SNAPSHOT.exists():
        print("ntrs: no snapshot (data/raw/ntrs/ntrs_records.json); run `python -m backend.ingest ntrs --fetch` once.")
        write({"atlas_resources": res})
        return {"resources": 0}
    snap = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    new = resources_from(snap)
    new = new[~new.url.isin(set(res.url.dropna()))]
    out = pd.concat([res, new], ignore_index=True)
    write({"atlas_resources": out})
    summary = {"resources": len(new), "by_type": new.type.value_counts().to_dict(), "snapshot": snap.get("retrieved_utc")}
    print("ntrs:", summary)
    return summary
