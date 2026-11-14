"""One fire check: zone, estimate (only where allowed), nearest NASA tests, what moves the estimate."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import yaml

from ..core.config import CONFIG, PROCESSED
from ..core.store import get_store
from .domain import Domain
from .problems import DATASETS, PROBLEMS, PSI, features_from, gas_fuel_parts
from .train import OUT

ZONE_TEXT = {
    "tested": "NASA ran tests at nearly these conditions. Their measured outcomes are the answer; the model is a cross-check.",
    "estimated": "No NASA test at exactly these conditions, but tests of this fuel surround them. The model estimates from the patterns it learned.",
    "untested": "Outside what NASA tested for this fuel. The model gives no number here.",
}


def clear():
    _bundle.cache_clear()
    _domain.cache_clear()
    _links.cache_clear()


@lru_cache(maxsize=4)
def _bundle(key: str) -> dict:
    p = OUT / f"{key}.joblib"
    if not p.exists():
        raise FileNotFoundError(f"Fire-check model {key!r} is not trained; run `python -m backend.ingest predict`.")
    return joblib.load(p)


@lru_cache(maxsize=4)
def _domain(key: str) -> Domain:
    b = _bundle(key)
    return Domain(key, b["X"], b["features"])


@lru_cache(maxsize=1)
def _links() -> dict:
    """test code -> catalog resource id (for 'open in Find data')."""
    f = PROCESSED / "atlas_test_points.parquet"
    if not Path(f).exists():
        return {}
    tp = pd.read_parquet(f, columns=["code", "source_resource_id"])
    return dict(zip(tp.code, tp.source_resource_id))


@lru_cache(maxsize=1)
def reference() -> dict:
    return yaml.safe_load((CONFIG / "outside_reference.yaml").read_text(encoding="utf-8"))


def available() -> bool:
    return all((OUT / f"{k}.joblib").exists() for k in PROBLEMS)


def meta() -> dict:
    out = {}
    for key, pb in PROBLEMS.items():
        b = _bundle(key)
        df = pb.frame()
        fuels = sorted(df.fuel.unique().tolist())
        cont = [f for f in pb.features if f not in ("carbon_n", "heptane", "fuel_share")]
        span = lambda d, f: [round(float(d[f].min()), 3), round(float(d[f].max()), 3)]  # noqa: E731
        ranges = {f: span(df, f) for f in cont}
        # The domain check compares a request with tests of the SAME fuel, so the hints must too.
        by_fuel = {fu: {f: span(g, f) for f in cont} for fu, g in df.groupby("fuel")}
        points = [{"id": r.test_id, "fuel": r.fuel, "o2_pct": round(float(r.o2_pct), 2), "psi": round(float(r.psi), 2),
                   "burned": int(getattr(r, pb.target))} for r in df.itertuples()]
        features = [{"key": f, "label": pb.feature_labels[f], "unit": pb.units[f]} for f in pb.features]
        out[key] = {"label": pb.label, "question": pb.question, "fuels": fuels, "ranges": ranges, "ranges_by_fuel": by_fuel,
                    "points": points, "features": features, "investigation": pb.investigation, "psi_id": pb.psi_id, "dataset": DATASETS[key],
                    "outcome_yes": pb.outcome_yes, "outcome_no": pb.outcome_no, "card": b["card"]}
    return out


def _test_row(code: str) -> dict:
    t = get_store().tests
    r = t.loc[code] if code in t.index else t[t.test_id == code].iloc[0]
    return r


def _nearest(pb, b, dom: Domain, x: np.ndarray, a: dict, n: int = 6) -> list[dict]:
    idx, dist = a["idx"], a["dist"]
    if not idx:          # fuel not tested: nearest of any fuel, flagged
        d = dom.dist(x, b["X"])
        idx = np.argsort(d).tolist()
        dist = d[idx].tolist()
    links = _links()
    rows = []
    for i, d in list(zip(idx, dist))[:n]:
        code = b["ids"][i]
        r = _test_row(code)
        row = {"code": code, "dataset": r["dataset"], "source_row": int(r["_row"]) if pd.notna(r.get("_row")) else None,
               "resource_id": links.get(code), "fuel": r["fuel"], "o2_pct": round(float(r["o2_frac"]) * 100, 2),
               "psi": round(float(r["pressure_kpa"]) / PSI, 2), "pressure_kpa": round(float(r["pressure_kpa"]), 1),
               "outcome": pb.outcome_yes if int(b["y"][i]) == 1 else pb.outcome_no, "burned": int(b["y"][i]),
               "distance": round(float(d), 2), "close": bool(d <= dom.close)}
        if pb.key == "gas":
            row["fuel_flow"] = round(float(r["fuel_flow_mg_s"]), 3)
        else:
            row["d0_mm"] = round(float(r["d0_mm"]), 2)
            row["diluent"] = r.get("diluent")
        rows.append(row)
    return rows


def _prob(models, x) -> np.ndarray:
    return np.array([m.predict_proba(x)[0, 1] for m in models])


def _drivers(pb, b, dom: Domain, x: np.ndarray, a: dict) -> list[dict]:
    m = b["model"]
    Xs = b["X"][a["idx"]] if a["idx"] else b["X"]
    p0 = float(m.predict_proba(x[None])[0, 1])
    out = []
    for i, f in enumerate(pb.features):
        if f in ("carbon_n", "heptane", "fuel_share", "co2_pct", "he_pct"):
            continue
        lo, hi = Xs[:, i].min(), Xs[:, i].max()
        step = float(f"{0.1 * (hi - lo):.1g}")
        if step <= 0:
            continue
        up, dn = x.copy(), x.copy()
        up[i], dn[i] = min(x[i] + step, hi), max(x[i] - step, lo)
        if up[i] == dn[i]:
            continue
        slope = (m.predict_proba(up[None])[0, 1] - m.predict_proba(dn[None])[0, 1]) / (up[i] - dn[i])
        out.append({"input": f, "label": pb.feature_labels[f], "step": round(float(step), 3), "unit": pb.units[f],
                    "change_pts": round(float(slope * step * 100), 1)})
    out.sort(key=lambda r: -abs(r["change_pts"]))
    return out, p0


def check(req: dict) -> dict:
    key = req["problem"]
    if key not in PROBLEMS:
        raise ValueError("problem must be 'gas' or 'droplet'")
    pb, b, dom = PROBLEMS[key], _bundle(key), _domain(key)
    x = features_from(pb, req)[0]
    g = float(req.get("gravity_g", 0.0))
    a = dom.assess(x, g, pb.feature_labels, pb.units)
    card = b["card"]
    best = next((r for r in card["comparison"] if r["model"] == card["chosen"]), None)
    res = {"problem": key, "label": pb.label, "question": pb.question, "inputs": _echo(pb, req, x),
           "zone": a["zone"], "zone_text": ZONE_TEXT[a["zone"]], "reasons": a["reasons"],
           "nearest": _nearest(pb, b, dom, x, a), "estimate": None, "quantities": [], "drivers": [],
           "tested": None, "reference": _reference(key, req),
           "model": {"chosen": card["chosen"], "n_tests": card["n_tests"], "n_campaigns": card["n_campaigns"],
                     "validation": card["validation"], "comparison": card["comparison"],
                     "auc": best and best["auc"], "brier": best and best["brier"],
                     "baseline_brier": card["comparison"][0]["brier"], "investigation": pb.investigation, "psi_id": pb.psi_id}}
    close = [r for r in res["nearest"] if r["close"]] if a["zone"] != "untested" else []
    if close:
        k = sum(r["burned"] for r in close)
        res["tested"] = {"n": len(close), "yes": k, "outcome_yes": pb.outcome_yes, "outcome_no": pb.outcome_no}
    if a["zone"] == "untested" or not card["chosen"]:
        if not card["chosen"]:
            res["reasons"].append("No model beat the 'always the average' baseline on unseen campaigns, so none is used.")
        return res
    folds = _prob(b["fold_models"], x[None])
    drivers, p = _drivers(pb, b, dom, x, a)
    # The range is the spread of the five fold models; it is widened to include the full-data model's own
    # estimate, so the number shown never sits outside the range shown with it (README Decision AH).
    res["estimate"] = {"probability": round(p, 3), "low": round(float(min(folds.min(), p)), 3), "high": round(float(max(folds.max(), p)), 3),
                       "outcome_yes": pb.outcome_yes, "outcome_no": pb.outcome_no, "will": pb.will, "model": card["chosen"]}
    res["drivers"] = drivers
    if res["tested"]:
        share = res["tested"]["yes"] / res["tested"]["n"]
        res["tested"]["agrees"] = (share >= 0.5) == (p >= 0.5)
    for target, rb in b["regressions"].items():
        rc = card["regressions"][target]
        if not rb.get("chosen"):
            continue
        if target == "extinction_d_mm" and p >= 0.5:
            continue
        v = float(rb["model"].predict(x[None])[0])
        q = rb["q90"]
        res["quantities"].append({"label": rc["label"], "unit": rc["unit"], "meaning": rc["meaning"], "value": round(v, 3),
                                  "low": round(max(0.0, v - q), 3), "high": round(v + q, 3), "model": rb["chosen"],
                                  "coverage": rc["interval90_coverage_on_unseen"], "n_tests": rc["n_tests"]})
    return res


def _echo(pb, req: dict, x: np.ndarray) -> list[dict]:
    rows = [{"label": "Fuel", "value": req["fuel"]},
            {"label": "Oxygen", "value": f"{req['o2_pct']:g} %"},
            {"label": "Pressure", "value": f"{req['psi']:g} psi ({req['psi'] * PSI:.0f} kPa)"}]
    if pb.key == "gas":
        rows.append({"label": "Fuel flow (leak size)", "value": f"{req['fuel_flow']:g} mg/s"})
    else:
        rows.append({"label": "Drop size", "value": f"{req['d0_mm']:g} mm"})
        rows.append({"label": "Rest of the air", "value": {"N2": "nitrogen", "CO2": "carbon dioxide", "He": "helium"}.get(req.get("diluent", "N2"), "nitrogen")})
    rows.append({"label": "Gravity", "value": "microgravity" if float(req.get("gravity_g", 0)) <= 0.02 else f"{float(req['gravity_g']):.3g} g"})
    return rows


def _reference(key: str, req: dict) -> dict | None:
    if key != "gas":
        return None
    ref = reference()["earth_limiting_oxygen"]
    parts = gas_fuel_parts(req["fuel"])
    v = ref["values"].get(parts[0]) if parts else None
    return {"meaning": ref["meaning"].strip(), "source": ref["source"], "note": ref["conditions_note"],
            "fuel": parts[0] if parts else req["fuel"], "values": v, "missing": None if v else ref["missing_note"]}
