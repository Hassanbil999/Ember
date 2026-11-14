"""Train and validate the fire-check models (`python -m backend.ingest predict`).

Validation: GroupKFold by NASA test campaign. A whole campaign is hidden while the model trains, then
predicted, so the score answers "does this work on an experiment it has never seen?". Random splits put
near-repeats of a test in training and overstate skill (on FLEX, k-nearest-neighbour AUC 0.89 random vs
0.71 grouped), so they are not used.

Candidates: logistic regression, random forest, Gaussian process (ARD kernel, as in the old site) and,
for the measured quantities, the same families as regressors. The baseline ignores the conditions and
always predicts the training average. A classifier is usable only if it beats that baseline on BOTH the
Brier score and log loss (the probabilities, not just the ranking); among usable ones the lowest log loss
wins. A regressor is usable only if its mean absolute error beats the baseline's. If nothing beats the
baseline, no estimate is ever shown for that question: the app shows the nearest real tests instead.

Uncertainty: the chosen model is refitted on 15 campaign-bootstrap samples (whole NASA campaigns drawn
with replacement, since tests inside one campaign are not independent); the 10th–90th percentile of
their predictions is the range shown. This is wider than the old 5-fold spread and reflects how much the
answer depends on which campaigns NASA happened to run. Calibration (predicted vs observed rate on
unseen campaigns, in five bins) is stored with the model so a reader can see whether "30 %" means 30 %. For measured quantities the 90 % range is split-conformal: the
90th percentile of the absolute errors on unseen campaigns, so its coverage is checked, not assumed.
"""
from __future__ import annotations

import json
import time
import warnings

import joblib
import numpy as np
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
from sklearn.gaussian_process import GaussianProcessClassifier, GaussianProcessRegressor
from sklearn.gaussian_process.kernels import RBF, ConstantKernel, WhiteKernel
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import brier_score_loss, log_loss, mean_absolute_error, roc_auc_score
from sklearn.model_selection import GroupKFold
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from ..core.config import ARTIFACTS
from .problems import PROBLEMS, Problem

warnings.filterwarnings("ignore")
OUT = ARTIFACTS / "predict"
OUT.mkdir(parents=True, exist_ok=True)
FOLDS = 5
BOOT = 15


def _classifiers(d: int) -> dict:
    return {
        "logistic regression": lambda: make_pipeline(StandardScaler(), LogisticRegression(max_iter=5000)),
        "random forest": lambda: RandomForestClassifier(n_estimators=400, min_samples_leaf=3, random_state=0, n_jobs=-1),
        "Gaussian process": lambda: make_pipeline(StandardScaler(), GaussianProcessClassifier(
            ConstantKernel(1.0, (1e-2, 1e2)) * RBF(np.ones(d), (0.05, 50)), random_state=0)),
    }


def _regressors(d: int) -> dict:
    return {
        "random forest": lambda: RandomForestRegressor(n_estimators=400, min_samples_leaf=3, random_state=0, n_jobs=-1),
        "Gaussian process": lambda: make_pipeline(StandardScaler(), GaussianProcessRegressor(
            ConstantKernel(1.0, (1e-2, 1e2)) * RBF(np.ones(d), (0.05, 50)) + WhiteKernel(0.05, (1e-5, 1.0)),
            normalize_y=True, random_state=0)),
    }


def _splits(X, y, groups):
    n = min(FOLDS, len(set(groups)))
    return list(GroupKFold(n_splits=n).split(X, y, groups))


def _clf_scores(y, p) -> dict:
    p = np.clip(p, 1e-3, 1 - 1e-3)
    return {"auc": round(float(roc_auc_score(y, p)), 3) if len(set(y)) > 1 else None,
            "brier": round(float(brier_score_loss(y, p)), 4), "log_loss": round(float(log_loss(y, p)), 4),
            "accuracy": round(float(((p > 0.5) == y).mean()), 3)}


def _calibration(y, p, bins: int = 5) -> list[dict]:
    """Unseen-campaign predictions split into equal-count bins: mean predicted chance vs observed share."""
    order = np.argsort(p)
    out = []
    for chunk in np.array_split(order, bins):
        if len(chunk):
            out.append({"n": int(len(chunk)), "predicted": round(float(p[chunk].mean()), 3), "observed": round(float(y[chunk].mean()), 3)})
    return out


def _campaign_bootstrap(mk, X, y, groups, n: int = BOOT, seed: int = 0) -> list:
    rng = np.random.default_rng(seed)
    camps = np.array(sorted(set(groups)))
    models = []
    while len(models) < n:
        pick = rng.choice(camps, size=len(camps), replace=True)
        idx = np.concatenate([np.flatnonzero(groups == c) for c in pick])
        if len(set(y[idx])) < 2:
            continue
        models.append(mk().fit(X[idx], y[idx]))
    return models


def train_classifier(pb: Problem) -> tuple[dict, dict]:
    df = pb.frame()
    X, y = df[pb.features].to_numpy(float), df[pb.target].astype(int).to_numpy()
    groups = df.campaign.astype(str).to_numpy()
    splits = _splits(X, y, groups)
    base = np.zeros(len(y))
    for tr, te in splits:
        base[te] = y[tr].mean()
    table = [{"model": "baseline (always the average)", **_clf_scores(y, base), "auc": 0.5}]
    oof_by = {}
    for name, mk in _classifiers(X.shape[1]).items():
        oof = np.zeros(len(y))
        for tr, te in splits:
            oof[te] = mk().fit(X[tr], y[tr]).predict_proba(X[te])[:, 1] if len(set(y[tr])) > 1 else y[tr].mean()
        oof_by[name] = oof
        s = _clf_scores(y, oof)
        s["beats_baseline"] = s["brier"] < table[0]["brier"] and s["log_loss"] < table[0]["log_loss"]
        table.append({"model": name, **s})
    usable = [r for r in table[1:] if r["beats_baseline"]]
    chosen = min(usable, key=lambda r: r["log_loss"])["model"] if usable else None
    bundle = {"problem": pb.key, "kind": "classifier", "features": pb.features, "X": X, "y": y,
              "ids": df.test_id.tolist(), "fuel": df.fuel_name.tolist(), "chosen": chosen}
    if chosen:
        mk = _classifiers(X.shape[1])[chosen]
        bundle["model"] = mk().fit(X, y)
        bundle["boot_models"] = _campaign_bootstrap(mk, X, y, groups)
    card = {"question": pb.question, "target": pb.target, "investigation": pb.investigation, "psi_id": pb.psi_id,
            "n_tests": int(len(y)), "n_yes": int(y.sum()), "outcome_yes": pb.outcome_yes, "outcome_no": pb.outcome_no,
            "n_campaigns": int(len(set(groups))), "validation": f"GroupKFold by campaign, {len(splits)} folds",
            "comparison": table, "chosen": chosen, "features": pb.features}
    if chosen:
        best = next(r for r in table if r["model"] == chosen)
        card["skill_vs_baseline"] = round(1 - best["brier"] / table[0]["brier"], 3)
        card["calibration"] = _calibration(y, np.clip(oof_by[chosen], 1e-3, 1 - 1e-3))
        card["range_method"] = f"10th–90th percentile of {BOOT} models refitted on campaign-bootstrap samples"
    return bundle, card


def train_regressor(pb: Problem, target: str, spec: dict) -> tuple[dict, dict]:
    df = pb.frame(target)
    for k, v in (spec.get("only_when") or {}).items():
        df = df[df[k] == v]
    X, y = df[pb.features].to_numpy(float), df[target].astype(float).to_numpy()
    groups = df.campaign.astype(str).to_numpy()
    splits = _splits(X, y, groups)
    base = np.zeros(len(y))
    for tr, te in splits:
        base[te] = y[tr].mean()
    table = [{"model": "baseline (always the average)", "mae": round(float(mean_absolute_error(y, base)), 4)}]
    resid = {}
    for name, mk in _regressors(X.shape[1]).items():
        oof = np.zeros(len(y))
        for tr, te in splits:
            oof[te] = mk().fit(X[tr], y[tr]).predict(X[te])
        mae = float(mean_absolute_error(y, oof))
        resid[name] = np.abs(y - oof)
        table.append({"model": name, "mae": round(mae, 4), "beats_baseline": mae < table[0]["mae"]})
    usable = [r for r in table[1:] if r["beats_baseline"]]
    chosen = min(usable, key=lambda r: r["mae"])["model"] if usable else None
    bundle = {"target": target, "chosen": chosen, "n": int(len(y))}
    card = {"target": target, "label": spec["label"], "unit": spec["unit"], "meaning": spec["meaning"], "n_tests": int(len(y)),
            "validation": f"GroupKFold by campaign, {len(splits)} folds", "comparison": table, "chosen": chosen}
    if chosen:
        q90 = float(np.quantile(resid[chosen], 0.9))
        bundle["model"] = _regressors(X.shape[1])[chosen]().fit(X, y)
        bundle["q90"] = q90
        card["interval90_half_width"] = round(q90, 4)
        card["interval90_coverage_on_unseen"] = round(float((resid[chosen] <= q90).mean()), 3)
    return bundle, card


def run() -> dict:
    t0 = time.time()
    summary = {}
    for key, pb in PROBLEMS.items():
        bundle, card = train_classifier(pb)
        card["regressions"] = {}
        bundle["regressions"] = {}
        for target, spec in pb.regressions.items():
            rb, rc = train_regressor(pb, target, spec)
            bundle["regressions"][target] = rb
            card["regressions"][target] = rc
        card["trained_seconds"] = round(time.time() - t0, 1)
        bundle["card"] = card
        joblib.dump(bundle, OUT / f"{key}.joblib")
        (OUT / f"{key}.card.json").write_text(json.dumps(card, indent=1), encoding="utf-8")
        best = next((r for r in card["comparison"] if r["model"] == card["chosen"]), None)
        summary[key] = {"tests": card["n_tests"], "chosen": card["chosen"],
                        "auc": best and best["auc"], "brier": best and best["brier"],
                        "baseline_brier": card["comparison"][0]["brier"],
                        "regressions": {k: v["chosen"] for k, v in card["regressions"].items()}}
    from . import service
    service.clear()
    return summary
