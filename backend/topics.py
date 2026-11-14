"""Answer screens for the four starting points on the home page.

Each topic returns the same shape: one finding sentence, an evidence grade, one visual, and
three columns that are never mixed: what was measured, what the model infers, what was never tested.
Every number carries a citation to the rows or the page it came from.

All evidence is the real NASA PSI data:
  * solid materials (BASS-II, SAFFIRE-1/2/3): oxygen level and, where the table says, how a test ended.
    These tables record no pressure, so solid tests are placed by oxygen only, and no model is trained
    on them (BASS-II has no burned / went-out column).
  * flames with oxygen, pressure and an outcome (FLEX droplets, CFI-G gas flames): placed in the air
    range of each environment, and the basis of the two models.
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
SOLID_DS = ["bass2", "saffire1", "saffire2", "saffire3"]          # solid tests with an oxygen level
FIRE_DS = {"flex": "FLEX droplet", "cfig_normal": "CFI-G gas-flame"}   # tests with oxygen, pressure and an outcome
MODELS = [("cfig_normal", "gas_sustain", "Gas flames (CFI-G)"), ("flex", "droplet_burn", "Fuel droplets (FLEX)")]

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


def _pct(x: float) -> str:
    return f"{x * 100:.1f}".rstrip("0").rstrip(".")


def _solids() -> pd.DataFrame:
    t = get_store().usable_tests()
    return t[t.dataset.isin(SOLID_DS) & t.o2_frac.notna()]


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


def _outcome_words(g: pd.DataFrame) -> str:
    """What the tables say about how these solid tests ended, in words, or ''."""
    parts = []
    known = g[g.burned.notna()]
    if len(known):
        nb = int(known.burned.sum())
        parts.append(f"{nb} of {len(known)} with a recorded outcome burned the whole sample")
    ends = g[g.burned.isna()].test_end.dropna()
    ends = ends[~ends.str.startswith(("Burned part", "Two-part"))]
    for text, n in ends.value_counts().items():
        parts.append(f"{text[0].lower() + text[1:]}: {n}")
    return "; ".join(parts)


def _o2_span(lo: float, hi: float) -> str:
    return f"{_pct(lo)}%" if abs(hi - lo) < 1e-9 else f"{_pct(lo)}–{_pct(hi)}%"


def _tests(n: int) -> str:
    return f"{n} test" if n == 1 else f"{n} tests"


def _cap(s: str) -> str:
    return s[0].upper() + s[1:]


def _material_rows(box: dict) -> list[dict]:
    t = _solids()
    ug = t[t.gravity_g < 0.02]
    out = []
    for m in sorted(ug.material.dropna().unique(), key=lambda m: (-(ug.material == m).sum(), m)):
        if m.startswith("Not named"):
            continue
        tm = ug[ug.material == m]
        near = tm[tm.o2_frac.between(*box["o2_frac"])]
        lo, hi = float(tm.o2_frac.min()), float(tm.o2_frac.max())
        out.append({"material": m, "n_tests": int(len(tm)), "n_near": int(len(near)), "near_ids": near.test_id.tolist(),
                    "all_ids": tm.test_id.tolist(), "o2_range": [lo, hi], "outcomes": _outcome_words(near),
                    "datasets": sorted(tm.dataset.unique().tolist()),
                    "tone": "text" if len(near) else "nodata",
                    "verdict": "tested at this oxygen level" if len(near) else f"tested only at {_o2_span(lo, hi)} oxygen"})
    return out


def _model_rows(preset: dict) -> list[dict]:
    st = get_store()
    out = []
    for ds, mid, label in MODELS:
        t = st.usable_tests(ds)
        sc = {"o2_frac": preset["o2_frac"], "pressure_kpa": preset["pressure_kpa"]}
        if ds == "flex":
            sc.update({"fuel": "n-heptane", "d0_mm": 3.0, "co2_frac": 0.0, "he_frac": 0.0})
            what = "a 3 mm n-heptane droplet"
        else:
            fuel = t.fuel.value_counts().index[0]
            sc.update({"fuel": fuel, "fuel_flow_mg_s": float(t.fuel_flow_mg_s.median())})
            what = f"a {fuel} flame at the median tested fuel flow"
        try:
            pr = surrogate.predict(mid, sc, with_sensitivity=False)
        except FileNotFoundError:
            continue
        verdict, tone = _verdict(pr["p"], pr["domain"]["status"])
        conf = pr["confidence"] if pr["domain"]["status"] == "inside" else "low"
        out.append({"label": label, "what": what, "p": round(pr["p"], 3), "status": pr["domain"]["status"],
                    "verdict": verdict, "tone": tone, "confidence": conf, "mode": "gas" if ds != "flex" else "droplet"})
    return out


def _environment(tid: str, material: str | None) -> dict:
    spec = TOPICS[tid]
    preset = next(p for p in config.presets()["presets"] if p["id"] == spec["preset"])
    box = next(t for t in config.presets()["targets"] if t["id"] == spec["target"])
    st = get_store()
    solids = _solids()
    ug = solids[solids.gravity_g < 0.02]
    mats = _material_rows(box)
    sel = next((m for m in mats if m["material"] == material), None)
    scope = [sel] if sel else mats
    partial = 0.02 < preset["gravity_g"] < 0.95
    n_partial = int(st.usable_tests().gravity_g.between(0.02, 0.95).sum())
    place = spec["title"].replace(" fire risk", "")
    g_name = gravity_label(preset["gravity_g"]).split(" (")[0]
    o2_lo, o2_hi = float(ug.o2_frac.min()), float(ug.o2_frac.max())

    solid_near = [i for m in scope for i in m["near_ids"]]
    fire = {}
    for ds, label in FIRE_DS.items():
        inside = _in_box(st.usable_tests(ds).dropna(subset=["o2_frac", "pressure_kpa"]), box)
        if len(inside):
            known = inside[inside.burned.notna()]
            fire[ds] = {"label": label, "ids": inside.test_id.tolist(), "n": len(inside),
                        "known_ids": known.test_id.tolist(), "n_known": len(known), "n_burned": int(known.burned.sum())}
    models = _model_rows(preset)

    # ---- finding: the solid-material evidence first, then the nearest flames, then the gravity gap
    if sel:
        lo, hi = sel["o2_range"]
        if sel["n_near"]:
            s = (f"{sel['material']} was burned in orbit at {place} oxygen levels in {_tests(sel['n_near'])}"
                 + (f" ({sel['outcomes']})." if sel["outcomes"] else "; the tables do not say how those tests ended."))
        else:
            s = (f"{sel['material']} was burned in orbit only at {_o2_span(lo, hi)} oxygen, "
                 f"never at the {preset['o2_frac'] * 100:.0f}% planned for {place}.")
    elif solid_near:
        s = f"In {place} air ({_air(preset)}), {len(solid_near)} real solid-material tests were run in orbit at this oxygen level."
    else:
        s = (f"No solid material has ever been burned in orbit in {place} air ({_air(preset)}): "
             f"NASA's real solid tests stopped at {_pct(o2_hi)}% oxygen.")
    if fire and not sel:
        bits = [f"{f['n']} {f['label']} tests" for f in fire.values()]
        nk, nb = sum(f["n_known"] for f in fire.values()), sum(f["n_burned"] for f in fire.values())
        s += f" The closest flames are {' and '.join(bits)} inside this air range; {nb} of the {nk} with an outcome kept burning."
    if partial:
        s += f" Nothing has ever been burned at {g_name}."
    finding = s

    # ---- grade
    what = sel["material"] if sel else "solid-material"
    if len(solid_near) >= 5:
        grade = {"label": "Measured", "tone": "text", "why": f"{len(solid_near)} real {what} tests at this oxygen level."}
    elif solid_near:
        grade = {"label": "Few tests", "tone": "warn", "why": f"Only {_tests(len(solid_near))} of {what} at this oxygen level."}
    elif fire and not sel:
        grade = {"label": "Close conditions", "tone": "warn",
                 "why": "No solid material was tested in this air. Real droplet or gas-flame tests were."}
    else:
        grade = {"label": "Not tested", "tone": "warn",
                 "why": f"{sel['material'] if sel else 'No solid material'} was {'never ' if sel else ''}tested at this oxygen level."}
    if partial:
        grade["why"] += f" None was at {g_name}: microgravity and Earth results can only bracket it."

    # ---- columns
    m_items = []
    for m in scope:
        lo, hi = m["o2_range"]
        if m["n_near"]:
            text = f"{m['material']}: {_tests(m['n_near'])} at this oxygen level" + (f" ({m['outcomes']})" if m["outcomes"] else "")
            m_items.append({"text": text, "citation": _rows(m["near_ids"], "test_id")})
        else:
            m_items.append({"text": f"{m['material']}: {_tests(m['n_tests'])}, {'all ' if m['n_tests'] > 1 else ''}at {_o2_span(lo, hi)} oxygen",
                            "citation": _rows(m["all_ids"], "o2_frac", "max")})
    for f in fire.values():
        m_items.append({"text": f"{_cap(f['label'])} tests in this air range: {f['n_burned']} of the {f['n_known']} with an outcome kept burning",
                        "citation": _rows(f["known_ids"])})
    # ACME's Burning Rate Emulator imitates a burning solid with a gas burner; its daily summary records oxygen, not pressure
    bre = st.usable_tests("acme_bre")
    bre = bre[bre.o2_frac.between(*box["o2_frac"])]
    lit = bre[bre.test_end.fillna("").str.startswith("At least one flame ignited")]
    if not sel and len(bre):
        days = lit.mission_date.nunique()
        m_items.append({"text": (f"Burning Rate Emulator (ACME), a gas burner that imitates a burning solid: flames ignited at "
                                 f"{place} oxygen levels on {days} test day{'s' if days != 1 else ''} "
                                 f"({', '.join(sorted({_pct(v) + '%' for v in lit.o2_frac}))} oxygen; pressure not given in its table)"
                                 if len(lit) else
                                 f"Burning Rate Emulator (ACME): no flame recorded as ignited at {place} oxygen levels"),
                        "citation": _rows(bre.test_id, "o2_frac")})
    measured = {"summary": ("Real solid-material tests in orbit at this oxygen level, then the nearest real flames. "
                            "The solid tables record no pressure."),
                "citation": _rows(solid_near, "test_id") if solid_near else None, "items": m_items}
    inferred = {"summary": (f"Two models learned from the real flame tests estimate whether a flame keeps burning in {place} air. "
                            "No model is trained for solid materials: their tables record no pressure, and BASS-II no burned-or-not outcome."),
                "items": [{"text": f"{r['label']}, {r['what']}: {r['verdict'].lower()}"
                                   + (f" ({r['p'] * 100:.0f}%, confidence {r['confidence']})" if r["status"] != "outside" else ""),
                           "tone": r["tone"]} for r in models]}
    un = []
    if partial:
        un.append({"text": f"{gravity_label(preset['gravity_g'])}: {n_partial} tests of any kind."})
    if preset["o2_frac"] > o2_hi:
        un.append({"text": f"Any solid material above {_pct(o2_hi)}% oxygen in orbit. {place} plans {preset['o2_frac'] * 100:.0f}%."})
    un.append({"text": "Pressure: none of the solid-material tables records it."})
    for m in scope:
        if not m["n_near"]:
            un.append({"text": f"{m['material']} at {place} oxygen levels."})
    untested = {"summary": "What no experiment in the loaded data covers.", "items": un[:5]}

    pts = pd.concat([st.usable_tests(ds) for ds in FIRE_DS])
    pts = pts.dropna(subset=["o2_frac", "pressure_kpa"])
    pts = pts[pts.pressure_kpa <= 220]
    band_src = (ug[ug.material == sel["material"]] if sel else ug)
    visual = {"kind": "envelope", "x": "o2_frac", "y": "pressure_kpa",
              "points": pts[["test_id", "o2_frac", "pressure_kpa", "burned", "dataset"]].to_dict("records"),
              "band": {"o2_frac": [float(band_src.o2_frac.min()), float(band_src.o2_frac.max())],
                       "label": f"{sel['material'] if sel else 'Solid materials'} tested in orbit",
                       "ids": band_src.test_id.tolist()},
              "box": {"label": f"{place} air", "o2_frac": box["o2_frac"], "pressure_kpa": box["pressure_kpa"]},
              "marker": {"o2_frac": preset["o2_frac"], "pressure_kpa": preset["pressure_kpa"]},
              "caption": ("Each dot is one real microgravity test of a fuel droplet (FLEX) or gas flame (CFI-G): amber kept burning, "
                          "blue went out, hollow has no outcome. The shaded band is the oxygen range of the real solid-material tests "
                          "in orbit; their tables record no pressure, so it spans the whole height. The outlined box is the air this place plans to use.")}
    lab_mode = "gas"
    return {"finding": finding, "grade": grade, "visual": visual, "measured": measured, "inferred": inferred,
            "untested": untested, "materials": mats, "material": sel["material"] if sel else None,
            "next": [{"label": "Try this air in the simulator", "href": f"/lab?preset={preset['id']}&mode={lab_mode}"},
                     {"label": "See which experiments matter most here", "href": f"/places?place={spec['target']}"},
                     {"label": "Open the solid-material tests", "href": "/data?dataset=bass2"}]}


def _microgravity() -> dict:
    """The same samples burned in orbit and on the ground (SAFFIRE-2): what gravity changes."""
    t = get_store().usable_tests("saffire2")
    t = t[t.burned.notna() & t.material.notna() & ~t.material.str.contains("two-part") & ~t.material.str.startswith("Not named")]
    ug, g1 = t[t.gravity_g < 0.02], t[t.gravity_g > 0.95]
    items = []
    finding = "With no up, hot gas does not rise: a flame becomes a slow, round shell fed only by whatever air drifts past it."
    for m in sorted(t.material.unique()):
        a, b = ug[ug.material == m], g1[g1.material == m]
        if len(a) and len(b):
            items.append({"text": f"{m}: burned the whole sample in {int(a.burned.sum())} of {len(a)} tests in orbit, "
                                  f"{int(b.burned.sum())} of {len(b)} on the ground",
                          "citation": _rows(pd.concat([a, b]).test_id)})
    sil_ug, sil_g = ug[ug.material == "Silicone"], g1[g1.material == "Silicone"]
    if len(sil_ug) and len(sil_g):
        finding += (f" In SAFFIRE-2, silicone samples burned completely in {int(sil_g.burned.sum())} of {len(sil_g)} ground tests "
                    f"but in {int(sil_ug.burned.sum())} of {len(sil_ug)} in orbit, with air moving at 20 cm/s: "
                    "on Earth, buoyancy feeds the flame; in orbit only the airflow does.")
    n_partial = int(get_store().usable_tests().gravity_g.between(0.02, 0.95).sum())
    n_flow = int(ug.flow_cm_s.notna().sum())
    return {"finding": finding,
            "grade": {"label": "Measured", "tone": "text",
                      "why": f"{len(ug)} flight tests and {len(g1)} ground tests of the same samples, with a recorded outcome."} if len(items)
            else {"label": "Documented", "tone": "text-2", "why": "Report text only."},
            "visual": {"kind": "flames", "caption": "Same fuel, same air. On Earth buoyancy pulls fresh air in from below and stretches the flame upward. "
                                                   "In microgravity nothing moves the air, so the flame sits as a dim sphere and can starve itself."},
            "measured": {"summary": "SAFFIRE-2: each sample burned in orbit (Cygnus vehicle, 20 cm/s airflow) and on the ground.",
                         "items": items},
            "inferred": {"summary": "The simulator estimates outcomes between the measured points, from droplet and gas-flame tests.",
                         "items": [{"text": "Change oxygen, pressure and fuel supply in the simulator and watch the flame respond."}]},
            "untested": {"summary": "What no experiment in the loaded data covers.",
                         "items": [{"text": f"Gravity between microgravity and Earth (Moon, Mars): {n_partial} tests."},
                                   {"text": f"Airflow other than 20 cm/s for these samples in orbit: {len(ug) - n_flow} tests."
                                    if len(ug) - n_flow else "Any airflow other than 20 cm/s for these samples in orbit."}]},
            "materials": [], "material": None,
            "next": [{"label": "Change the air yourself", "href": "/lab"},
                     {"label": "See the experiments behind this", "href": "/explore?open=inv:Saffire-II"},
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
                       "caption": "Bar length is the number of real tests inside each environment's oxygen and pressure range "
                                  "(tests that record both; the solid-material tables record no pressure). "
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
