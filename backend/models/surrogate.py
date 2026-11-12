"""Data-driven surrogates (not physics simulators), defined per dataset in config/models.yaml.

* GP classifier for burn vs extinction, GP regressors for rates (with predictive std).
* Group-aware CV (GroupKFold by campaign), always compared with a naive baseline.
* Applicability domain: mean distance to k nearest training points in standardized
  feature space; thresholds from the training set's own leave-one-out distances.
* Partial gravity is always flagged as untested (no such data exists).
"""
from __future__ import annotations

import json
import time
import warnings

import joblib
import numpy as np
import pandas as pd
from sklearn.gaussian_process import GaussianProcessClassifier, GaussianProcessRegressor
from sklearn.gaussian_process.kernels import RBF, ConstantKernel, WhiteKernel
from sklearn.metrics import brier_score_loss, mean_absolute_error, r2_score, roc_auc_score
from sklearn.model_selection import GroupKFold

from ..core import config
from ..core.config import ARTIFACTS, PROCESSED

warnings.filterwarnings("ignore", category=UserWarning)
warnings.filterwarnings("ignore", module="sklearn")

MODEL_DIR = ARTIFACTS / "models"
MODEL_DIR.mkdir(parents=True, exist_ok=True)


class Encoder:
    def __init__(self, df: pd.DataFrame, features: list[str]):
        vm = config.variables()
        self.numeric = [f for f in features if vm.get(f, {}).get("kind") == "number"]
        self.categorical = [f for f in features if f not in self.numeric]
        self.mean = {f: float(df[f].mean()) for f in self.numeric}
        self.std = {f: float(df[f].std() or 1.0) or 1.0 for f in self.numeric}
        self.min = {f: float(df[f].min()) for f in self.numeric}
        self.max = {f: float(df[f].max()) for f in self.numeric}
        self.cats = {f: sorted(df[f].dropna().astype(str).unique().tolist()) for f in self.categorical}
        self.cat_weight = 0.7

    def columns(self):
        return self.numeric + [f"{f}={c}" for f in self.categorical for c in self.cats[f]]

    def transform(self, df: pd.DataFrame) -> np.ndarray:
        cols = []
        for f in self.numeric:
            v = pd.to_numeric(df[f], errors="coerce").fillna(self.mean[f]).values if f in df else np.full(len(df), self.mean[f])
            cols.append((v - self.mean[f]) / self.std[f])
        for f in self.categorical:
            vals = df[f].astype(str).values if f in df else np.array([""] * len(df))
            for c in self.cats[f]:
                cols.append((vals == c).astype(float) * self.cat_weight)
        return np.column_stack(cols) if cols else np.zeros((len(df), 0))


def _kernel(d: int, classifier: bool):
    k = ConstantKernel(1.0, (1e-2, 1e2)) * RBF(length_scale=np.ones(d), length_scale_bounds=(0.05, 50))
    return k if classifier else k + WhiteKernel(0.05, (1e-5, 1.0))


def _fit(kind: str, X, y):
    if kind == "gp_classifier":
        m = GaussianProcessClassifier(kernel=_kernel(X.shape[1], True), random_state=0, n_restarts_optimizer=0)
    else:
        m = GaussianProcessRegressor(kernel=_kernel(X.shape[1], False), normalize_y=True, random_state=0,
                                     n_restarts_optimizer=0)
    return m.fit(X, y)


def _training_frame(mid: str, cfg: dict) -> pd.DataFrame:
    t = pd.read_parquet(PROCESSED / "tests.parquet")
    t = t[(t.dataset == cfg["dataset"]) & (~t.excluded)]
    for k, v in (cfg.get("only_when") or {}).items():
        t = t[t[k] == v]
    t = t.dropna(subset=[cfg["target"]] + [f for f in cfg["features"]])
    return t


def train_one(mid: str, cfg: dict, ad_cfg: dict) -> dict:
    t0 = time.time()
    df = _training_frame(mid, cfg)
    enc = Encoder(df, cfg["features"])
    X = enc.transform(df)
    clf = cfg["type"] == "gp_classifier"
    y = df[cfg["target"]].astype(int if clf else float).values
    groups = df[cfg.get("group", "campaign")].astype(str).values
    n_groups = len(set(groups))
    cv = {"scheme": f"GroupKFold by {cfg.get('group', 'campaign')} ({min(5, n_groups)} folds, {n_groups} groups)"}
    oof = np.full(len(y), np.nan)
    oof_std = np.full(len(y), np.nan)
    base = np.full(len(y), np.nan)
    if n_groups >= 2:
        for tr, te in GroupKFold(n_splits=min(5, n_groups)).split(X, y, groups):
            if clf and len(set(y[tr])) < 2:
                continue
            m = _fit(cfg["type"], X[tr], y[tr])
            if clf:
                oof[te] = m.predict_proba(X[te])[:, 1]
                base[te] = y[tr].mean()
            else:
                mu, sd = m.predict(X[te], return_std=True)
                oof[te], oof_std[te] = mu, sd
                base[te] = y[tr].mean()
    ok = ~np.isnan(oof)
    if clf:
        cv["metrics"] = {
            "accuracy": float(((oof[ok] > 0.5) == y[ok]).mean()),
            "brier": float(brier_score_loss(y[ok], oof[ok])),
            "auc": float(roc_auc_score(y[ok], oof[ok])) if len(set(y[ok])) > 1 else None,
        }
        cv["baseline"] = {
            "name": "majority class / base rate",
            "accuracy": float(((base[ok] > 0.5) == y[ok]).mean()),
            "brier": float(brier_score_loss(y[ok], base[ok])),
            "auc": 0.5,
        }
        cv["better_than_baseline"] = cv["metrics"]["brier"] < cv["baseline"]["brier"]
    else:
        cover = np.abs(y[ok] - oof[ok]) <= 1.645 * oof_std[ok]
        cv["metrics"] = {"mae": float(mean_absolute_error(y[ok], oof[ok])), "r2": float(r2_score(y[ok], oof[ok])),
                         "interval90_coverage": float(cover.mean())}
        cv["baseline"] = {"name": "training mean", "mae": float(mean_absolute_error(y[ok], base[ok])),
                          "r2": float(r2_score(y[ok], base[ok]))}
        cv["better_than_baseline"] = cv["metrics"]["mae"] < cv["baseline"]["mae"]
    cv["n_scored"] = int(ok.sum())

    model = _fit(cfg["type"], X, y)
    # applicability domain
    k = min(ad_cfg.get("k_neighbors", 5), len(X) - 1)
    D = np.sqrt(((X[:, None, :] - X[None, :, :]) ** 2).sum(-1))
    np.fill_diagonal(D, np.inf)
    loo = np.sort(D, axis=1)[:, :k].mean(1)
    inside = float(np.percentile(loo, ad_cfg.get("inside_percentile", 95)))
    edge = inside * ad_cfg.get("edge_multiplier", 2.0)

    kern = str(model.kernel_)
    card = {
        "id": mid, "label": cfg["label"], "dataset": cfg["dataset"], "type": cfg["type"], "target": cfg["target"],
        "features": cfg["features"], "encoded_columns": enc.columns(), "rows": int(len(df)),
        "only_when": cfg.get("only_when"), "kernel": kern, "cv": cv,
        "applicability": {"k": k, "inside": inside, "edge": edge, "metric": "mean distance to k nearest training points, standardized units"},
        "ranges": {f: [enc.min[f], enc.max[f]] for f in enc.numeric},
        "categories": enc.cats,
        "limits": [
            "Learned only from the loaded data" + (" (a synthetic demo fixture)." if config.datasets()[cfg["dataset"]].get("demo") else "."),
            "Not a physics model: it interpolates measured outcomes and cannot extrapolate physics.",
            "No partial-gravity data exist; any partial-gravity scenario is untested by construction.",
        ] + (["All training tests are microgravity droplets with no imposed flow; flow and gravity sliders do not change this model."]
             if cfg["dataset"] == "flex" else []),
        "trained_seconds": round(time.time() - t0, 2), "demo": bool(config.datasets()[cfg["dataset"]].get("demo")),
    }
    joblib.dump({"model": model, "enc": enc, "X": X, "y": y, "ids": df["test_id"].tolist(), "card": card,
                 "cfg": cfg}, MODEL_DIR / f"{mid}.joblib")
    (MODEL_DIR / f"{mid}.card.json").write_text(json.dumps(card, indent=1, default=float), encoding="utf-8")
    return card


def train_all() -> list[dict]:
    mc = config.models_cfg()
    cards = []
    for mid, cfg in mc["models"].items():
        card = train_one(mid, cfg, mc.get("applicability", {}))
        m = card["cv"]["metrics"]
        print(f"model {mid}: rows={card['rows']} {m} better_than_baseline={card['cv']['better_than_baseline']}")
        cards.append(card)
    _cache.clear()
    return cards


# ------------------------------------------------------------------ inference
_cache: dict = {}


def load(mid: str) -> dict:
    if mid not in _cache:
        _cache[mid] = joblib.load(MODEL_DIR / f"{mid}.joblib")
    return _cache[mid]


def clear_cache():
    _cache.clear()


def _predict_raw(b: dict, X: np.ndarray):
    m = b["model"]
    if b["card"]["type"] == "gp_classifier":
        return m.predict_proba(X)[:, 1], None
    mu, sd = m.predict(X, return_std=True)
    return mu, sd


def domain(b: dict, x: np.ndarray, scenario: dict) -> dict:
    X = b["X"]
    d = np.sqrt(((X - x) ** 2).sum(1))
    k = b["card"]["applicability"]["k"]
    order = np.argsort(d)
    dist = float(d[order[:k]].mean())
    ad = b["card"]["applicability"]
    status = "inside" if dist <= ad["inside"] else ("edge" if dist <= ad["edge"] else "outside")
    notes = []
    g = scenario.get("gravity_g")
    feats = b["card"]["features"]
    if g is not None and 0.02 < float(g) < 0.95:
        status = "untested" if status != "outside" else "outside"
        notes.append("Partial gravity is untested: PSI has no partial-gravity combustion data. "
                     "Microgravity and 1g results can only bound this case.")
    if "gravity_g" not in feats and g is not None and float(g) > 0.02:
        notes.append("This model has only microgravity training data; the gravity setting is not modelled.")
        if float(g) >= 0.95:
            status = "outside"
    if "flow_cm_s" not in feats and scenario.get("flow_cm_s"):
        notes.append("Training tests had no imposed flow; flow is not a feature of this model.")
    for f, (lo, hi) in b["card"]["ranges"].items():
        v = scenario.get(f)
        if v is not None and (float(v) < lo or float(v) > hi):
            notes.append(f"{f} = {float(v):.3g} is outside the tested range [{lo:.3g}, {hi:.3g}].")
    return {"status": status, "distance": round(dist, 3), "inside": round(ad["inside"], 3), "edge": round(ad["edge"], 3),
            "nearest_idx": order[:12].tolist(), "nearest_d": [round(float(d[i]), 3) for i in order[:12]], "notes": notes}


def _row(scenario: dict, feats: list[str]) -> pd.DataFrame:
    return pd.DataFrame([{f: scenario.get(f) for f in feats}])


def predict(mid: str, scenario: dict, with_sensitivity: bool = True) -> dict:
    b = load(mid)
    card = b["card"]
    feats = card["features"]
    sc = dict(scenario)
    for f in feats:
        if sc.get(f) is None:
            sc[f] = b["enc"].cats[f][0] if f in b["enc"].categorical else b["enc"].mean[f]
    x = b["enc"].transform(_row(sc, feats))
    val, sd = _predict_raw(b, x)
    out = {"model": mid, "label": card["label"], "type": card["type"], "target": card["target"]}
    if card["type"] == "gp_classifier":
        p = float(val[0])
        out.update({"p": p, "outcome": "burns" if p >= 0.5 else "extinguishes",
                    "confidence": "high" if abs(p - 0.5) > 0.35 else ("moderate" if abs(p - 0.5) > 0.15 else "low")})
    else:
        mu, s = float(val[0]), float(sd[0])
        out.update({"mean": mu, "std": s, "lo": max(0.0, mu - 1.645 * s), "hi": mu + 1.645 * s,
                    "confidence": "high" if s / max(abs(mu), 1e-6) < 0.1 else ("moderate" if s / max(abs(mu), 1e-6) < 0.25 else "low")})
    dom = domain(b, x[0], scenario)
    out["domain"] = {k: v for k, v in dom.items() if k not in ("nearest_idx",)}
    out["nearest"] = [{"test_id": b["ids"][i], "distance": dd, "target": float(b["y"][i])}
                      for i, dd in zip(dom["nearest_idx"][:6], dom["nearest_d"][:6])]
    # partial gravity: bracket with µg and 1g if the model has gravity as a feature
    g = scenario.get("gravity_g")
    if g is not None and 0.02 < float(g) < 0.95 and "gravity_g" in feats:
        br = {}
        for gv in (0.0, 1.0):
            xb = b["enc"].transform(_row({**sc, "gravity_g": gv}, feats))
            vb, sb = _predict_raw(b, xb)
            br["µg" if gv == 0 else "1g"] = float(vb[0])
        out["bracket"] = br
    if with_sensitivity:
        sens = []
        base_v = float(val[0])
        for f in b["enc"].numeric:
            lo, hi = card["ranges"][f]
            step = (hi - lo) * 0.1 or 0.1
            vals = []
            for sgn in (-1, 1):
                xs = b["enc"].transform(_row({**sc, f: float(sc[f]) + sgn * step}, feats))
                vals.append(float(_predict_raw(b, xs)[0][0]))
            sens.append({"feature": f, "delta_minus": vals[0] - base_v, "delta_plus": vals[1] - base_v,
                         "step": step, "magnitude": max(abs(vals[0] - base_v), abs(vals[1] - base_v))})
        sens.sort(key=lambda s: -s["magnitude"])
        out["sensitivity"] = sens
    return out


def advisor(mid: str, target: dict, n: int = 5, base: dict | None = None) -> dict:
    """Suggest test conditions that most reduce uncertainty in a target region.

    Candidates are sampled inside the target box (O₂, pressure); other features are held at
    the user's scenario. Score = predictive variance (GP regressor) or Bernoulli variance
    p(1−p) (classifier), with greedy diversity so suggestions are not clustered."""
    b = load(mid)
    card = b["card"]
    feats = card["features"]
    rng = np.random.default_rng(0)
    base = dict(base or {})
    for f in feats:
        if base.get(f) is None:
            base[f] = b["enc"].cats[f][0] if f in b["enc"].categorical else b["enc"].mean[f]
    if "gravity_g" in feats:
        base["gravity_g"] = 0.0   # partial gravity is untestable in current hardware → nearest testable proxy
    o2 = target.get("o2_frac", [card["ranges"].get("o2_frac", [0.15, 0.4])[0], card["ranges"].get("o2_frac", [0.15, 0.4])[1]])
    pr = target.get("pressure_kpa", card["ranges"].get("pressure_kpa", [50, 150]))
    cands = []
    for _ in range(400):
        c = dict(base)
        c["o2_frac"] = float(rng.uniform(*o2))
        c["pressure_kpa"] = float(rng.uniform(*pr))
        if "flow_cm_s" in feats:
            c["flow_cm_s"] = float(np.exp(rng.uniform(np.log(0.5), np.log(40))))
        cands.append(c)
    df = pd.DataFrame(cands)
    X = b["enc"].transform(df[feats])
    val, sd = _predict_raw(b, X)
    score = val * (1 - val) if sd is None else sd ** 2
    D = np.sqrt(((X[:, None, :] - b["X"][None, :, :]) ** 2).sum(-1))
    nearest = np.sort(D, axis=1)[:, :3].mean(1)
    picks = []
    for i in np.argsort(-score):
        if all(np.linalg.norm(X[i] - X[j]) > 0.6 for j in picks):
            picks.append(int(i))
        if len(picks) >= n:
            break
    out = []
    for i in picks:
        c = cands[i]
        why = (f"predicted p(burn) = {val[i]:.2f} — the outcome here is least certain" if sd is None
               else f"predictive σ = {sd[i]:.3g} — largest uncertainty in the target region")
        out.append({"conditions": {k: c[k] for k in feats if k in c}, "score": float(score[i]),
                    "prediction": float(val[i]), "nearest_distance": float(nearest[i]),
                    "rationale": f"{why}; nearest existing test is {nearest[i]:.2f} σ away."})
    return {"model": mid, "criterion": "max predictive variance" if sd is not None else "max Bernoulli variance p(1−p)",
            "suggestions": out, "note": "Research aid, not a test plan. Gravity is held at microgravity, the nearest "
                                        "testable proxy; partial gravity itself remains untested."}


def replay(scenario: dict) -> dict:
    """Predicted droplet evolution from the K / burn / extinction-diameter surrogates."""
    pb = predict("droplet_burn", scenario, with_sensitivity=False)
    pk = predict("droplet_k", scenario, with_sensitivity=False)
    d0 = float(scenario.get("d0_mm") or 3.0)
    K = max(pk["mean"], 0.05)
    d_ext = None
    if pb["p"] < 0.5:
        pe = predict("droplet_dext", scenario, with_sensitivity=False)
        d_ext = float(np.clip(pe["mean"], 0.05, d0 * 0.95))
    t_end = (d0 ** 2 - (d_ext or 0) ** 2) / K
    ts = np.linspace(0, t_end, 60)
    d = np.sqrt(np.clip(d0 ** 2 - K * ts, 0, None))
    return {"t": ts.round(3).tolist(), "d_mm": d.round(4).tolist(), "K": K, "K_lo": pk["lo"], "K_hi": pk["hi"],
            "p_burn": pb["p"], "extinction_d_mm": d_ext, "n_tests": load("droplet_k")["card"]["rows"],
            "domain": pk["domain"], "label": f"replay predicted from {load('droplet_k')['card']['rows']} measured tests"}
