"""Two answers built on the fire-check models, for the engineer's own settings.

oxygen_line   Where is the line? Oxygen is swept from low to high while every other input stays as entered.
              Each point gets the same zone rule as a single check (tested / estimated / untested), and a
              chance only where the zone allows one. The 50 % crossing is reported with its range (where the
              lowest and the highest of the 15 campaign-bootstrap models cross). Same-fuel NASA tests are drawn on it.
              If the estimate falls as oxygen rises, it is flagged: combustion physics expects more oxygen to
              help a flame, so a fall probably reflects other differences between those tests, not oxygen.

next_tests    Which test would teach the models most? "Query by committee" active learning (Seung, Opper and
              Sompolinsky, 1992): the 15 campaign-bootstrap models, each refitted on NASA campaigns drawn with replacement, are the
              committee; where they disagree most, one more test is most informative. Candidates stay inside
              what the hardware has already done for any fuel (so the test can be run), favour conditions
              far from existing tests of this fuel and close to the engineer's own settings, and are kept
              apart from each other so the three suggestions are different experiments.
"""
from __future__ import annotations

import itertools

import numpy as np

from .domain import same_fuel_mask

O2_AXIS = {"gas": (12.0, 45.0), "droplet": (10.0, 40.0)}
GRID = 11                      # points per input for next_tests (11³ candidates, a few hundred ms)
FALLING = 0.10                 # a drop of 10 points as oxygen rises is flagged


def _probs(b: dict, X: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    p = b["model"].predict_proba(X)[:, 1]
    F = np.array([m.predict_proba(X)[:, 1] for m in b["boot_models"]])
    return p, F.min(0), F.max(0)


def _cross(o2: np.ndarray, p: np.ndarray) -> float | None:
    """First oxygen (rising) where p goes from below 0.5 to 0.5 or above, linearly interpolated."""
    for i in range(1, len(p)):
        if p[i - 1] < 0.5 <= p[i]:
            return float(o2[i - 1] + (0.5 - p[i - 1]) * (o2[i] - o2[i - 1]) / (p[i] - p[i - 1]))
    return None


def _segments(o2: np.ndarray, keep: np.ndarray) -> list[list[float]]:
    out, start = [], None
    for i, k in enumerate(keep):
        if k and start is None:
            start = i
        if (not k or i == len(keep) - 1) and start is not None:
            end = i if k else i - 1
            out.append([float(o2[start]), float(o2[end])])
            start = None
    return out


def oxygen_line(pb, b: dict, dom, x: np.ndarray, gravity_g: float = 0.0) -> dict:
    j = pb.features.index("o2_pct")
    lo, hi = O2_AXIS[pb.key]
    o2 = np.round(np.arange(lo, hi + 1e-9, 0.5), 2)
    X = np.tile(x, (len(o2), 1))
    X[:, j] = o2
    zones = np.array([dom.assess(r, gravity_g)["zone"] for r in X])
    p, pl, ph = _probs(b, X)
    ok = zones != "untested"
    points = [{"o2_pct": float(o), "zone": z, "p": round(float(a), 3) if k else None,
               "low": round(float(lo), 3) if k else None, "high": round(float(hi), 3) if k else None}
              for o, z, a, lo, hi, k in zip(o2, zones, p, pl, ph, ok)]

    # the 50 % line, only where an estimate is allowed
    line = None
    if ok.any():
        idx = np.flatnonzero(ok)
        seg = idx[np.r_[True, np.diff(idx) == 1].cumprod().astype(bool)] if len(idx) else idx   # first continuous run
        c, c_lo, c_hi = _cross(o2[seg], p[seg]), _cross(o2[seg], ph[seg]), _cross(o2[seg], pl[seg])
        line = {"o2_pct": None if c is None else round(c, 1),
                "range": None if c is None else [round(v, 1) if v is not None else None for v in (c_lo, c_hi)],
                "max_p": round(float(p[ok].max()), 3), "min_p": round(float(p[ok].min()), 3)}
        # physics check: does the estimate fall as oxygen rises (beyond the model spread)?
        run_max, fall = -1.0, None
        for i in np.flatnonzero(ok):
            if p[i] > run_max:
                run_max, peak = p[i], o2[i]
            elif run_max - p[i] > FALLING and fall is None:
                fall = {"from_o2": float(peak), "peak_p": round(float(run_max), 3)}
        line["falls_with_oxygen"] = fall

    # same-fuel NASA tests, marked when their other inputs are close to the engineer's
    m = same_fuel_mask(pb.key, b["X"], pb.features, x)
    other = [i for i in dom.cols if i != j]
    sc = dom.scale[[dom.cols.index(i) for i in other]]
    tests = []
    for i in np.flatnonzero(m):
        d_other = float(np.sqrt((((b["X"][i, other] - x[other]) / sc) ** 2).sum()))
        tests.append({"code": b["ids"][i], "o2_pct": round(float(b["X"][i, j]), 2), "burned": int(b["y"][i]),
                      "near_settings": d_other <= 1.0})
    return {"points": points, "line": line, "tests": tests,
            "estimated_spans": _segments(o2, ok), "held": [pb.feature_labels[f] for f in pb.features if f != "o2_pct"]}


def next_tests(pb, b: dict, dom, x: np.ndarray, k: int = 3) -> list[dict]:
    X = b["X"]
    same = same_fuel_mask(pb.key, X, pb.features, x)
    # vary oxygen, pressure and leak / drop size; the rest of the air (CO₂, helium) stays as entered
    cont = [i for i in dom.cols if pb.features[i] in ("o2_pct", "psi", "fuel_flow", "d0_mm")]
    axes = [np.linspace(X[:, i].min(), X[:, i].max(), GRID) for i in cont]       # what the hardware has done
    C = np.tile(x, (GRID ** len(cont), 1))
    for n, combo in enumerate(itertools.product(*axes)):
        C[n, cont] = combo
    F = np.array([mdl.predict_proba(C)[:, 1] for mdl in b["boot_models"]])
    disagree = F.max(0) - F.min(0)
    Xs = X[same] if same.any() else X
    nearest = np.array([dom.dist(c, Xs).min() for c in C])
    novelty = np.minimum(nearest / dom.inside, 2.0)
    from_you = dom.dist(x, C)
    score = (disagree + 0.25 * novelty) * np.exp(-from_you / 2)
    picked: list[int] = []
    for i in np.argsort(-score):
        if all(dom.dist(C[i], C[q][None])[0] > 1.0 for q in picked):
            picked.append(int(i))
        if len(picked) == k:
            break
    out = []
    for i in picked:
        d = dom.dist(C[i], Xs)
        ni = int(np.flatnonzero(same)[np.argmin(d)]) if same.any() else int(np.argmin(d))
        out.append({
            "inputs": {pb.features[c]: round(float(C[i, c]), 2) for c in cont},
            "labels": {pb.features[c]: pb.feature_labels[pb.features[c]] for c in cont},
            "units": {pb.features[c]: pb.units[pb.features[c]] for c in cont},
            "committee_low": round(float(F[:, i].min()), 3), "committee_high": round(float(F[:, i].max()), 3),
            "nearest_test": b["ids"][ni], "nearest_burned": int(b["y"][ni]), "nearest_distance": round(float(d.min()), 2),
            "why": (f"The five models disagree here: {F[:, i].min() * 100:.0f}–{F[:, i].max() * 100:.0f} % chance. "
                    f"The nearest test of this fuel ({b['ids'][ni]}) is {float(d.min()):.1f} spread-units away."),
        })
    return out
