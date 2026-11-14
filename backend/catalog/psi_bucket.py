"""The public PSI bucket s3://nasa-psi (SPEC §6.2), anonymous access over the S3 REST API.

    python -m backend.ingest psi --discover   network: list prefixes, write data/psi_map.csv (prefix → candidate
                                              investigation) for a person to confirm (set confirmed=yes)
    python -m backend.ingest psi --fetch      network: list every file under the confirmed prefixes into the
                                              snapshot data/raw/psi_bucket/files.json (commit it)
    python -m backend.ingest psi              offline: register the snapshot's files as resources

Folder names are never hard-coded: the map is matched from the prefix names and only a person confirms it.
File types: .csv .xlsx .txt .dat → data, .mp4 .avi .mov → video, .jpg .png .tif → image, .pdf → report,
.ppt .pptx → slides. Publisher "NASA PSI"; traceability 1.0 for raw data files.
"""
from __future__ import annotations

import csv
import json
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

import pandas as pd
import yaml

from ..core.config import CONFIG, DATA, RAW
from .build import read, write
from .groups import MEMBER_TO_GROUP

BUCKET, REGION = "nasa-psi", "us-west-2"
ENDPOINT = f"https://{BUCKET}.s3.{REGION}.amazonaws.com/"
MAP = DATA / "psi_map.csv"
SNAPSHOT = RAW / "psi_bucket" / "files.json"
NS = {"s3": "http://s3.amazonaws.com/doc/2006-03-01/"}
KIND = {**dict.fromkeys(["csv", "xlsx", "xls", "txt", "dat"], "data"), **dict.fromkeys(["mp4", "avi", "mov"], "video"),
        **dict.fromkeys(["jpg", "jpeg", "png", "tif", "tiff"], "image"), "pdf": "report", **dict.fromkeys(["ppt", "pptx"], "slides")}
CRED = {"data": (1.0, 0.8, 1.0), "video": (1.0, 0.8, 0.8), "image": (1.0, 0.8, 0.8), "report": (1.0, 0.8, 0.8), "slides": (1.0, 0.6, 0.8)}


def _http_get(params: dict) -> str:
    import httpx
    r = httpx.get(ENDPOINT, params=params, timeout=30, headers={"User-Agent": "freefall-atlas-ingest/1.0"})
    r.raise_for_status()
    return r.text


def list_level(prefix: str, get=_http_get) -> tuple[list[str], list[dict]]:
    """(sub-prefixes, files) directly under one prefix, following continuation tokens."""
    prefixes, files, token = [], [], None
    while True:
        params = {"list-type": "2", "delimiter": "/", "prefix": prefix, "max-keys": "1000"}
        if token:
            params["continuation-token"] = token
        root = ET.fromstring(get(params))
        prefixes += [e.text for e in root.findall("s3:CommonPrefixes/s3:Prefix", NS)]
        files += [{"key": c.find("s3:Key", NS).text, "size": int(c.find("s3:Size", NS).text)} for c in root.findall("s3:Contents", NS)]
        nxt = root.find("s3:NextContinuationToken", NS)
        if nxt is None:
            return prefixes, files
        token = nxt.text


def list_all(prefix: str, get=_http_get, limit: int = 20000) -> list[dict]:
    files, token = [], None
    while len(files) < limit:
        params = {"list-type": "2", "prefix": prefix, "max-keys": "1000"}
        if token:
            params["continuation-token"] = token
        root = ET.fromstring(get(params))
        files += [{"key": c.find("s3:Key", NS).text, "size": int(c.find("s3:Size", NS).text)} for c in root.findall("s3:Contents", NS)]
        nxt = root.find("s3:NextContinuationToken", NS)
        if nxt is None:
            break
        token = nxt.text
    return files


def candidates(prefix: str) -> list[str]:
    """Real investigation ids whose acronym or full name appears in the prefix name."""
    inv = yaml.safe_load((CONFIG / "investigations.yaml").read_text(encoding="utf-8"))["investigations"]
    name = re.sub(r"[_\-/]+", " ", prefix).lower()
    out = []
    for i in inv:
        acr = i["id"].lower().replace("-", " ")
        if re.search(rf"(?<![a-z0-9]){re.escape(acr)}(?![a-z0-9])", name) or i["name"].lower() in name:
            out.append(i["id"])
    return out


def discover(get=_http_get) -> dict:
    top, _ = list_level("", get)
    rows = []
    for p in top:
        subs, files = list_level(p, get)
        for q in [p] + subs:
            cand = candidates(q)
            rows.append({"prefix": q, "candidate_investigation": ";".join(cand),
                         "candidate_slug": ";".join(dict.fromkeys(MEMBER_TO_GROUP.get(c, "") for c in cand if MEMBER_TO_GROUP.get(c))),
                         "sample_files": " | ".join(f["key"].split("/")[-1] for f in files[:3]) if q == p else "",
                         "confirmed": "", "note": "" if cand else "no combustion investigation named in this prefix"})
    with open(MAP, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()) if rows else ["prefix"])
        w.writeheader()
        w.writerows(rows)
    matched = [r for r in rows if r["candidate_investigation"]]
    print(f"psi --discover: {len(rows)} prefixes, {len(matched)} with a candidate investigation → {MAP}. "
          "Set confirmed=yes on the rows a person has checked, then run `psi --fetch`.")
    return {"prefixes": len(rows), "candidates": len(matched)}


def confirmed() -> list[dict]:
    if not MAP.exists():
        return []
    with open(MAP, encoding="utf-8") as f:
        return [r for r in csv.DictReader(f) if r.get("confirmed", "").strip().lower() in ("yes", "y", "true", "1") and r.get("candidate_slug")]


def fetch(get=_http_get) -> dict:
    rows = confirmed()
    snap = {"retrieved_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "bucket": BUCKET, "region": REGION,
            "prefixes": [{"prefix": r["prefix"], "slug": r["candidate_slug"].split(";")[0],
                          "investigation": r["candidate_investigation"].split(";")[0], "files": list_all(r["prefix"], get)} for r in rows]}
    SNAPSHOT.parent.mkdir(parents=True, exist_ok=True)
    SNAPSHOT.write_text(json.dumps(snap, indent=1) + "\n", encoding="utf-8")
    n = sum(len(p["files"]) for p in snap["prefixes"])
    print(f"psi --fetch: {len(rows)} confirmed prefixes, {n} files → {SNAPSHOT}")
    return {"prefixes": len(rows), "files": n}


def resources_from(snap: dict) -> pd.DataFrame:
    rows = []
    for p in snap.get("prefixes", []):
        for f in p["files"]:
            ext = f["key"].rsplit(".", 1)[-1].lower() if "." in f["key"] else ""
            kind = KIND.get(ext)
            if not kind:
                continue
            P, R, T = CRED[kind]
            rows.append({"id": "s3-" + re.sub(r"[^A-Za-z0-9]+", "-", f["key"]).strip("-")[:120], "investigation": p["slug"],
                         "investigations": json.dumps([p["slug"]]), "investigation_detail": p["investigation"], "type": kind,
                         "title": f["key"].split("/")[-1], "publisher": "NASA PSI", "year": None, "format": ext.upper(),
                         "url": ENDPOINT + f["key"].replace(" ", "%20"), "s3_key": f["key"], "doi": None, "psi_id": None,
                         "description": f"File in the public PSI bucket s3://{BUCKET}/{f['key']} ({f['size'] / 1e6:.1f} MB).",
                         "cred_publisher": P, "cred_review": R, "cred_trace": T, "status": "published", "envs_override": None,
                         "origin": "psi_s3", "dataset": None, "doc_id": None})
    return pd.DataFrame(rows)


def run() -> dict:
    res = read("atlas_resources")
    res = res[res.origin != "psi_s3"]
    snap = json.loads(SNAPSHOT.read_text(encoding="utf-8")) if SNAPSHOT.exists() else {}
    new = resources_from(snap)
    write({"atlas_resources": pd.concat([res, new], ignore_index=True) if not new.empty else res})
    print(f"psi: {len(new)} bucket files registered" + ("" if SNAPSHOT.exists() else " (no snapshot: run `psi --discover`, confirm, then `psi --fetch`)"))
    return {"resources": len(new)}
