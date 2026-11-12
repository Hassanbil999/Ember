"""Simulator grid: model outputs precomputed over the three slider axes.

The browser interpolates this grid, so moving a slider needs no network round trip
(immediate feedback). One request per (mode, item, gravity, extra setting), cached.
"""
from __future__ import annotations

from functools import lru_cache

import numpy as np
import pandas as pd

from .core.store import get_store
from .models import surrogate

O2 = np.round(np.linspace(0.10, 1.00, 37), 4)
AXES = {
    "solid": {"burn": "solid_burn", "rate": "solid_spread", "dataset": "bass2_demo", "item": "material",
              "axes": [("o2_frac", O2), ("pressure_kpa", np.linspace(20, 140, 13)), ("flow_cm_s", np.linspace(0, 40, 11))],
              "rate_label": "flame spread", "rate_unit": "mm/s"},
    "droplet": {"burn": "droplet_burn", "rate": "droplet_k", "dataset": "flex", "item": "fuel",
                "axes": [("o2_frac", O2), ("pressure_kpa", np.linspace(20, 320, 13)), ("d0_mm", np.linspace(1, 6, 11))],
                "rate_label": "burning rate K", "rate_unit": "mm²/s"},
}


def _knn_dist(X: np.ndarray, G: np.ndarray, k: int) -> np.ndarray:
    out = np.empty(len(G))
    for i in range(0, len(G), 1024):                      # chunked to keep memory flat
        d = np.sqrt(((G[i:i + 1024, None, :] - X[None, :, :]) ** 2).sum(-1))
        out[i:i + 1024] = np.sort(d, axis=1)[:, :k].mean(1)
    return out


@lru_cache(maxsize=64)
def grid(mode: str, item: str, gravity: float = 0.0, diluent: str = "N2") -> dict:
    spec = AXES[mode]
    burn, rate = surrogate.load(spec["burn"]), surrogate.load(spec["rate"])
    t = get_store().usable_tests(spec["dataset"])
    t = t[t[spec["item"]] == item]
    (a, av), (b, bv), (c, cv_) = spec["axes"]
    A, B, C = np.meshgrid(av, bv, cv_, indexing="ij")
    fixed = {spec["item"]: item}
    if mode == "solid":
        fixed.update({"thickness_mm": float(t.thickness_mm.median()) if len(t) else 0.5, "gravity_g": float(gravity)})
    else:
        fixed.update({"co2_frac": 0.3 if diluent == "CO2" else 0.0, "he_frac": 0.3 if diluent == "He" else 0.0})
    df = pd.DataFrame({a: A.ravel(), b: B.ravel(), c: C.ravel(), **{k: v for k, v in fixed.items()}})
    Xb = burn["enc"].transform(df[burn["card"]["features"]])
    p = burn["model"].predict_proba(Xb)[:, 1]
    mu = rate["model"].predict(rate["enc"].transform(df[rate["card"]["features"]]))
    ad = burn["card"]["applicability"]
    dist = _knn_dist(burn["X"], Xb, ad["k"])
    cols = ["test_id", a, b, c, "burned"]
    cv = burn["card"]["cv"]
    return {
        "mode": mode, "item": item, "fixed": fixed, "demo": bool(t["demo"].any()) if len(t) else False,
        "axes": [{"var": v, "values": [round(float(x), 4) for x in vals]} for v, vals in spec["axes"]],
        "p": np.round(p, 3).tolist(), "rate": np.round(np.clip(mu, 0, None), 3).tolist(), "dist": np.round(dist, 2).tolist(),
        "inside": round(ad["inside"], 3), "edge": round(ad["edge"], 3),
        "tested": {k: v for k, v in burn["card"]["ranges"].items() if k in (a, b, c)},
        "gravity_is_feature": "gravity_g" in burn["card"]["features"],
        "rate_label": spec["rate_label"], "rate_unit": spec["rate_unit"],
        "tests": t[cols].dropna(subset=[a, b, c]).round(4).to_dict("records"),
        "cv": {"accuracy": cv["metrics"]["accuracy"], "baseline": cv["baseline"]["accuracy"], "auc": cv["metrics"].get("auc"), "scheme": cv["scheme"], "rows": burn["card"]["rows"]},
    }


def items() -> dict:
    st = get_store()
    return {"solid": sorted(st.usable_tests("bass2_demo").material.dropna().unique().tolist()),
            "droplet": sorted(st.usable_tests("flex").fuel.dropna().unique().tolist()),
            "diluents": ["N2", "CO2", "He"]}
