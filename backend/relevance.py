"""Rank the investigations for one place people live or will live.

The challenge asks for exactly this: which investigations matter most for a station, a spacecraft,
a Moon or Mars base, a rover. The score is a sum of four parts, each 0-3, and every part carries
its reason in words and its source, so the ranking can be checked line by line. Nothing is
learned or hidden: the rules are in config/places.yaml and in this file.

  burns     how directly the thing it burns bears on a cabin fire (from the challenge text)
  air       how many loaded tests sit inside this place's oxygen and pressure range
  gravity   whether the tests were run at this place's gravity (nothing in PSI is partial gravity)
  evidence  whether real test rows are loaded here, demo rows, or only the catalogue entry
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import yaml

from .core import config
from .core.store import get_store
from .explore import explore
from .record import gravity_label

PSI = 6.894757
PARTS = [("burns", "What it burns"), ("air", "Air match"), ("gravity", "Gravity"), ("evidence", "Data in hand")]
GOAL = {"prevention": "preventing fire", "detection": "detecting fire", "suppression": "putting fire out"}


@lru_cache(maxsize=1)
def _cfg() -> dict:
    return yaml.safe_load((Path(__file__).resolve().parents[1] / "config" / "places.yaml").read_text(encoding="utf-8"))


def _src(sid: str | None) -> dict | None:
    return {"id": sid, **_cfg()["sources"][sid]} if sid else None


def _box(place: dict) -> dict | None:
    return next((t for t in config.presets()["targets"] if t["id"] == place["target"]), None) if place.get("target") else None


def _score(inv: dict, place: dict, tests) -> dict:
    c = _cfg()
    iid, g = inv["label"], place["gravity_g"]
    partial, earth = 0.02 < g < 0.95, g >= 0.95
    parts = {}

    fr = c["fuel_overrides"].get(iid) or c["fuel_relevance"].get(inv["fuel_phase"], {"score": 1, "why": "Relevance not stated", "source": None})
    parts["burns"] = {"score": fr["score"], "why": fr["why"] + ".", "source": _src(fr.get("source"))}

    mine = tests[tests.investigation_id == iid]
    box, ids = _box(place), []
    if earth:
        parts["air"] = {"score": 0, "unknown": True, "why": "Run in microgravity to remove buoyancy; the air is not the point of comparison on Earth."}
    elif len(mine) and box:
        o2r = f"{box['o2_frac'][0] * 100:.0f}–{box['o2_frac'][1] * 100:.0f}% oxygen"
        both = mine[mine.o2_frac.notna() & mine.pressure_kpa.notna()]
        o2_only = mine[mine.o2_frac.notna() & mine.pressure_kpa.isna()]
        if len(both):
            near = both[both.o2_frac.between(*box["o2_frac"]) & both.pressure_kpa.between(*box["pressure_kpa"])]
            ids, n = near.test_id.tolist(), len(near)
            parts["air"] = {"score": 3 if n >= 10 else 2 if n >= 3 else 1 if n else 0,
                            "why": f"{n} of its {len(both)} tests with a recorded oxygen level and pressure were run in this place's air"
                                   f" ({o2r}, {box['pressure_kpa'][0] / PSI:.1f}–{box['pressure_kpa'][1] / PSI:.1f} psi)."}
        elif len(o2_only):
            near = o2_only[o2_only.o2_frac.between(*box["o2_frac"])]
            ids, n = near.test_id.tolist(), len(near)
            # a match on oxygen alone is weaker evidence than a match on the whole atmosphere: capped at 2
            parts["air"] = {"score": 2 if n >= 3 else 1 if n else 0, "o2_only": True,
                            "why": f"{n} of its {len(o2_only)} tests with a recorded oxygen level were run at this place's oxygen level ({o2r}). "
                                   "Its table does not record pressure, so this is a match on oxygen only."}
        else:
            parts["air"] = {"score": 0, "unknown": True,
                            "why": "Its table is loaded but records neither the oxygen level nor the pressure of each test, so it cannot be placed in this air."}
    elif iid in c["documented_air"]:
        d = c["documented_air"][iid]
        ok = d["o2_max"] >= place["air"]["o2_frac"]
        parts["air"] = {"score": 2 if ok else 1, "why": d["why"] + ("; its test table is not loaded here." if ok else "."), "source": _src(d["source"])}
    else:
        parts["air"] = {"score": 0, "unknown": True, "why": "Its test table is not loaded here, so its oxygen and pressure range is not known to this atlas."}

    if partial or earth:
        note = c["gravity_notes"].get(iid)
        parts["gravity"] = {"score": 1 + (note["bonus"] if note and partial else 0),
                            "why": (note["why"] + "." if note and partial else
                                    f"Run in microgravity. That bounds what happens at {gravity_label(g).split(' (')[0]} from one side; it is not a test of it."),
                            "source": _src(note["source"] if note and partial else "challenge")}
    else:
        parts["gravity"] = {"score": 3, "why": "Run in microgravity, the gravity of this place."}

    real = int((~mine.demo.astype(bool)).sum()) if len(mine) else 0
    if real:
        parts["evidence"] = {"score": 3, "why": f"{real} real NASA test rows are loaded and can be opened."}
    elif len(mine):
        parts["evidence"] = {"score": 1, "demo": True, "why": f"{len(mine)} rows are loaded, but they are demo data standing in for the real table."}
    else:
        parts["evidence"] = {"score": 0, "why": "Catalogue entry only; no test rows are loaded."}

    return {"id": inv["id"], "label": iid, "name": inv["name"], "pillars": inv["pillars"], "burns": inv["burns"],
            "objectives": inv["objectives"], "parts": parts, "score": sum(p["score"] for p in parts.values()),
            "n_tests": int(len(mine)), "near_ids": ids}


@lru_cache(maxsize=16)
def rank(pid: str) -> dict | None:
    c = _cfg()
    place = next((p for p in c["places"] if p["id"] == pid), None)
    if not place:
        return None
    tests = get_store().usable_tests()
    rows = [_score(i, place, tests) for i in explore()["investigations"]]
    rows.sort(key=lambda r: (-r["score"], -r["parts"]["burns"]["score"], -r["n_tests"], r["label"]))
    for n, r in enumerate(rows, 1):
        r["rank"] = n
    best = {k: next((r["label"] for r in rows if k in r["pillars"]), None) for k in GOAL}

    g = place["gravity_g"]
    partial, earth = 0.02 < g < 0.95, g >= 0.95
    box = _box(place)
    inside = tests[tests.o2_frac.between(*box["o2_frac"]) & tests.pressure_kpa.between(*box["pressure_kpa"])] if box else tests.iloc[0:0]
    real_inside = inside[~inside.demo.astype(bool)]
    n_g = int((tests.gravity_g - g).abs().lt(0.02).sum())
    gname = gravity_label(g).split(" (")[0]

    top = rows[0]
    if earth:
        reading = (f"Every investigation here ran in microgravity, which removes buoyancy so the chemistry and the airflow can be seen alone. "
                   f"{top['label']} ranks first for fire safety on Earth, and the hardware built around these experiments has already come home.")
    else:
        name = place["label"].replace(" today", "")
        reading = f"For {'the ' if name[0].isupper() and name != 'Mars base' and name != 'Crew spacecraft' else 'a '}{name if name[:3] in ('ISS', 'Moo') else name.lower() if name != 'Mars base' else name}, {top['label']} ranks first."
        if top["parts"]["air"]["score"] >= 1 and not top["parts"]["air"].get("unknown"):
            reading += " " + top["parts"]["air"]["why"]
        if partial:
            reading += f" No investigation has ever burned anything at {gname}, so every result here is a bound, not a test."

    gaps = []
    if partial:
        gaps.append({"text": f"{gravity_label(g)}: {n_g} tests in the loaded data, and no partial-gravity combustion data in PSI at all.", "source": _src("challenge")})
        gaps.append({"text": "Expected to fill it: " + "; ".join(f"{p['id']} ({p['name']})" for p in c["planned"]) + ".", "source": _src("combustion")})
    if box:
        n_demo = len(inside) - len(real_inside)
        gaps.append({"text": ((f"{len(real_inside)} real and {n_demo} demo tests sit" if n_demo else f"{len(real_inside)} real tests sit")
                              + " inside this place's oxygen and pressure range." if len(inside)
                              else "No loaded test sits inside this place's oxygen and pressure range."),
                     "citation": {"kind": "aggregate", "op": "count", "field": "burned", "rows": inside.test_id.tolist()} if len(inside) else None})
    if box:
        no_p = int(tests.pressure_kpa.isna().sum())
        if no_p:
            gaps.append({"text": f"{no_p} of the {len(tests)} loaded tests do not record cabin pressure, so they cannot be placed in this range. "
                                 "Most are solid-material tests (BASS, BASS-II, Saffire)."})
    not_loaded = [r["label"] for r in rows if r["n_tests"] == 0 and r["parts"]["burns"]["score"] == 3]
    if not_loaded:
        gaps.append({"text": "Directly relevant but not loaded here: " + ", ".join(not_loaded) + ". Their ranks rest on the catalogue description alone."})

    air = place["air"]
    return {"id": pid, "label": place["label"], "preset": place["preset"],
            "air": {"text": f"{air['o2_frac'] * 100:.0f}% oxygen at {air['pressure_kpa'] / PSI:.1f} psi", "assumed": bool(air.get("assumed")),
                    "note": place.get("air_note"), "source": _src(place.get("air_source"))},
            "gravity": gravity_label(g), "gravity_tested": n_g > 0 and not partial,
            "flame": place["flame"], "reading": reading, "best": [{"goal": GOAL[k], "label": v} for k, v in best.items() if v],
            "parts": [{"key": k, "label": lab} for k, lab in PARTS], "max": 3 * len(PARTS), "rows": rows, "gaps": gaps,
            "history": [{**h, "source": _src(h["source"])} for h in place.get("history", [])],
            "spinoffs": [{**s, "source": _src(s["source"])} for s in place.get("spinoffs", [])],
            "demo": bool(tests.demo.any())}


def places() -> list[dict]:
    return [{"id": p["id"], "label": p["label"]} for p in _cfg()["places"]]
