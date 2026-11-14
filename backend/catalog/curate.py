"""`ingest curate`: the human review layer (SPEC §6 admin verify page).

Two tracked files, so a reviewer's work survives a rebuild and reaches the deploy through git:
  data/curation/ai_extracted.json   test points proposed by `ingest extract` (extraction=ai, verified=false)
  data/curation/verifications.json  decisions made on /admin/verify: verify | edit | reject, with who and when

Rules: an AI-extracted point is added only if its code is new (it never overwrites a real or seed row).
A NASA PSI row can only be verified: its values come from the published table and are never edited or removed.
Seed and AI rows can be edited (which clears `verified` until someone verifies the new values) or rejected.
Applying the decisions is idempotent, so the step can run any number of times.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from ..core.config import DATA
from .build import read, write

CURATION = DATA / "curation"
AI_FILE = CURATION / "ai_extracted.json"
DECISIONS = CURATION / "verifications.json"
EDITABLE = ["material", "sample_desc", "gravity_g", "o2_pct", "pressure_kpa", "flow_cm_s", "flow_direction", "diluent",
            "outcome", "spread_mm_s", "notes"]
NUMERIC = {"gravity_g": (0, 1.2), "o2_pct": (0, 100), "pressure_kpa": (0, 200), "flow_cm_s": (0, 100), "spread_mm_s": (0, 1000)}
OUTCOMES = {"burned", "went_out", "cool_flame", "flame", "measured"}
MATERIALS = {"fabric", "pmma", "droplet", "gas", "other"}


class CurationError(ValueError):
    pass


def _load(path: Path) -> list:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else []


def decisions() -> list[dict]:
    return _load(DECISIONS)


def validate_fields(fields: dict) -> dict:
    out = {}
    for k, v in fields.items():
        if k not in EDITABLE:
            raise CurationError(f"{k} cannot be edited")
        if k in NUMERIC and v is not None:
            v = float(v)
            lo, hi = NUMERIC[k]
            if not lo <= v <= hi:
                raise CurationError(f"{k} must be between {lo} and {hi}")
        if k == "outcome" and v not in OUTCOMES:
            raise CurationError(f"outcome must be one of {sorted(OUTCOMES)}")
        if k == "material" and v not in MATERIALS:
            raise CurationError(f"material must be one of {sorted(MATERIALS)}")
        out[k] = v
    return out


def record(code: str, action: str, by: str, fields: dict | None = None, note: str | None = None) -> dict:
    """Validate one reviewer decision against the current table and append it to verifications.json."""
    pts = read("atlas_test_points").set_index("code")
    if code not in pts.index:
        raise CurationError(f"No test point {code}")
    origin = pts.loc[code, "origin"]
    if action not in ("verify", "edit", "reject"):
        raise CurationError("action must be verify, edit or reject")
    if origin == "psi" and action != "verify":
        raise CurationError("NASA PSI rows are published values: they can be verified, not edited or rejected")
    d = {"code": code, "action": action, "by": by.strip() or "reviewer", "at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")}
    if action == "edit":
        d["fields"] = validate_fields(fields or {})
        if not d["fields"]:
            raise CurationError("No fields to edit")
    if note:
        d["note"] = note[:500]
    CURATION.mkdir(parents=True, exist_ok=True)
    DECISIONS.write_text(json.dumps(decisions() + [d], indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return d


def run() -> dict:
    pts = read("atlas_test_points")
    links = read("atlas_resource_points")
    res = read("atlas_resources")
    if pts.empty:
        raise SystemExit("No test points yet: run `existing` and `seed` first.")
    pts = pts[pts.origin != "ai"]                                  # rebuilt from the file below every run
    links = links[links.code.isin(pts.code)]
    added = 0
    ai_rows = []
    for p in _load(AI_FILE):
        if p["code"] in set(pts.code):
            continue
        if p.get("source_resource_id") not in set(res.id):
            continue
        ai_rows.append({**{c: None for c in pts.columns}, **p, "origin": "ai", "extraction": "ai", "verified": False,
                        "unverified_reason": "Extracted by AI: not yet checked against the source quote.", "extra": "{}"})
        added += 1
    if ai_rows:
        new = pd.DataFrame(ai_rows)[pts.columns]
        pts = pd.concat([pts, new], ignore_index=True)
        links = pd.concat([links, pd.DataFrame({"resource_id": new.source_resource_id, "code": new.code})], ignore_index=True)
    pts = pts.set_index("code", drop=False)
    applied = {"verify": 0, "edit": 0, "reject": 0}
    for d in decisions():
        code = d["code"]
        if code not in pts.index:
            continue
        if d["action"] == "reject" and pts.loc[code, "origin"] != "psi":
            pts = pts.drop(index=code)
            links = links[links.code != code]
        elif d["action"] == "edit" and pts.loc[code, "origin"] != "psi":
            for k, v in d.get("fields", {}).items():
                pts.loc[code, k] = v
            pts.loc[code, ["verified", "verified_by", "verified_at"]] = [False, None, None]
            pts.loc[code, "unverified_reason"] = f"Edited by {d['by']} on {d['at'][:10]}: needs verification."
        elif d["action"] == "verify":
            pts.loc[code, ["verified", "verified_by", "verified_at", "unverified_reason"]] = [True, d["by"], d["at"], None]
        else:
            continue
        applied[d["action"]] += 1
    pts = pts.reset_index(drop=True)
    pts["verified"] = pts["verified"].astype(bool)
    write({"atlas_test_points": pts, "atlas_resource_points": links.drop_duplicates()})
    summary = {"ai_points_added": added, **applied}
    print("curate:", summary)
    return summary
