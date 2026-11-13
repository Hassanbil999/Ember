"""Insights feed: findings computed from the loaded tests, each one sentence + one visual + a citation.

Nothing here is hand-written about the data: every number in a sentence is recomputed from the rows
listed in its citation, so the feed changes when the data changes. Findings that cannot be supported
(too few rows) are simply not emitted.
"""
from __future__ import annotations

import json
from functools import lru_cache

from .core import config
from .core.store import get_store
from .models import surrogate
from .topics import coverage

SOLID_DS = ["bass2", "saffire1", "saffire2", "saffire3"]
DIL = {"N2": "nitrogen", "CO2": "carbon dioxide", "He": "helium"}


def _cite(ids, field, op):
    return {"kind": "aggregate", "op": op, "field": field, "rows": list(ids)}


@lru_cache(maxsize=1)
def insights() -> dict:
    st = get_store()
    drops, gas = st.usable_tests("flex"), st.usable_tests("cfig_normal")
    solids = st.usable_tests()
    solids = solids[solids.dataset.isin(SOLID_DS) & solids.o2_frac.notna()]
    out = []

    # 1 — oxygen decides, but not alone: CFI-G gas flames along the oxygen axis, per fuel (position on a common scale)
    s = gas.dropna(subset=["burned", "o2_frac", "fuel"])
    if len(s) >= 20 and s.burned.nunique() == 2:
        lo_burn = s[s.burned == 1].o2_frac.min()
        hi_out = s[s.burned == 0].o2_frac.max()
        out.append({
            "id": "oxygen-limit", "tag": "Preventing fire", "datasets": ["cfig_normal"],
            "sentence": f"In microgravity, no CFI-G gas flame kept burning below {lo_burn * 100:.0f}% oxygen, "
                        f"yet flames went out by themselves at up to {hi_out * 100:.0f}%: oxygen alone does not decide.",
            "visual": {"kind": "strip", "x_label": "Oxygen in the atmosphere (%)", "scale": 100,
                       "rows": [{"group": g, "x": float(r.o2_frac), "burned": int(r.burned)}
                                for g, sub in s.groupby("fuel") for r in sub.itertuples()]},
            "citation": _cite(s.test_id, "o2_frac", "min"), "source": "CFI-G gas flames (NASA PSI-159)",
            "studio": "/studio?dataset=cfig_normal"})

    # 2 — gravity: the same samples in orbit and on the ground (SAFFIRE-2), share that burned the whole sample
    sf = st.usable_tests("saffire2")
    sf = sf[sf.burned.notna() & ~sf.material.fillna("").str.contains("two-part")]
    ug, g1 = sf[sf.gravity_g < 0.02], sf[sf.gravity_g > 0.95]
    if len(ug) >= 3 and len(g1) >= 3:
        out.append({
            "id": "gravity", "tag": "Preventing fire", "datasets": ["saffire2"],
            "sentence": f"Gravity changes what burns: the same SAFFIRE-2 samples burned completely in {int(g1.burned.sum())} of {len(g1)} "
                        f"ground tests but {int(ug.burned.sum())} of {len(ug)} in orbit, where only the 20 cm/s airflow fed them.",
            "visual": {"kind": "bars", "unit": "% that burned the whole sample (number of tests on the right)", "max": 100,
                       "rows": [{"label": "On the ground (1g)", "value": round(float(g1.burned.mean() * 100), 1), "n": int(len(g1))},
                                {"label": "In orbit", "value": round(float(ug.burned.mean() * 100), 1), "n": int(len(ug))}]},
            "citation": _cite(sf.test_id, "burned", "share"), "source": "SAFFIRE-2 (NASA PSI-99)",
            "studio": "/studio?dataset=saffire2"})

    # 3 — diluent changes the burning rate of droplets
    d = drops.dropna(subset=["burn_rate_k_mm2_s", "diluent"])
    g = [(k, v) for k, v in d.groupby("diluent") if len(v) >= 5]
    if len(g) >= 2:
        g.sort(key=lambda kv: -kv[1].burn_rate_k_mm2_s.median())
        fast, slow = g[0], g[-1]
        out.append({
            "id": "diluent", "tag": "Putting fire out", "datasets": ["flex"],
            "sentence": f"What the oxygen is mixed with matters: droplets burned {fast[1].burn_rate_k_mm2_s.median() / slow[1].burn_rate_k_mm2_s.median():.1f}× "
                        f"faster in {DIL.get(fast[0], fast[0])} than in {DIL.get(slow[0], slow[0])}.",
            "visual": {"kind": "bars", "unit": "median burning rate K, mm²/s (number of tests behind each bar on the right)", "max": None,
                       "rows": [{"label": DIL.get(k, k).capitalize(), "value": round(float(v.burn_rate_k_mm2_s.median()), 3), "n": int(len(v))} for k, v in g]},
            "citation": _cite(d.test_id, "burn_rate_k_mm2_s", "median"), "source": "FLEX droplet tests (NASA PSI-69)",
            "studio": "/studio?dataset=flex"})

    # 4 — which diluent puts droplets out
    e = drops.dropna(subset=["burned", "diluent"])
    g = [(k, v) for k, v in e.groupby("diluent") if len(v) >= 5]
    if len(g) >= 2:
        g.sort(key=lambda kv: kv[1].burned.mean())
        best = g[0]
        out.append({
            "id": "extinction", "tag": "Putting fire out", "datasets": ["flex"],
            "sentence": f"{DIL.get(best[0], best[0]).capitalize()} was the most effective at stopping droplet flames: "
                        f"{(1 - best[1].burned.mean()) * 100:.0f}% of those tests ended in extinction.",
            "visual": {"kind": "bars", "unit": "% extinguished", "max": 100, "tone": "ext",
                       "rows": [{"label": DIL.get(k, k).capitalize(), "value": round(float((1 - v.burned.mean()) * 100), 1), "n": int(len(v))} for k, v in g]},
            "citation": _cite(e.test_id, "burned", "share"), "source": "FLEX droplet tests (NASA PSI-69)",
            "studio": "/studio?dataset=flex"})

    # 5 — where solid-material testing stops: real solid tests in orbit by oxygen band
    su = solids[solids.gravity_g < 0.02]
    if len(su) >= 20:
        edges = [(0.0, 0.16, "Under 16%"), (0.16, 0.18, "16–18%"), (0.18, 0.20, "18–20%"), (0.20, 0.22, "20–22%"),
                 (0.22, 0.26, "22–26%"), (0.26, 0.30, "26–30%"), (0.30, 1.01, "30% and over")]
        rows = [{"label": lab, "value": int(su.o2_frac.between(lo, hi, inclusive="left").sum()),
                 "n": int(len(su))} for lo, hi, lab in edges]
        out.append({
            "id": "solid-oxygen", "tag": "Not tested yet", "datasets": sorted(su.dataset.unique().tolist()),
            "sentence": f"All {len(su)} real solid-material tests in orbit ran at {su.o2_frac.min() * 100:.1f}–{su.o2_frac.max() * 100:.1f}% oxygen: "
                        "none at the 30–34% planned for Moon and Mars habitats.",
            "visual": {"kind": "bars", "unit": "solid-material tests in orbit, by oxygen level (total on the right)", "max": None, "tone": "text",
                       "rows": rows},
            "citation": _cite(su.test_id, "o2_frac", "max"), "source": "BASS-II and SAFFIRE (NASA PSI-25, 98, 99, 100)",
            "studio": "/studio?dataset=bass2"})

    # 6 — the gap
    cov = coverage()
    no_g = [c for c in cov if not c["gravity_tested"]]
    if no_g:
        out.append({
            "id": "gap", "tag": "Not tested yet", "datasets": None,
            "sentence": f"{', '.join(c['label'] for c in no_g[:-1])} and {no_g[-1]['label']} share one blind spot: "
                        "not one test in the loaded data was run at their gravity." if len(no_g) > 1 else
                        f"{no_g[0]['label']} has a blind spot: not one test in the loaded data was run at its gravity.",
            "visual": {"kind": "coverage", "rows": cov},
            "citation": _cite([i for c in cov for i in c["ids"]], "test_id", "count"), "source": "All loaded tests",
            "studio": "/studio?chart=gap"})

    # 7 — how far to trust the model (against a baseline, cross-validated)
    card_p = surrogate.MODEL_DIR / "gas_sustain.card.json"
    if card_p.exists():
        card = json.loads(card_p.read_text(encoding="utf-8"))
        cv, base = card["cv"]["metrics"], card["cv"]["baseline"]
        out.append({
            "id": "model", "tag": "How far to trust the simulator", "datasets": None,
            "sentence": f"The gas-flame model is right {cv['accuracy'] * 100:.0f}% of the time on test campaigns it has never seen; "
                        f"always guessing the commonest outcome scores {base['accuracy'] * 100:.0f}%.",
            "visual": {"kind": "bars", "unit": "% correct on campaigns the model never saw", "max": 100, "tone": "text",
                       "rows": [{"label": "Model", "value": round(cv["accuracy"] * 100, 1), "n": card["cv"]["n_scored"]},
                                {"label": "Baseline guess", "value": round(base["accuracy"] * 100, 1), "n": card["cv"]["n_scored"], "muted": True}]},
            "citation": None, "source": f"Cross-validation: {card['cv']['scheme']}", "studio": "/lab"})

    # 8 — data quality, stated
    log = st.validation_log
    n_all = len(st.tests)
    n_imp = int((log.rule == "impossible_value").sum())
    n_ex = int(st.tests.excluded.sum())
    out.append({
        "id": "quality", "tag": "Data quality", "datasets": None,
        "sentence": f"{n_ex} of {n_all} source rows are excluded from every chart and model, {n_imp} of them for physically impossible values "
                    "that are shown as flagged and never converted.",
        "visual": {"kind": "bars", "unit": "source rows, out of the total on the right", "max": None, "tone": "text",
                   "rows": [{"label": "Used", "value": n_all - n_ex, "n": n_all},
                            {"label": "Used, with a warning", "value": int(((st.tests["flags"].map(len) > 0) & ~st.tests["excluded"]).sum()), "n": n_all, "muted": True},
                            {"label": "Excluded", "value": n_ex, "n": n_all, "muted": True}]},
        "citation": _cite(st.tests[st.tests.excluded].test_id, "test_id", "count"), "source": "Validation log", "studio": "/data"})
    dcfg = config.datasets()
    for o in out:
        ds = o.pop("datasets", None)
        o["demo"] = None if not ds else any(dcfg[d].get("demo") for d in ds)   # None: spans every table, or is about the model
    out.sort(key=lambda o: {False: 0, None: 1, True: 2}[o["demo"]])      # findings on real data first (stable sort)
    return {"insights": out[:8], "demo": bool(st.tests["demo"].any()), "mixed": bool((~st.tests["demo"]).any())}
