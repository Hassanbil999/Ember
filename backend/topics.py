"""Answer screens for the four starting points on the home page.

Each topic returns the same shape: one finding sentence, an evidence grade, one visual, and
three columns that are never mixed: what was measured, what the model infers, what was never tested.
Every number carries a citation to the rows or the page it came from.
"""
from __future__ import annotations

from functools import lru_cache

import pandas as pd

from .api import views
from .core import config
from .core.store import get_store
from .models import surrogate
from .record import gravity_label

PSI = 6.894757
TOPICS = {
    "moon-base": {"title": "Moon base fire risk", "preset": "moon_base", "target": "moon_base",
                  "question": "Would a fire keep burning in a Moon base?",
                  "terms": "Moon base exploration atmosphere oxygen pressure"},
    "iss-cabin": {"title": "ISS cabin", "preset": "iss", "target": "iss",
                  "question": "How do materials burn in the air astronauts breathe on the ISS today?",
                  "terms": "ISS cabin air ventilation flow flame spread"},
    "microgravity": {"title": "How fire behaves in microgravity", "question": "What changes when a flame has no up?",
                     "terms": "microgravity buoyancy flow flame spherical"},
    "untested": {"title": "What NASA hasn't tested yet", "question": "Where does the data stop?",
                 "terms": "partial gravity lunar untested exploration atmosphere"},
}


def _rows(ids, field="burned", op="count"):
    return {"kind": "aggregate", "op": op, "field": field, "rows": list(ids)}


def _solids() -> pd.DataFrame:
    return get_store().usable_tests("bass2_demo")


def _in_box(t: pd.DataFrame, box: dict) -> pd.DataFrame:
    return t[t.o2_frac.between(*box["o2_frac"]) & t.pressure_kpa.between(*box["pressure_kpa"])]


def _passages(terms: str, k: int = 2) -> list[dict]:
    return views.passages_for(terms, k=k)


def _air(p: dict) -> str:
    return f"{p['o2_frac'] * 100:.0f}% oxygen at {p['pressure_kpa'] / PSI:.1f} psi"


def _verdict(p: float, status: str) -> tuple[str, str]:
    """(short verdict, tone) from the model probability and whether it is inside the tested range."""
    if status == "outside":
        return "No basis to predict", "nodata"
    if p >= 0.65:
        return "Likely keeps burning", "flame"
    if p <= 0.35:
        return "Likely goes out", "ext"
    return "Too close to call", "unc"


def _material_rows(preset: dict, box: dict) -> list[dict]:
    t = _solids()
    out = []
    for m in sorted(t.material.dropna().unique()):
        tm = t[t.material == m]
        ug = tm[tm.gravity_g < 0.02]
        near = _in_box(ug, box)
        sc = {"o2_frac": preset["o2_frac"], "pressure_kpa": preset["pressure_kpa"], "flow_cm_s": preset["flow_cm_s"],
              "gravity_g": preset["gravity_g"], "material": m, "thickness_mm": float(tm.thickness_mm.median())}
        pr = surrogate.predict("solid_burn", sc, with_sensitivity=False)
        verdict, tone = _verdict(pr["p"], pr["domain"]["status"])
        if pr["domain"]["status"] != "inside":          # a confident number outside the tested range is still a guess
            pr["confidence"] = "low"
        out.append({"material": m, "n_tests": int(len(ug)), "n_near": int(len(near)),
                    "n_near_burned": int(near.burned.fillna(0).sum()), "near_ids": near.test_id.tolist(),
                    "p": round(pr["p"], 3), "confidence": pr["confidence"], "status": pr["domain"]["status"],
                    "bracket": pr.get("bracket"), "verdict": verdict, "tone": tone,
                    "nearest": pr["nearest"][0] if pr["nearest"] else None,
                    "lab": f"/lab?preset={preset['id']}&item={m}"})
    return out


def _environment(tid: str, material: str | None) -> dict:
    spec = TOPICS[tid]
    preset = next(p for p in config.presets()["presets"] if p["id"] == spec["preset"])
    box = next(t for t in config.presets()["targets"] if t["id"] == spec["target"])
    t = _solids()
    ug = t[t.gravity_g < 0.02]
    mats = _material_rows(preset, box)
    sel = next((m for m in mats if m["material"] == material), None)
    partial = 0.02 < preset["gravity_g"] < 0.95
    n_partial = int(get_store().usable_tests().gravity_g.between(0.02, 0.95).sum())
    place = spec["title"].replace(" fire risk", "")
    scope = [sel] if sel else mats
    near_ids = [i for m in scope for i in m["near_ids"]]
    n_near, n_burn = len(near_ids), sum(m["n_near_burned"] for m in scope)
    likely = [m for m in mats if m["tone"] == "flame"]

    if sel:
        finding = (f"{sel['material']} in {place} air ({_air(preset)}): the model says "
                   f"“{sel['verdict'].lower()}” ({sel['p'] * 100:.0f}% chance of sustained burning).")
        if sel["n_near"]:
            finding += f" {sel['n_near_burned']} of {sel['n_near']} microgravity tests in this air range kept burning."
        else:
            finding += " No test of this material was run inside this air range."
    else:
        close = [m for m in mats if m["tone"] == "unc"]
        parts = ([f"{len(likely)} of {len(mats)} tested materials are predicted to keep burning"] if likely else [])
        if close:
            parts.append(f"{'all ' if len(close) == len(mats) else ''}{len(close)} of the {len(mats)} tested materials "
                         f"{'is' if len(close) == 1 else 'are'} too close to call" if not likely else
                         f"{len(close)} {'is' if len(close) == 1 else 'are'} too close to call")
        if not parts:
            parts = [f"none of the {len(mats)} tested materials is predicted to keep burning"]
        finding = f"In {place} air ({_air(preset)}), " + " and ".join(parts) + "."
    if partial:
        finding += f" Nothing has ever been burned at {gravity_label(preset['gravity_g']).split(' (')[0]}."

    if partial:
        grade = {"label": "Model estimate", "tone": "unc",
                 "why": "Predictions rest on microgravity and Earth-gravity tests. Partial gravity has no data, so they can only bracket the answer."}
    elif n_near >= 5:
        grade = {"label": "Measured", "tone": "text", "why": f"{n_near} real tests sit inside this air range."}
    elif n_near:
        grade = {"label": "Close conditions", "tone": "warn", "why": f"Only {n_near} real tests sit inside this air range; the rest is model."}
    else:
        grade = {"label": "Model estimate", "tone": "unc", "why": "No real test sits inside this air range."}

    measured = {"summary": (f"{n_burn} of {n_near} microgravity tests inside this air range kept burning."
                            if n_near else "No microgravity test falls inside this air range."),
                "citation": _rows(near_ids) if n_near else None,
                "items": [{"text": f"{m['material']}: {m['n_near_burned']} of {m['n_near']} burned" if m["n_near"]
                           else f"{m['material']}: not tested in this range",
                           "citation": _rows(m["near_ids"]) if m["n_near"] else None} for m in scope]}
    inferred = {"summary": "A model trained only on the loaded tests estimates the chance that a flame keeps spreading.",
                "items": [{"text": f"{m['material']}: {m['verdict'].lower()} ({m['p'] * 100:.0f}%, confidence {m['confidence']})"
                           + (f"; between {min(m['bracket'].values()) * 100:.0f}% and {max(m['bracket'].values()) * 100:.0f}% "
                              "if gravity behaves like microgravity or like Earth" if m.get("bracket") else ""),
                           "tone": m["tone"]} for m in scope]}
    untested_items = []
    if partial:
        untested_items.append({"text": f"{gravity_label(preset['gravity_g'])}: {n_partial} tests. Every prediction here assumes it behaves "
                                       "somewhere between microgravity and Earth gravity."})
    for m in scope:
        if not m["n_near"]:
            untested_items.append({"text": f"{m['material']} has no test inside this oxygen and pressure range."})
    all_m = set(t.material.dropna().unique())
    untested_items.append({"text": f"Only {len(all_m)} materials are in the loaded data. Anything else is unknown."})
    untested = {"summary": "What no experiment in the loaded data covers.", "items": untested_items[:4]}

    pts = ug if not sel else ug[ug.material == sel["material"]]
    visual = {"kind": "envelope", "x": "o2_frac", "y": "pressure_kpa",
              "points": pts[["test_id", "o2_frac", "pressure_kpa", "burned", "material"]].dropna(subset=["o2_frac", "pressure_kpa"]).to_dict("records"),
              "box": {"label": f"{place} air", "o2_frac": box["o2_frac"], "pressure_kpa": box["pressure_kpa"]},
              "marker": {"o2_frac": preset["o2_frac"], "pressure_kpa": preset["pressure_kpa"]},
              "caption": "Each dot is one real microgravity test: amber burned, blue went out. The outlined box is the air this place plans to use."}
    return {"finding": finding, "grade": grade, "visual": visual, "measured": measured, "inferred": inferred,
            "untested": untested, "materials": mats, "material": sel["material"] if sel else None,
            "next": [{"label": "Try other conditions in the simulator", "href": (sel or mats[0])["lab"] if sel else f"/lab?preset={preset['id']}"},
                     {"label": "See which experiments matter most here", "href": f"/places?place={spec['target']}"},
                     {"label": "Open the test table", "href": "/data?dataset=bass2_demo"}]}


def _microgravity() -> dict:
    t = _solids()
    b = t[t.burned == 1]
    ug, g1 = b[b.gravity_g < 0.02], b[b.gravity_g > 0.95]
    fl = t[(t.gravity_g < 0.02) & t.flow_cm_s.notna()]
    still, moving = fl[fl.flow_cm_s < 1], fl[fl.flow_cm_s >= 5]
    finding = ("With no up, hot gas does not rise: a flame becomes a slow, round shell fed only by whatever air drifts past it.")
    items = []
    if len(still) and len(moving):
        finding += (f" In the loaded tests, {still.burned.mean() * 100:.0f}% of samples kept burning in still air "
                    f"against {moving.burned.mean() * 100:.0f}% with airflow of 5 cm/s or more.")
        items.append({"text": f"Still air (under 1 cm/s): {int(still.burned.sum())} of {len(still)} burned", "citation": _rows(still.test_id)})
        items.append({"text": f"Airflow of 5 cm/s or more: {int(moving.burned.sum())} of {len(moving)} burned", "citation": _rows(moving.test_id)})
    if len(ug) and len(g1):
        items.append({"text": f"Lowest oxygen that sustained a flame: {ug.o2_frac.min() * 100:.1f}% in microgravity, "
                              f"{g1.o2_frac.min() * 100:.1f}% at Earth gravity",
                      "citation": _rows(pd.concat([ug.nsmallest(1, 'o2_frac'), g1.nsmallest(1, 'o2_frac')]).test_id, "o2_frac", "min")})
    n_partial = int(get_store().usable_tests().gravity_g.between(0.02, 0.95).sum())
    return {"finding": finding,
            "grade": {"label": "Measured", "tone": "text", "why": f"Based on {len(fl)} microgravity tests with a recorded airflow."} if len(fl)
            else {"label": "Documented", "tone": "text-2", "why": "Report text only."},
            "visual": {"kind": "flames", "caption": "Same fuel, same air. On Earth buoyancy pulls fresh air in from below and stretches the flame upward. "
                                                   "In microgravity nothing moves the air, so the flame sits as a dim sphere and can starve itself."},
            "measured": {"summary": "What the loaded tests show about airflow and gravity.", "items": items},
            "inferred": {"summary": "The simulator uses the same tests to estimate outcomes between the measured points.",
                         "items": [{"text": "Airflow is the strongest lever in microgravity: move the airflow slider and watch the flame respond."}]},
            "untested": {"summary": "What no experiment in the loaded data covers.",
                         "items": [{"text": f"Gravity between microgravity and Earth (Moon, Mars): {n_partial} tests."}]},
            "materials": [], "material": None,
            "next": [{"label": "Change the airflow yourself", "href": "/lab"},
                     {"label": "See the experiments behind this", "href": "/explore"},
                     {"label": "More findings", "href": "/insights"}]}


def coverage() -> list[dict]:
    """How many real tests sit inside each planned environment's air range, and whether its gravity was ever tested."""
    t = get_store().usable_tests()
    out = []
    for box in config.presets()["targets"]:
        inside = _in_box(t, box)
        g = box["gravity_g"]
        g_tests = int((t.gravity_g - g).abs().lt(0.02).sum())
        out.append({"id": box["id"], "label": box["label"], "n": int(len(inside)), "ids": inside.test_id.tolist(),
                    "air": f"{box['o2_frac'][0] * 100:.0f}–{box['o2_frac'][1] * 100:.0f}% O₂, "
                           f"{box['pressure_kpa'][0] / PSI:.1f}–{box['pressure_kpa'][1] / PSI:.1f} psi",
                    "gravity": gravity_label(g), "gravity_tested": g_tests > 0, "gravity_tests": g_tests})
    return out


def _untested() -> dict:
    cov = coverage()
    t = get_store().usable_tests()
    no_grav = [c for c in cov if not c["gravity_tested"]]
    empty = [c for c in cov if c["n"] == 0]
    finding = (f"{len(no_grav)} of {len(cov)} planned environments have never had a single fire test at their gravity"
               + (f", and {len(empty)} {'has' if len(empty) == 1 else 'have'} no test at all inside {'its' if len(empty) == 1 else 'their'} air range."
                  if empty else "."))
    return {"finding": finding,
            "grade": {"label": "Measured", "tone": "text", "why": f"A count over all {len(t)} usable tests in the loaded data."},
            "visual": {"kind": "coverage", "rows": cov,
                       "caption": "Bar length is the number of real tests inside each environment's oxygen and pressure range. "
                                  "The right column says whether its gravity was ever tested."},
            "measured": {"summary": "Tests that fall inside each environment's air range.",
                         "items": [{"text": f"{c['label']}: {c['n']} tests", "citation": _rows(c["ids"]) if c["n"] else None} for c in cov]},
            "inferred": {"summary": "Where data is missing the simulator still answers, and says how far it is reaching.",
                         "items": [{"text": "Predictions outside the tested range are labelled “outside the data” instead of being shown as numbers you can trust."}]},
            "untested": {"summary": "The gaps, stated plainly.",
                         "items": [{"text": f"{c['label']}: no test at {c['gravity']}"} for c in no_grav]},
            "materials": [], "material": None,
            "next": [{"label": "Probe a gap in the simulator", "href": "/lab?preset=moon_base"},
                     {"label": "See which experiments exist", "href": "/explore"},
                     {"label": "Open the test table", "href": "/data"}]}


@lru_cache(maxsize=64)
def topic(tid: str, material: str | None = None) -> dict | None:
    if tid not in TOPICS:
        return None
    spec = TOPICS[tid]
    body = _environment(tid, material) if "preset" in spec else _microgravity() if tid == "microgravity" else _untested()
    return {"id": tid, "title": spec["title"], "question": spec["question"], "demo": bool(get_store().tests["demo"].any()),
            "sources": _passages(spec["terms"]), **body}
