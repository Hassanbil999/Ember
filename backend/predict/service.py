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
from . import explore
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
    meta.cache_clear()
    from . import pipeline  # imported here: pipeline itself uses this module
    pipeline.build.cache_clear()


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


NOT_IN_DATA = {
    "gas": "Airflow is not an input: CFI-G records no surrounding airflow, only the fuel jet.",
    "droplet": "Airflow is not an input: every FLEX drop here burned in still air (no imposed flow).",
}


def _ranges(df: pd.DataFrame, features: list[str]) -> dict:
    return {f: [round(float(df[f].min()), 3), round(float(df[f].max()), 3)]
            for f in features if f not in ("carbon_n", "heptane", "fuel_share")}


@lru_cache(maxsize=1)          # the same answer until the models are retrained (clear() resets it)
def meta() -> dict:
    out = {}
    for key, pb in PROBLEMS.items():
        b = _bundle(key)
        df = pb.frame()
        fuels = sorted(df.fuel.unique().tolist())
        out[key] = {"label": pb.label, "question": pb.question, "fuels": fuels, "ranges": _ranges(df, pb.features),
                    "ranges_by_fuel": {f: _ranges(df[df.fuel == f], pb.features) for f in fuels},
                    # for the Statistics coverage chart and the page labels
                    "points": [{"id": r.test_id, "fuel": r.fuel, "o2_pct": round(float(r.o2_pct), 2), "psi": round(float(r.psi), 2),
                                "burned": int(getattr(r, pb.target))} for r in df.itertuples()],
                    "features": [{"key": f, "label": pb.feature_labels[f], "unit": pb.units[f]} for f in pb.features],
                    "investigation": pb.investigation, "psi_id": pb.psi_id, "dataset": DATASETS[key],
                    "not_in_data": NOT_IN_DATA[key], "outcome_yes": pb.outcome_yes, "outcome_no": pb.outcome_no, "card": b["card"]}
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
                     "baseline_brier": card["comparison"][0]["brier"], "investigation": pb.investigation, "psi_id": pb.psi_id,
                     "skill": card.get("skill_vs_baseline"), "calibration": card.get("calibration", []), "range_method": card.get("range_method"),
                     },
           "not_in_data": NOT_IN_DATA[key], "suggestion": None}
    # where is the line, and which test would teach the models most (computed in every zone: an untested
    # request is exactly where a next test matters). Model chances on the line appear only where allowed.
    res["oxygen_line"], res["next_tests"] = None, []
    if card["chosen"] and b.get("boot_models"):
        res["oxygen_line"] = explore.oxygen_line(pb, b, dom, x, g)
        res["next_tests"] = explore.next_tests(pb, b, dom, x)
    close = [r for r in res["nearest"] if r["close"]] if a["zone"] != "untested" else []
    if close:
        k = sum(r["burned"] for r in close)
        res["tested"] = {"n": len(close), "yes": k, "outcome_yes": pb.outcome_yes, "outcome_no": pb.outcome_no}
    if a["zone"] == "untested" and a["idx"] and g <= 0.02:
        res["suggestion"] = _suggest(pb, b, a["idx"][0])
    if a["zone"] == "untested" or not card["chosen"]:
        if not card["chosen"]:
            res["reasons"].append("No model beat the 'always the average' baseline on unseen campaigns, so none is used.")
        return res
    boots = _prob(b["boot_models"], x[None])
    drivers, p = _drivers(pb, b, dom, x, a)
    lo, hi = np.percentile(boots, [10, 90])
    res["estimate"] = {"probability": round(p, 3), "low": round(float(min(lo, p)), 3), "high": round(float(max(hi, p)), 3),
                       "outcome_yes": pb.outcome_yes, "outcome_no": pb.outcome_no, "will": pb.will, "model": card["chosen"]}
    res["drivers"] = drivers
    if res["tested"]:
        share = res["tested"]["yes"] / res["tested"]["n"]
        res["tested"]["agrees"] = (share >= 0.5) == (p >= 0.5)
    for target, rb in b["regressions"].items():
        rc = card["regressions"][target]
        if not rb.get("chosen"):
            continue
        if (pb.regressions[target].get("only_when") or {}).get("burned") == 0 and p >= 0.5:
            continue          # a quantity measured only when the flame goes out is not shown when it most likely stays lit
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
        co2, he = float(req.get("co2_pct") or 0), float(req.get("he_pct") or 0)
        n2 = max(0.0, 100 - float(req["o2_pct"]) - co2 - he)
        rows.append({"label": "Rest of the air", "value": f"{n2:g} % nitrogen" + (f", {co2:g} % CO₂" if co2 else "") + (f", {he:g} % helium" if he else "")})
    rows.append({"label": "Gravity", "value": "microgravity" if float(req.get("gravity_g", 0)) <= 0.02 else f"{float(req['gravity_g']):.3g} g"})
    return rows


def _suggest(pb, b, i: int) -> dict:
    """The conditions of the nearest real test of the same fuel, as inputs the engineer can load."""
    r = _test_row(b["ids"][i])
    sug = {"code": b["ids"][i], "fuel": r["fuel"], "o2_pct": round(float(r["o2_frac"]) * 100, 2), "psi": round(float(r["pressure_kpa"]) / PSI, 2)}
    if pb.key == "gas":
        sug["fuel_flow"] = round(float(r["fuel_flow_mg_s"]), 3)
    else:
        sug["d0_mm"] = round(float(r["d0_mm"]), 2)
        sug["co2_pct"] = round(float(r["co2_frac"] or 0) * 100, 1) if pd.notna(r["co2_frac"]) else 0.0
        sug["he_pct"] = round(float(r["he_frac"] or 0) * 100, 1) if pd.notna(r["he_frac"]) else 0.0
    return sug


def _reference(key: str, req: dict) -> dict | None:
    if key != "gas":
        return None
    ref = reference()["earth_limiting_oxygen"]
    parts = gas_fuel_parts(req["fuel"])
    v = ref["values"].get(parts[0]) if parts else None
    return {"meaning": ref["meaning"].strip(), "source": ref["source"], "note": ref["conditions_note"],
            "fuel": parts[0] if parts else req["fuel"], "values": v, "missing": None if v else ref["missing_note"]}
