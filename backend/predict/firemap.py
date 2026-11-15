"""The fire map (/engine/map): every NASA test with a recorded ending, placed by its conditions, and where new tests are
needed. One answer for the whole page (no settings), cached.

Axes: oxygen (%), pressure (psi) and fuel (one lane per fuel, gas jets then liquid drops). These are the tests the fire
check learns from (CFI-G gas jets, FLEX droplets): the rows with oxygen, pressure and an outcome. The NASA tables give no
airflow for them, so airflow is not an axis.

Future studies, two kinds:
  next      per fuel, the two tests the models would learn most from (explore.next_tests: query by committee, inside
            what the hardware has done, far from this fuel's tests).
  crew      the air crews will breathe (presets): ISS cabin for reference, and the Moon and Mars base air. No NASA fire
            test has run at Moon or Mars gravity; for each fuel the map says whether that air is even inside what NASA
            tested in microgravity (the fire check's zone rule).
"""
from __future__ import annotations

from functools import lru_cache

import numpy as np

from . import explore, service
from .problems import PROBLEMS, features_from

SIZE = {"gas": "fuel_flow", "droplet": "d0_mm"}
KIND = {"gas": "Gas jet", "droplet": "Liquid drop"}


def _crew() -> list[dict]:
    from ..catalog.query import catalog
    by = catalog().preset_by_key
    out = []
    for k, label in (("iss", "ISS cabin air"), ("moon", "Moon & Mars base air")):
        if k in by:
            p = by[k]
            out.append({"key": k, "label": label, "o2": float(p["o2"]), "psi": float(p["psi"]), "note": p.get("note"),
                        "needed": k != "iss"})
    return out


@lru_cache(maxsize=1)
def build() -> dict:
    lanes, tests, nxt = [], [], []
    crew = _crew()
    crew_zone: dict[str, dict[str, str]] = {c["key"]: {} for c in crew}
    for key, pb in PROBLEMS.items():
        b, dom = service._bundle(key), service._domain(key)
        df = pb.frame()
        size = SIZE[key]
        for fuel in sorted(df.fuel.unique(), key=lambda f: (-int((df.fuel == f).sum()), f)):
            sub = df[df.fuel == fuel]
            lane = len(lanes)
            lanes.append({"lane": lane, "problem": key, "fuel": fuel, "kind": KIND[key], "investigation": pb.investigation,
                          "psi_id": pb.psi_id, "outcome_yes": pb.outcome_yes, "outcome_no": pb.outcome_no,
                          "n": int(len(sub)), "lit": int(sub[pb.target].sum())})
            for t in sub.itertuples():
                row = {"id": t.test_id, "lane": lane, "o2": round(float(t.o2_pct), 2), "psi": round(float(t.psi), 2),
                       "lit": int(getattr(t, pb.target)), "campaign": str(t.campaign), "size": round(float(getattr(t, size)), 2)}
                if key == "droplet":
                    row["co2"], row["he"] = round(float(t.co2_pct), 1), round(float(t.he_pct), 1)
                tests.append(row)
            held = {"fuel_flow": float(sub.fuel_flow.median())} if key == "gas" else {"d0_mm": float(sub.d0_mm.median()), "co2_pct": 0.0, "he_pct": 0.0}
            mid = features_from(pb, {"problem": key, "fuel": fuel, "o2_pct": float(sub.o2_pct.median()), "psi": float(sub.psi.median()), **held})[0]
            if b["card"]["chosen"] and b.get("boot_models"):
                for s in explore.next_tests(pb, b, dom, mid, k=2):
                    nxt.append({"lane": lane, "o2": s["inputs"]["o2_pct"], "psi": s["inputs"]["psi"], "size": s["inputs"].get(size),
                                "low": s["committee_low"], "high": s["committee_high"], "nearest": s["nearest_test"], "why": s["why"]})
            for c in crew:
                x = features_from(pb, {"problem": key, "fuel": fuel, "o2_pct": c["o2"], "psi": c["psi"], **held})[0]
                crew_zone[c["key"]][str(lane)] = dom.assess(x, 0.0)["zone"]
    for c in crew:
        c["zone_by_lane"] = crew_zone[c["key"]]
    return {"lanes": lanes, "tests": tests, "next": nxt, "crew": crew,
            "size_label": {"gas": "leak", "droplet": "drop"}, "size_unit": {"gas": "mg/s", "droplet": "mm"},
            "o2_range": [float(np.floor(min(t["o2"] for t in tests))), float(np.ceil(max(t["o2"] for t in tests)))],
            "psi_range": [0.0, float(np.ceil(max(t["psi"] for t in tests)))]}
