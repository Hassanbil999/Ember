"""`ingest seed`: load data/seed.json only where no real row exists. Idempotent.

Matching (SPEC §6.1): investigations by slug, resources by URL or title, test points by code. A seed row
never overwrites a real row; it keeps its `status` and `verified` exactly as given. Two gap-filling rules:
- For an investigation that exists in the real data, the seed adds only tags the real catalog has no
  notion of (`basics`, relevance environments such as "Moon or Mars") and fuels when the real catalog
  names none (smoke, dust).
- A seed *placeholder data* resource stands in for "the PSI test matrix"; it is skipped when a real PSI
  data resource exists for its investigation (Decision J).
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pandas as pd

from ..core.config import DATA
from .build import read, write

SEED = DATA / "seed.json"
SEED_NOTE = "Starter row from data/seed.json: not yet checked against its source."


def load_seed(path: Path = SEED) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _real(df: pd.DataFrame) -> pd.DataFrame:
    return df[df.origin != "seed"].copy() if not df.empty and "origin" in df else df


def _union(a: list, b: list) -> list:
    return list(dict.fromkeys(list(a or []) + list(b or [])))


def run() -> dict:
    seed = load_seed()
    inv = _real(read("atlas_investigations"))
    res = _real(read("atlas_resources"))
    pts = _real(read("atlas_test_points"))
    links = read("atlas_resource_points")
    if not links.empty:
        links = links[links.resource_id.isin(res.id)]
    if inv.empty:
        raise SystemExit("No real tables yet: run `python -m backend.ingest existing` first.")
    added = {"investigations": 0, "investigations_filled": 0, "resources": 0, "resources_skipped": [], "test_points": 0}

    # investigations
    inv = inv.set_index("slug", drop=False)
    new_inv = []
    for s in seed["investigations"]:
        if s["slug"] in inv.index:
            r = inv.loc[s["slug"]]
            purposes = _union(json.loads(r.purposes), s.get("purposes"))
            envs = _union(json.loads(r.envs), s.get("envs"))
            fuels = json.loads(r.fuels) or list(s.get("fuels") or [])
            if (purposes, envs, fuels) != (json.loads(r.purposes), json.loads(r.envs), json.loads(r.fuels)):
                added["investigations_filled"] += 1
            inv.loc[s["slug"], ["purposes", "envs", "fuels"]] = [json.dumps(purposes), json.dumps(envs), json.dumps(fuels)]
            continue
        new_inv.append({"slug": s["slug"], "name": s["name"], "full_name": s.get("full_name") or s["name"],
                        "purposes": json.dumps(s.get("purposes") or []), "fuels": json.dumps(s.get("fuels") or []),
                        "envs": json.dumps(s.get("envs") or []), "hardware": s.get("hardware"), "summary": s.get("summary"),
                        "psi_url": None, "members": "[]", "origin": "seed"})
    added["investigations"] = len(new_inv)
    inv = pd.concat([inv.reset_index(drop=True), pd.DataFrame(new_inv)], ignore_index=True)

    # resources
    real_urls = {u for u in res.url.dropna()}
    ntrs_id = re.compile(r"ntrs\.nasa\.gov/(?:api/)?citations/(\d+)")
    real_ntrs = {m.group(1) for u in real_urls for m in [ntrs_id.search(u)] if m}
    real_titles = {t.strip().lower() for t in res.title.dropna()}
    real_data_invs = set(res.loc[res.type == "data", "investigation"].dropna())
    for s in seed["resources"]:
        if s.get("investigation") in real_data_invs and s["type"] == "data" and s.get("status") == "placeholder":
            added["resources_skipped"].append(s["key"])
            continue
        m = ntrs_id.search(s.get("url") or "")
        if (s.get("url") and s["url"] in real_urls) or s["title"].strip().lower() in real_titles or (m and m.group(1) in real_ntrs):
            added["resources_skipped"].append(s["key"])
            continue
    seed_res = []
    for s in seed["resources"]:
        if s["key"] in added["resources_skipped"]:
            continue
        cred = s.get("cred") or {}
        seed_res.append({
            "id": s["key"], "investigation": s.get("investigation"), "investigations": json.dumps([s.get("investigation")]),
            "investigation_detail": None, "type": s["type"], "title": s["title"], "publisher": s.get("publisher"),
            "year": s.get("year"), "format": s.get("format"), "url": s.get("url"), "s3_key": None, "doi": None, "psi_id": None,
            "description": s.get("description"), "cred_publisher": cred.get("publisher"), "cred_review": cred.get("review"),
            "cred_trace": cred.get("trace"), "status": s.get("status") or ("published" if s.get("url") else "placeholder"),
            "envs_override": json.dumps(s["envs_override"]) if s.get("envs_override") else None,
            "origin": "seed", "dataset": None, "doc_id": None,
        })
    added["resources"] = len(seed_res)
    res = pd.concat([res, pd.DataFrame(seed_res)], ignore_index=True)

    # test points
    real_codes = set(pts.code)
    loaded_res = set(res.id)
    seed_pts = []
    for s in seed["test_points"]:
        if s["code"] in real_codes:
            continue
        src = s.get("source_resource")
        seed_pts.append({
            "code": s["code"], "investigation": s.get("investigation"), "investigation_detail": None,
            "source_resource_id": src if src in loaded_res else None, "material": s.get("material"),
            "sample_desc": s.get("sample_desc"), "geometry": None, "gravity_g": s.get("gravity_g"),
            "o2_pct": s.get("o2_pct"), "pressure_kpa": s.get("pressure_kpa"), "flow_cm_s": s.get("flow_cm_s"),
            "flow_direction": s.get("flow_direction"), "diluent": s.get("diluent"), "outcome": s.get("outcome"),
            "spread_mm_s": s.get("spread_mm_s"), "notes": s.get("notes"), "source_file": None, "source_page": None,
            "source_quote": None, "extraction": s.get("extraction") or "manual", "verified": bool(s.get("verified")),
            "verified_by": None, "verified_at": None, "unverified_reason": None if s.get("verified") else SEED_NOTE,
            "origin": "seed", "dataset": None, "extra": "{}",
        })
    added["test_points"] = len(seed_pts)
    pts = pd.concat([pts, pd.DataFrame(seed_pts)], ignore_index=True)
    codes = set(pts.code)
    seed_links = [{"resource_id": s["key"], "code": c} for s in seed["resources"] if s["key"] in loaded_res
                  for c in (s.get("points") or []) if c in codes]
    links = pd.concat([links, pd.DataFrame(seed_links, columns=["resource_id", "code"])], ignore_index=True).drop_duplicates()

    presets = pd.DataFrame([{"key": p["key"], "label": p["label"], "g": p["g"], "o2": p["o2"], "psi": p["psi"],
                             "u": p["u"], "env": p["env"], "note": p.get("note")} for p in seed["presets"]])
    params = pd.DataFrame([{"material": m, **v, "n_points": 0, "rmse": None, "fitted_at": None,
                            "source": "defaults (SPEC §8.1)"} for m, v in seed["model_defaults"].items()])
    existing_params = read("atlas_model_params")
    if not existing_params.empty and (existing_params.source != "defaults (SPEC §8.1)").any():
        params = existing_params          # a fit already ran; `ingest fit` owns these rows
    write({"atlas_investigations": inv, "atlas_resources": res, "atlas_test_points": pts,
           "atlas_resource_points": links, "atlas_presets": presets, "atlas_model_params": params})
    print("seed:", {**added, "resources_skipped": ", ".join(added["resources_skipped"])})
    return added
