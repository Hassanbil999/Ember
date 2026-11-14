"""POST /api/simulate and GET /api/flammability-map: the §8 model on the server, with §8.3 coverage and evidence."""
from __future__ import annotations

import math

from ..catalog.query import catalog
from .model import PSI_TO_KPA, fit_label, limit_at, model, rec_dist, simulate

MAP_U = [0.1 * (50 / 0.1) ** (i / 80) for i in range(81)]          # 0.1 → 50 cm/s, log-spaced (the prototype map)


def coverage(g: float, o2: float, psi: float, points: list[dict]) -> dict:
    """§8.3: partial gravity first, then extrapolation in oxygen or pressure, judged against the loaded points."""
    if 0.02 < g < 0.95:
        return {"kind": "partial-g", "text": "No partial-gravity data exists yet. This sits between the 0 g and 1 g results."}
    o2s = [p["o2_pct"] for p in points if p.get("o2_pct") is not None]
    max_o2 = max(o2s) if o2s else 21.0
    if o2 > max_o2 + 0.5:
        return {"kind": "o2", "text": f"Extrapolated: no solid-fuel test above {round(max_o2, 1):g}% O₂ in this dataset."}
    kpas = [p["pressure_kpa"] for p in points if p.get("pressure_kpa") is not None]
    min_kpa = min(kpas) if kpas else 101.3
    if psi * PSI_TO_KPA < min_kpa - 5:
        return {"kind": "pressure", "text": "Extrapolated: no reduced-pressure solid-fuel tests in this dataset."}
    return {"kind": "inside", "text": "Inside the range of tested conditions."}


def nearest(g: float, o2: float, psi: float, u: float, material: str, points: list[dict], k: int = 3) -> list[dict]:
    scored = sorted(((rec_dist(p, g, o2, psi, u, material), p) for p in points), key=lambda x: x[0])
    return [{"distance": round(d, 4), "match": fit_label(d), **p} for d, p in scored[:k] if not math.isinf(d)]


def run(g: float, o2: float, psi: float, u: float, material: str) -> dict:
    c = catalog()
    P = c.params[material]
    s = simulate(g, o2, psi, u, P)
    iss = model(0.0, 21.0, 14.7, 10.0, P)
    return {
        "settings": {"g": g, "o2": o2, "psi": psi, "u": u, "material": material},
        "result": {**s["result"], "spread_vs_iss": (s["result"]["spread"] / iss.spread) if iss.spread > 0 and s["result"]["burns"] else None},
        "D": s["D"], "dt": s["dt"], "n": s["n"], "t_out": s["t_out"], "t_end": s["t_end"],
        "t": [round(x, 4) for x in s["t"]], "I": [round(x, 5) for x in s["I"]], "x_mm": [round(x, 4) for x in s["x_mm"]],
        "coverage": coverage(g, o2, psi, c.sim_points),
        "nearest": nearest(g, o2, psi, u, material, c.sim_points),
        "model_params": {**P, **c.params_meta[material]},
        "illustrative": "Reduced-order model fitted to published limits; it shows trends and is not a design tool.",
    }


def flammability_map(g: float, o2: float, psi: float, u: float, material: str) -> dict:
    c = catalog()
    P = c.params[material]
    gc = 0.0 if g < 0.02 else 1.0 if g > 0.95 else None
    pts = [p for p in c.sim_points if p["material"] == material and p.get("flow_cm_s") is not None and gc is not None
           and (p.get("gravity_g") or 0) == gc]
    r = model(g, o2, psi, u, P)
    return {
        "settings": {"g": g, "o2": o2, "psi": psi, "u": u, "material": material},
        "limit": [{"u": round(x, 5), "o2_limit": round(limit_at(x, g, psi, P), 4)} for x in MAP_U],
        "you": {"u": u, "o2": o2, "burns": r.burns, "xlim": r.xlim},
        "points": [{"code": p["code"], "u": p["flow_cm_s"], "o2": p["o2_pct"], "outcome": p["outcome"], "verified": p["verified"],
                    "sample": p.get("sample_desc")} for p in pts],
        "gravity_class": gc,
        "note": None if gc is not None else "Measured points are shown only at 0 g and 1 g; no partial-gravity tests exist.",
    }
