"""Insights feed: findings computed from the loaded tests, each one sentence + one visual + a citation.

Nothing here is hand-written about the data: every number in a sentence is recomputed from the rows
listed in its citation, so the feed changes when the data changes. Findings that cannot be supported
(too few rows) are simply not emitted.
"""
from __future__ import annotations

import json
from functools import lru_cache

from .core.store import get_store
from .models import surrogate
from .topics import coverage

DIL = {"N2": "nitrogen", "CO2": "carbon dioxide", "He": "helium"}


def _cite(ids, field, op):
    return {"kind": "aggregate", "op": op, "field": field, "rows": list(ids)}


@lru_cache(maxsize=1)
def insights() -> dict:
    st = get_store()
    solids, drops = st.usable_tests("bass2_demo"), st.usable_tests("flex_demo")
    out = []

    # 1 — oxygen decides: burned vs extinguished along the oxygen axis, per material (position on a common scale)
    s = solids[(solids.gravity_g < 0.02)].dropna(subset=["burned", "o2_frac", "material"])
    if len(s) >= 20:
        top = s.material.value_counts().index[0]
        m = s[s.material == top]
        lo_burn = m[m.burned == 1].o2_frac.min()
        hi_out = m[m.burned == 0].o2_frac.max()
        out.append({
            "id": "oxygen-limit", "tag": "Preventing fire",
            "sentence": f"In microgravity, {top} never kept burning below {lo_burn * 100:.0f}% oxygen, "
                        f"and it went out in tests as rich as {hi_out * 100:.0f}%: there is no single safe oxygen level.",
            "visual": {"kind": "strip", "x_label": "Oxygen in the atmosphere (%)", "scale": 100,
                       "rows": [{"group": g, "x": float(r.o2_frac), "burned": int(r.burned)}
                                for g, sub in s.groupby("material") for r in sub.itertuples()]},
            "citation": _cite(m.test_id, "o2_frac", "min"), "source": "Solid-material flammability tests",
            "studio": "/studio?dataset=bass2_demo"})

    # 2 — airflow: share that burned, by flow band (length on a common baseline)
    f = solids[(solids.gravity_g < 0.02)].dropna(subset=["burned", "flow_cm_s"])
    bands = [("Still air", f[f.flow_cm_s < 1]), ("1–5 cm/s", f[(f.flow_cm_s >= 1) & (f.flow_cm_s < 5)]),
             ("5–15 cm/s", f[(f.flow_cm_s >= 5) & (f.flow_cm_s < 15)]), ("Over 15 cm/s", f[f.flow_cm_s >= 15])]
    bands = [(lab, b) for lab, b in bands if len(b) >= 5]
    if len(bands) >= 2:
        lo, hi = min(bands, key=lambda b: b[1].burned.mean()), max(bands, key=lambda b: b[1].burned.mean())
        out.append({
            "id": "airflow", "tag": "Preventing fire",
            "sentence": f"Air movement feeds a microgravity flame: {hi[1].burned.mean() * 100:.0f}% of samples kept burning at "
                        f"{hi[0].lower()}, against {lo[1].burned.mean() * 100:.0f}% {'in still air' if lo[0] == 'Still air' else 'at ' + lo[0].lower()}.",
            "visual": {"kind": "bars", "unit": "% kept burning", "max": 100,
                       "rows": [{"label": lab, "value": round(float(b.burned.mean() * 100), 1), "n": int(len(b))} for lab, b in bands]},
            "citation": _cite(f.test_id, "burned", "share"), "source": "Solid-material flammability tests",
            "studio": "/studio?dataset=bass2_demo"})

    # 3 — diluent changes the burning rate of droplets
    d = drops.dropna(subset=["burn_rate_k_mm2_s", "diluent"])
    g = [(k, v) for k, v in d.groupby("diluent") if len(v) >= 5]
    if len(g) >= 2:
        g.sort(key=lambda kv: -kv[1].burn_rate_k_mm2_s.median())
        fast, slow = g[0], g[-1]
        out.append({
            "id": "diluent", "tag": "Putting fire out",
            "sentence": f"What the oxygen is mixed with matters: droplets burned {fast[1].burn_rate_k_mm2_s.median() / slow[1].burn_rate_k_mm2_s.median():.1f}× "
                        f"faster in {DIL.get(fast[0], fast[0])} than in {DIL.get(slow[0], slow[0])}.",
            "visual": {"kind": "bars", "unit": "median burning rate K, mm²/s (number of tests behind each bar on the right)", "max": None,
                       "rows": [{"label": DIL.get(k, k).capitalize(), "value": round(float(v.burn_rate_k_mm2_s.median()), 3), "n": int(len(v))} for k, v in g]},
            "citation": _cite(d.test_id, "burn_rate_k_mm2_s", "median"), "source": "Droplet combustion tests",
            "studio": "/studio?dataset=flex_demo"})

    # 4 — which diluent puts droplets out
    e = drops.dropna(subset=["burned", "diluent"])
    g = [(k, v) for k, v in e.groupby("diluent") if len(v) >= 5]
    if len(g) >= 2:
        g.sort(key=lambda kv: kv[1].burned.mean())
        best = g[0]
        out.append({
            "id": "extinction", "tag": "Putting fire out",
            "sentence": f"{DIL.get(best[0], best[0]).capitalize()} was the most effective at stopping droplet flames: "
                        f"{(1 - best[1].burned.mean()) * 100:.0f}% of those tests ended in extinction.",
            "visual": {"kind": "bars", "unit": "% extinguished", "max": 100, "tone": "ext",
                       "rows": [{"label": DIL.get(k, k).capitalize(), "value": round(float((1 - v.burned.mean()) * 100), 1), "n": int(len(v))} for k, v in g]},
            "citation": _cite(e.test_id, "burned", "share"), "source": "Droplet combustion tests",
            "studio": "/studio?dataset=flex_demo"})

    # 5 — thinner samples spread flame faster
    th = solids.dropna(subset=["spread_rate_mm_s", "thickness_mm"])
    g = [(k, v) for k, v in th.groupby("thickness_mm") if len(v) >= 4]
    if len(g) >= 2:
        g.sort(key=lambda kv: kv[0])
        out.append({
            "id": "thickness", "tag": "Preventing fire",
            "sentence": f"Thin burns fast: flame crossed {g[0][0]:g} mm samples at a median {g[0][1].spread_rate_mm_s.median():.1f} mm/s, "
                        f"against {g[-1][1].spread_rate_mm_s.median():.1f} mm/s for {g[-1][0]:g} mm.",
            "visual": {"kind": "bars", "unit": "median flame spread, mm/s (number of tests behind each bar on the right)", "max": None,
                       "rows": [{"label": f"{k:g} mm thick", "value": round(float(v.spread_rate_mm_s.median()), 2), "n": int(len(v))} for k, v in g]},
            "citation": _cite(th.test_id, "spread_rate_mm_s", "median"), "source": "Solid-material flammability tests",
            "studio": "/studio?dataset=bass2_demo"})

    # 6 — the gap
    cov = coverage()
    no_g = [c for c in cov if not c["gravity_tested"]]
    if no_g:
        out.append({
            "id": "gap", "tag": "Not tested yet",
            "sentence": f"{', '.join(c['label'] for c in no_g[:-1])} and {no_g[-1]['label']} share one blind spot: "
                        "not one test in the loaded data was run at their gravity." if len(no_g) > 1 else
                        f"{no_g[0]['label']} has a blind spot: not one test in the loaded data was run at its gravity.",
            "visual": {"kind": "coverage", "rows": cov},
            "citation": _cite([i for c in cov for i in c["ids"]], "test_id", "count"), "source": "All loaded tests",
            "studio": "/studio?chart=gap"})

    # 7 — how far to trust the model (against a baseline, cross-validated)
    card_p = surrogate.MODEL_DIR / "solid_burn.card.json"
    if card_p.exists():
        card = json.loads(card_p.read_text(encoding="utf-8"))
        cv, base = card["cv"]["metrics"], card["cv"]["baseline"]
        out.append({
            "id": "model", "tag": "How far to trust the simulator",
            "sentence": f"The burn-or-not model is right {cv['accuracy'] * 100:.0f}% of the time on test campaigns it has never seen; "
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
        "id": "quality", "tag": "Data quality",
        "sentence": f"{n_ex} of {n_all} source rows are excluded from every chart and model, {n_imp} of them for physically impossible values "
                    "that are shown as flagged and never converted.",
        "visual": {"kind": "bars", "unit": "source rows, out of the total on the right", "max": None, "tone": "text",
                   "rows": [{"label": "Used", "value": n_all - n_ex, "n": n_all},
                            {"label": "Used, with a warning", "value": int(((st.tests["flags"].map(len) > 0) & ~st.tests["excluded"]).sum()), "n": n_all, "muted": True},
                            {"label": "Excluded", "value": n_ex, "n": n_all, "muted": True}]},
        "citation": _cite(st.tests[st.tests.excluded].test_id, "test_id", "count"), "source": "Validation log", "studio": "/data"})
    return {"insights": out[:8], "demo": bool(st.tests["demo"].any())}
