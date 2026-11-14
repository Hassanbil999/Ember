"""SPEC §8: the illustrative reduced-order flame model, ported line for line from prototype/index.html.

model()     flame limit, burns/goes out, spread rate (§8.1)
simulate()  time series of one burn (§8.2), the reference implementation is the prototype's simulate()
rec_dist()  distance to a measured test point (§8.3)
"""
from __future__ import annotations

import math
from dataclasses import dataclass

PSI_TO_KPA = 6.89476
U_D = 0.3                      # cm/s, diffusion floor: u_d² = 0.09
DT, SAMPLE_MM, IGN = 0.05, 100.0, 1.5

DEFAULTS = {
    "fabric": {"xmin": 15.5, "ustar": 8.0, "kl": 1.5, "kh": 0.78, "c": 0.46, "pexp": 0.15},
    "pmma": {"xmin": 16.0, "ustar": 5.0, "kl": 1.5, "kh": 0.78, "c": 0.30, "pexp": 0.15},
}


@dataclass
class Result:
    ub: float
    ueff: float
    xlim: float
    margin: float
    burns: bool
    regime: str          # burns | quench | blowoff
    spread: float        # mm/s

    def as_dict(self) -> dict:
        return {"ub": self.ub, "ueff": self.ueff, "xlim": self.xlim, "margin": self.margin, "burns": self.burns,
                "regime": self.regime, "spread": self.spread}


def model(g: float, o2: float, psi: float, u: float, params: dict) -> Result:
    ub = 30 * math.sqrt(max(g, 0.0))
    ueff = math.sqrt(u * u + ub * ub + U_D * U_D)
    L = math.log(ueff / params["ustar"])
    k = params["kl"] if L < 0 else params["kh"]
    xlim = (params["xmin"] + k * L * L) * (14.7 / psi) ** params.get("pexp", 0.15)
    margin = o2 - xlim
    burns = margin >= 0
    spread = params["c"] * margin * (ueff / (ueff + 5)) if burns else 0.0
    return Result(ub, ueff, xlim, margin, burns, "burns" if burns else ("quench" if L < 0 else "blowoff"), spread)


def limit_at(u: float, g: float, psi: float, params: dict) -> float:
    return model(g, 0.0, psi, u, params).xlim


def simulate(g: float, o2: float, psi: float, u: float, params: dict) -> dict:
    r = model(g, o2, psi, u, params)
    t_burn = SAMPLE_MM / max(r.spread, 0.01) + 1.5 if r.burns else math.inf
    D = min(240, max(10, math.ceil((t_burn + 4) / 5) * 5)) if r.burns else 10
    n = round(D / DT) + 1
    I, X, T = [0.0] * n, [0.0] * n, [0.0] * n
    x, st, t_out, t_end, lv = 0.0, "lit", None, None, 0.0
    for k in range(n):
        t = k * DT
        ign = t < IGN
        if st == "lit":
            target = 1.0 if r.burns else (0.55 if ign else 0.0)
            lv += (target - lv) * min(1.0, (2.2 if target > lv else 1.4) * DT)
            x += r.spread * min(1.0, lv * 1.15) * DT
            if not r.burns and not ign and lv < 0.03:
                st, lv, t_out = "out", 0.0, t
            if x >= SAMPLE_MM:
                x, st, t_end = SAMPLE_MM, "done", t
        elif st == "done":
            lv *= max(0.0, 1 - 1.8 * DT)
        I[k], X[k], T[k] = lv, x, t
    return {"result": r.as_dict(), "D": D, "dt": DT, "n": n, "t": T, "I": I, "x_mm": X, "t_out": t_out, "t_end": t_end}


def rec_dist(point: dict, g: float, o2: float, psi: float, u: float, material: str) -> float:
    """§8.3 distance from the settings to one test point. Missing pressure or flow is left out of the sum."""
    if point.get("o2_pct") is None:
        return math.inf
    d2 = ((g - (point.get("gravity_g") or 0)) / 0.3) ** 2 + ((o2 - point["o2_pct"]) / 8) ** 2
    if point.get("pressure_kpa") is not None:
        d2 += ((psi * PSI_TO_KPA - point["pressure_kpa"]) / 30) ** 2
    if point.get("flow_cm_s") is not None:
        d2 += (math.log((u + 0.3) / (point["flow_cm_s"] + 0.3)) / 1.2) ** 2
    if point.get("material") != material:
        d2 += 2.25
    return math.sqrt(d2)


def fit_label(d: float) -> str:
    return "close" if d < 1 else "partial" if d < 2.5 else "distant"
