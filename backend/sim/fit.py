"""`ingest fit` (SPEC §8.4): fit X_min, u*, k_l, k_h, c per material to VERIFIED test points.

Loss: a hinge on the sign of X_O2 − X_lim (burned needs a margin ≥ +0.5 pt, went out ≤ −0.5 pt) plus squared
error on spread_mm_s where present. A point is usable only if it is verified and reports oxygen, pressure,
airflow, gravity and a burned / went-out outcome; nothing is assumed for a missing value. With fewer than
4 usable points the §8.1 defaults stay, and `n_points` records how many there were.
"""
from __future__ import annotations

from datetime import datetime, timezone

import numpy as np
import pandas as pd
from scipy.optimize import least_squares

from ..catalog.build import read, write
from .model import DEFAULTS, PSI_TO_KPA, model

NAMES = ["xmin", "ustar", "kl", "kh", "c"]
LOWER = [10.0, 0.5, 0.1, 0.1, 0.05]
UPPER = [25.0, 30.0, 5.0, 5.0, 2.0]
MARGIN = 0.5
SPREAD_SCALE = 0.5          # mm/s: one unit of residual
MIN_POINTS = 4


def usable(points: pd.DataFrame, material: str) -> pd.DataFrame:
    p = points[(points.material == material) & points.verified.astype(bool) & points.outcome.isin(["burned", "went_out"])]
    return p.dropna(subset=["o2_pct", "pressure_kpa", "flow_cm_s", "gravity_g"])


def _params(x: np.ndarray, pexp: float) -> dict:
    return {**dict(zip(NAMES, map(float, x))), "pexp": pexp}


def residuals(x: np.ndarray, pts: list[dict], pexp: float) -> np.ndarray:
    P = _params(x, pexp)
    out = []
    for p in pts:
        r = model(p["gravity_g"], p["o2_pct"], p["pressure_kpa"] / PSI_TO_KPA, p["flow_cm_s"], P)
        m = p["o2_pct"] - r.xlim
        out.append(max(0.0, MARGIN - m) if p["outcome"] == "burned" else max(0.0, m + MARGIN))
        if p.get("spread_mm_s") is not None and not pd.isna(p["spread_mm_s"]):
            out.append((r.spread - p["spread_mm_s"]) / SPREAD_SCALE)
    return np.asarray(out, dtype=float)


def fit_material(pts: list[dict], start: dict) -> tuple[dict, float]:
    x0 = np.clip([start[n] for n in NAMES], LOWER, UPPER)
    sol = least_squares(residuals, x0, bounds=(LOWER, UPPER), args=(pts, start.get("pexp", 0.15)), method="trf")
    res = residuals(sol.x, pts, start.get("pexp", 0.15))
    return _params(sol.x, start.get("pexp", 0.15)), float(np.sqrt(np.mean(res ** 2))) if len(res) else 0.0


def run() -> dict:
    points = read("atlas_test_points")
    if points.empty:
        raise SystemExit("No test points yet: run `python -m backend.ingest existing` and `seed` first.")
    rows, summary = [], {}
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    for mat, default in DEFAULTS.items():
        pts = usable(points, mat).to_dict("records")
        if len(pts) >= MIN_POINTS:
            params, rmse = fit_material(pts, default)
            rows.append({"material": mat, **params, "n_points": len(pts), "rmse": rmse, "fitted_at": now,
                         "source": f"fitted (SPEC §8.4) to {len(pts)} verified test points"})
        else:
            rows.append({"material": mat, **default, "n_points": len(pts), "rmse": None, "fitted_at": None,
                         "source": "defaults (SPEC §8.1)"})
        summary[mat] = {"usable_verified_points": len(pts), "fitted": len(pts) >= MIN_POINTS}
    write({"atlas_model_params": pd.DataFrame(rows)})
    print("fit:", summary)
    return summary
