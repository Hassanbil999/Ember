"""Where an estimate can be trusted: the model's "applicability domain" (OECD QSAR principle 3: a model
must state the domain in which it makes reliable predictions).

Only tests of the SAME fuel count as evidence (same carbon number and dilution for gas jets, same liquid
for drops). Distances are measured on the continuous inputs, each divided by its spread in the training
data so oxygen in %, pressure in psi and flow in mg/s count equally. Thresholds come from the data itself:

  close    the median distance from a NASA test to its nearest same-fuel neighbour. A request this close
           to a real test is TESTED: the real tests answer, the model only cross-checks.
  inside   the 95th percentile of every test's mean distance to its 5 nearest same-fuel neighbours.
           Within twice this, and inside the tested range of every input, it is ESTIMATED by the model.
  beyond   anything else, any gravity other than microgravity, or a fuel with no tests: UNTESTED.
           No number is produced.
"""
from __future__ import annotations

import numpy as np

K = 5


def continuous(features: list[str]) -> list[int]:
    return [i for i, f in enumerate(features) if f not in ("carbon_n", "heptane")]


def same_fuel_mask(problem_key: str, X: np.ndarray, features: list[str], x: np.ndarray) -> np.ndarray:
    keys = ("carbon_n", "fuel_share") if problem_key == "gas" else ("heptane",)
    m = np.ones(len(X), bool)
    for k in keys:
        i = features.index(k)
        m &= np.isclose(X[:, i], x[i], atol=1e-6)
    return m


class Domain:
    def __init__(self, problem_key: str, X: np.ndarray, features: list[str]):
        self.key, self.X, self.features = problem_key, X, features
        self.cols = continuous(features)
        self.scale = X[:, self.cols].std(0)
        self.scale[self.scale == 0] = 1.0
        nn1, knn = [], []
        for j in range(len(X)):
            m = same_fuel_mask(problem_key, X, features, X[j])
            m[j] = False
            if m.sum() == 0:
                continue
            d = np.sort(self.dist(X[j], X[m]))
            nn1.append(d[0])
            knn.append(d[:K].mean())
        self.close = float(np.median(nn1))
        self.inside = float(np.percentile(knn, 95))
        self.edge = 2 * self.inside

    def dist(self, x: np.ndarray, Xs: np.ndarray) -> np.ndarray:
        return np.sqrt((((Xs[:, self.cols] - x[self.cols]) / self.scale) ** 2).sum(1))

    def assess(self, x: np.ndarray, gravity_g: float, labels: dict | None = None, units: dict | None = None) -> dict:
        labels, units = labels or {}, units or {}
        m = same_fuel_mask(self.key, self.X, self.features, x)
        reasons = []
        if gravity_g > 0.02:
            reasons.append("Every NASA test here ran in microgravity; no test has burned anything at "
                           f"{gravity_g:.3g} g, so the model has learned nothing about gravity.")
        if m.sum() == 0:
            reasons.append("No NASA test used this fuel.")
            return {"zone": "untested", "reasons": reasons, "same_fuel": 0, "idx": [], "dist": [], "knn": None}
        Xs = self.X[m]
        for i in self.cols:
            lo, hi = Xs[:, i].min(), Xs[:, i].max()
            if x[i] < lo - 1e-9 or x[i] > hi + 1e-9:
                f = self.features[i]
                u = (" " + units[f]) if units.get(f) else ""
                reasons.append(f"{labels.get(f, f)} {x[i]:.3g}{u} is outside what NASA tested for this fuel ({lo:.3g}–{hi:.3g}{u}).")
        d = self.dist(x, Xs)
        order = np.argsort(d)
        knn = float(d[order[:K]].mean())
        if knn > self.edge:
            reasons.append("Too far from the NASA tests of this fuel in the combination of inputs.")
        idx = np.flatnonzero(m)[order]
        if reasons:
            zone = "untested"
        elif d[order[0]] <= self.close:
            zone = "tested"
        else:
            zone = "estimated"
        return {"zone": zone, "reasons": reasons, "same_fuel": int(m.sum()), "idx": idx.tolist(),
                "dist": d[order].tolist(), "knn": knn, "close": self.close, "inside": self.inside}
