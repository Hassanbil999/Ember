"""How the data becomes a model, for the Statistics page. Three views per question, all from the same NASA table
and trained model as the fire check:

cleaning      rows in the NASA table → usable (rows flagged by the cleaning set aside) → with a recorded outcome →
              with every model input. The last count is what the model learns from.
clusters      unsupervised: a Gaussian mixture on the physical test conditions (oxygen, pressure, and leak size or
              drop size, CO₂ and helium), standardized, with the number of groups chosen by BIC among 2–6. The
              outcome is not used. Each group's share that kept burning is reported afterwards, and the agreement
              with NASA's own test campaigns is the adjusted Rand index. Exploratory only: no estimate uses it.
surface       supervised: what the Gaussian process learned for the most-tested fuel, as the chance it keeps burning
              over oxygen × pressure with the other inputs held at that fuel's median (CO₂ and helium at 0). Cells
              the fire check would call untested are left empty, so the map shows numbers only where the app does.
"""
from __future__ import annotations

from functools import lru_cache

import numpy as np
from sklearn.metrics import adjusted_rand_score
from sklearn.mixture import GaussianMixture
from sklearn.preprocessing import StandardScaler

from ..core.store import get_store
from . import service
from .problems import DATASETS, PROBLEMS

CATEGORICAL = ("carbon_n", "heptane", "fuel_share")
K_RANGE = range(2, 7)


def cleaning(key: str) -> list[dict]:
    pb, ds, st = PROBLEMS[key], DATASETS[key], get_store()
    usable = st.usable_tests(ds)
    return [
        {"stage": "Rows in the NASA table", "n": int((st.tests.dataset == ds).sum())},
        {"stage": "Usable after cleaning", "n": int(len(usable))},
        {"stage": "With a recorded outcome", "n": int(usable[pb.target].notna().sum())},
        {"stage": "With every model input", "n": int(len(pb.frame()))},
    ]


def clusters(key: str) -> dict:
    pb = PROBLEMS[key]
    df = pb.frame()
    cont = [f for f in pb.features if f not in CATEGORICAL]
    Z = StandardScaler().fit_transform(df[cont].to_numpy(float))
    fits = [(GaussianMixture(k, covariance_type="full", random_state=0, n_init=3, reg_covar=1e-3).fit(Z), k) for k in K_RANGE]
    bics = [{"k": k, "bic": round(float(g.bic(Z)), 1)} for g, k in fits]
    g, k = min(fits, key=lambda t: t[0].bic(Z))
    raw = g.predict(Z)
    order = [c for c, _ in sorted(((c, int((raw == c).sum())) for c in range(k)), key=lambda t: -t[1])]   # largest group first
    lab = np.array([order.index(c) for c in raw])
    groups = []
    for c in range(k):
        m = lab == c
        groups.append({"id": c + 1, "n": int(m.sum()), "kept_burning": round(float(df[pb.target][m].mean()), 3),
                       "mean": {f: round(float(df[f][m].mean()), 2) for f in cont},
                       "fuels": {str(f): int(n) for f, n in df.fuel[m].value_counts().items()}})
    points = [{"id": r.test_id, "fuel": r.fuel, "o2_pct": round(float(r.o2_pct), 2), "psi": round(float(r.psi), 2),
               "group": int(lab[i]) + 1, "burned": int(getattr(r, pb.target))} for i, r in enumerate(df.itertuples())]
    return {"inputs": [{"key": f, "label": pb.feature_labels[f], "unit": pb.units[f]} for f in cont], "k": int(k), "bic": bics,
            "ari_campaigns": round(float(adjusted_rand_score(df.campaign.astype(str), lab)), 2),
            "n_campaigns": int(df.campaign.nunique()), "groups": groups, "points": points}


def surface(key: str, nx: int = 34, ny: int = 26) -> dict:
    pb, b, dom = PROBLEMS[key], service._bundle(key), service._domain(key)
    df = pb.frame()
    fuel = df.fuel.value_counts().index[0]
    sub = df[df.fuel == fuel]
    base = {f: float(sub[f].median()) for f in pb.features}
    for f in ("co2_pct", "he_pct"):
        if f in base:
            base[f] = 0.0                                   # nitrogen as the rest of the air
    o2s = np.linspace(max(0.0, sub.o2_pct.min() - 3), sub.o2_pct.max() + 3, nx)
    psis = np.linspace(max(0.5, sub.psi.min() - 3), sub.psi.max() + 3, ny)
    rows = []
    for p_ in psis:
        for o in o2s:
            rows.append([o if f == "o2_pct" else p_ if f == "psi" else base[f] for f in pb.features])
    G = np.array(rows)
    chance = b["model"].predict_proba(G)[:, 1] if b.get("model") is not None else np.full(len(G), np.nan)
    cells = []
    for x, p in zip(G, chance):
        zone = dom.assess(x, 0.0)["zone"]
        cells.append(None if zone == "untested" or np.isnan(p) else round(float(p), 3))
    held = [{"label": pb.feature_labels[f], "value": round(base[f], 2), "unit": pb.units[f]}
            for f in pb.features if f not in ("o2_pct", "psi") + CATEGORICAL]
    tests = [{"id": r.test_id, "o2_pct": round(float(r.o2_pct), 2), "psi": round(float(r.psi), 2), "burned": int(getattr(r, pb.target))}
             for r in sub.itertuples()]
    return {"fuel": fuel, "model": b["card"]["chosen"], "held": held, "o2": [round(float(v), 2) for v in o2s],
            "psi": [round(float(v), 2) for v in psis], "chance": cells, "tests": tests,
            "outcome_yes": pb.outcome_yes, "outcome_no": pb.outcome_no}


@lru_cache(maxsize=1)          # same answer until the models are retrained (service.clear() resets it)
def build() -> dict:
    return {key: {"label": pb.label, "investigation": pb.investigation, "psi_id": pb.psi_id,
                  "cleaning": cleaning(key), "clusters": clusters(key), "surface": surface(key)}
            for key, pb in PROBLEMS.items()}
