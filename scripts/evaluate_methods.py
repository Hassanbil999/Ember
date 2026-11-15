"""Reproduce every number in docs/methods/ with one command:

    python scripts/evaluate_methods.py          # writes docs/methods/results.md (about 2 minutes)

It reuses the app's own data frames and model families (backend/predict), so the documentation and the
Fire check cannot disagree. Sections:
  A  cleaning: what the validation rules flagged or excluded
  B  the models the app trains, and how stable their scores are over 10 different campaign splits
  B2 a ladder of baselines, from "always the average" to "look up the closest NASA tests"
  C  preprocessing choices tested (features, penalty, class weights, flagged rows, mixing data sets)
  D  checks on the main conclusion (significance, stability, coverage), no model involved
"""
from __future__ import annotations

import json
import sys
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from scipy.stats import fisher_exact  # noqa: E402
from sklearn.ensemble import RandomForestClassifier  # noqa: E402
from sklearn.gaussian_process import GaussianProcessClassifier  # noqa: E402
from sklearn.gaussian_process.kernels import RBF, ConstantKernel  # noqa: E402
from sklearn.linear_model import LogisticRegression  # noqa: E402
from sklearn.metrics import brier_score_loss, log_loss, roc_auc_score  # noqa: E402
from sklearn.pipeline import make_pipeline  # noqa: E402
from sklearn.preprocessing import StandardScaler  # noqa: E402

from backend.core.config import ARTIFACTS  # noqa: E402
from backend.core.store import get_store  # noqa: E402
from backend.predict.problems import PROBLEMS, gas_fuel_parts  # noqa: E402

OUT = ROOT / "docs" / "methods" / "results.md"
REPEATS, FOLDS = 10, 5
lines: list[str] = []


def w(s: str = "") -> None:
    print(s)
    lines.append(s)


# the app's three families (backend/predict/train.py), plus variants tested in section C
def LR(C=1.0, cw=None):
    return lambda d: make_pipeline(StandardScaler(), LogisticRegression(C=C, class_weight=cw, max_iter=5000))


def RF():
    return lambda d: RandomForestClassifier(n_estimators=400, min_samples_leaf=3, random_state=0, n_jobs=-1)


def GP():
    return lambda d: make_pipeline(StandardScaler(), GaussianProcessClassifier(
        ConstantKernel(1.0, (1e-2, 1e2)) * RBF(np.ones(d), (0.05, 50)), random_state=0))


def splits(groups, seed):
    """Whole campaigns go to the test side: shuffled differently for each repeat."""
    u = np.array(sorted(set(groups)))
    np.random.default_rng(seed).shuffle(u)
    for k in range(FOLDS):
        held = set(u[k::FOLDS])
        te = np.array([g in held for g in groups])
        yield np.where(~te)[0], np.where(te)[0]


def calib_slope(y, p):
    p = np.clip(p, 1e-4, 1 - 1e-4)
    return float(LogisticRegression(C=1e6).fit(np.log(p / (1 - p))[:, None], y).coef_[0, 0])


def score(X, y, g, make, mask=None):
    """Mean and spread over REPEATS campaign splits. `mask`: score only these rows."""
    r = {"auc": [], "brier": [], "logloss": [], "slope": []}
    for rep in range(REPEATS):
        p = np.full(len(y), np.nan)
        for tr, te in splits(g, rep):
            if len(set(y[tr])) > 1:
                p[te] = make(X.shape[1]).fit(X[tr], y[tr]).predict_proba(X[te])[:, 1]   # a fresh model per fold
        m = ~np.isnan(p) if mask is None else (~np.isnan(p) & mask)
        pc = np.clip(p[m], 1e-3, 1 - 1e-3)
        r["auc"].append(roc_auc_score(y[m], pc))
        r["brier"].append(brier_score_loss(y[m], pc))
        r["logloss"].append(log_loss(y[m], pc))
        r["slope"].append(calib_slope(y[m], pc))
    out = {k: (float(np.mean(v)), float(np.std(v))) for k, v in r.items()}
    out["runs"] = r                      # per-split scores, for paired comparisons
    return out


# ---- baselines with the same fit / predict_proba shape as the models (section B2)
class _Base:
    def predict_proba(self, X):
        p = np.clip(self._p(X), 0.0, 1.0)
        return np.c_[1 - p, p]


class Average(_Base):
    """The app's baseline: ignores the conditions."""
    def fit(self, X, y):
        self.m = y.mean()
        return self

    def _p(self, X):
        return np.full(len(X), self.m)


class FuelAverage(_Base):
    """Share that burned for this fuel (falls back to the average when a fuel has fewer than 3 tests)."""
    def __init__(self, fuel_cols):
        self.cols = fuel_cols

    def fit(self, X, y):
        self.m, keys = y.mean(), [tuple(r) for r in X[:, self.cols]]
        self.by = {k: y[[kk == k for kk in keys]].mean() for k in set(keys) if sum(kk == k for kk in keys) >= 3}
        return self

    def _p(self, X):
        return np.array([self.by.get(tuple(r), self.m) for r in X[:, self.cols]])


class OxygenOnly(_Base):
    def __init__(self, j):
        self.j = j

    def fit(self, X, y):
        self.m = make_pipeline(StandardScaler(), LogisticRegression()).fit(X[:, [self.j]], y)
        return self

    def _p(self, X):
        return self.m.predict_proba(X[:, [self.j]])[:, 1]


class OxygenRule(_Base):
    """An engineer's rule, 'it keeps burning above X % oxygen': the cut that is right most often in training."""
    def __init__(self, j):
        self.j = j

    def fit(self, X, y):
        o = X[:, self.j]
        cut = max(np.unique(o), key=lambda c: ((o >= c) == y).mean())
        self.cut = cut
        self.hi = y[o >= cut].mean() if (o >= cut).any() else y.mean()
        self.lo = y[o < cut].mean() if (o < cut).any() else y.mean()
        return self

    def _p(self, X):
        return np.where(X[:, self.j] >= self.cut, self.hi, self.lo)


class NearestTests(_Base):
    """Look up the k closest NASA tests of the same fuel (inputs scaled) and use the share that burned."""
    def __init__(self, fuel_cols, k=3):
        self.cols, self.k = fuel_cols, k

    def fit(self, X, y):
        self.cont = [i for i in range(X.shape[1]) if i not in self.cols]
        self.s = StandardScaler().fit(X[:, self.cont])
        self.A, self.F, self.y = self.s.transform(X[:, self.cont]), X[:, self.cols], y
        return self

    def _p(self, X):
        B, out = self.s.transform(X[:, self.cont]), []
        for b, f in zip(B, X[:, self.cols]):
            m = (self.F == f).all(1)
            A, y = (self.A[m], self.y[m]) if m.any() else (self.A, self.y)
            out.append(y[np.argsort(((A - b) ** 2).sum(1))[: self.k]].mean())
        return np.array(out)


def base_scores(y):
    p = np.full(len(y), y.mean())
    return brier_score_loss(y, p), log_loss(y, p)


def row(label, s, bb, bl):
    beats = "yes" if s["brier"][0] < bb and s["logloss"][0] < bl else "no"
    w(f"| {label} | {s['auc'][0]:.3f} ± {s['auc'][1]:.3f} | {s['brier'][0]:.3f} | {s['logloss'][0]:.3f} | {s['slope'][0]:.2f} | {beats} |")


def table_head():
    w("| Choice | AUC (mean ± spread over 10 splits) | Brier | Log loss | Calibration slope | Beats baseline? |")
    w("|---|---|---|---|---|---|")


def frame(key):
    pb = PROBLEMS[key]
    df = pb.frame()
    return pb, df, df[pb.features].to_numpy(float), df[pb.target].astype(int).to_numpy(), df.campaign.astype(str).to_numpy()


w("# Results (generated)")
w()
w("Generated by `python scripts/evaluate_methods.py`. Do not edit by hand: rerun the script.")
w(f"Each score below averages {REPEATS} different ways of splitting the NASA test campaigns into {FOLDS} groups; "
  "the model never sees the campaign it is scored on. The ± is the spread between those splits.")

# ------------------------------------------------------------------ A. cleaning
st = get_store()
log = pd.read_parquet(ROOT / "data" / "processed" / "validation_log.parquet")
t_all = st.tests[~st.tests["demo"].astype(bool)]
w("\n## A. Cleaning: what the rules did\n")
w(f"Rows read from the 19 PSI tables: **{len(t_all)}**. Excluded: **{int(t_all.excluded.sum())}**. Used: **{int((~t_all.excluded).sum())}**.\n")
w("| Rule | Action | Rows |")
w("|---|---|---|")
for (rule, action), n in log.groupby(["rule", "action"]).size().items():
    w(f"| {rule} | {action} | {n} |")
for key in PROBLEMS:
    pb, df, X, y, g = frame(key)
    warn = df["flags"].map(lambda f: any(x != "missing_outcome" for x in f)).astype(bool)
    flagged = df.loc[warn]
    w(f"\n{pb.investigation} model data: {len(df)} tests, of which {len(flagged)} carry a warning flag "
      f"({', '.join(sorted(flagged.test_id)) or 'none'}).")

# ------------------------------------------------------------------ B. the app's models, stability
w("\n## B. The models the app trains, scored over 10 splits\n")
cards = {k: json.loads((ARTIFACTS / "predict" / f"{k}.card.json").read_text(encoding="utf-8")) for k in PROBLEMS}
for key in PROBLEMS:
    pb, df, X, y, g = frame(key)
    bb, bl = base_scores(y)
    w(f"### {pb.label} ({pb.investigation}, {pb.psi_id}): {len(y)} tests, {int(y.sum())} '{pb.outcome_yes}', {len(set(g))} campaigns\n")
    w(f"Baseline (always predicts the average, {y.mean():.0%}): Brier {bb:.3f}, log loss {bl:.3f}, AUC 0.5.\n")
    table_head()
    for name, mk in [("Logistic regression", LR()), ("Random forest", RF()), ("Gaussian process (chosen by the app)", GP())]:
        row(name, score(X, y, g, mk), bb, bl)
    w(f"\nThe app's single 5-fold run chose **{cards[key]['chosen']}**: " + ", ".join(
        f"{r['model']} AUC {r['auc']}, Brier {r['brier']}" for r in cards[key]["comparison"][1:]) + ".")

# ------------------------------------------------------------------ B2. a ladder of baselines
w("\n## B2. A ladder of baselines: is the model better than simple ways of guessing?\n")
w("The average is the minimum bar (like a sugar pill in a drug trial). These baselines use simple knowledge of the "
  "conditions; the last one is what an engineer would do by hand: look up the closest real NASA tests. "
  "Same 10 campaign splits as section B. A constant guess cannot rank anything, so its AUC is 0.5 by definition.\n")
for key in PROBLEMS:
    pb, df, X, y, g = frame(key)
    bb, bl = base_scores(y)
    j = pb.features.index("o2_pct")
    fuel_cols = [pb.features.index(c) for c in ("carbon_n", "fuel_share", "heptane") if c in pb.features]
    ladder = [("1. Always the average (the app's baseline)", lambda d: Average()),
              ("2. Average for this fuel", lambda d, fc=fuel_cols: FuelAverage(fc)),
              ("3. Oxygen only (logistic regression)", lambda d, j=j: OxygenOnly(j)),
              ("4. Rule: 'keeps burning above X % oxygen'", lambda d, j=j: OxygenRule(j)),
              ("5. Look up the 3 closest NASA tests of this fuel", lambda d, fc=fuel_cols: NearestTests(fc)),
              ("6. Gaussian process, all inputs (the app's model)", GP())]
    w(f"### {pb.label} ({pb.investigation})\n")
    w("| Way of guessing | AUC (mean ± spread) | Brier | Log loss | Calibration slope | Beats the average? |")
    w("|---|---|---|---|---|---|")
    res = {}
    for name, mk in ladder:
        s = res[name] = score(X, y, g, mk)
        if name.startswith("1."):
            w(f"| {name} | 0.5 (by definition) | {s['brier'][0]:.3f} | {s['logloss'][0]:.3f} | — | — |")
        else:
            row(name, s, bb, bl)
    gp_runs, nn = res[ladder[-1][0]]["runs"], res[ladder[-2][0]]["runs"]
    wins = sum(a > b and c < d for a, b, c, d in zip(gp_runs["auc"], nn["auc"], gp_runs["brier"], nn["brier"]))
    gain = np.array(gp_runs["auc"]) - np.array(nn["auc"])
    w(f"\nAgainst the strongest baseline (5, the closest-tests lookup), the model has the higher AUC **and** the lower Brier "
      f"score in **{wins} of {REPEATS}** splits; AUC gain {gain.mean():+.3f} (smallest {gain.min():+.3f}, largest {gain.max():+.3f}).\n")

# ------------------------------------------------------------------ C. preprocessing choices
w("\n## C. Preprocessing choices tested\n")
pb, df, X, y, g = frame("gas")
bb, bl = base_scores(y)
w(f"### Gas leak flames (CFI-G): {int(y.sum())} 'stayed lit' among {len(y)} tests\n")
table_head()
onehot = pd.get_dummies(df.fuel, dtype=float).to_numpy()
row("App features: oxygen %, pressure, fuel flow, carbon atoms, fuel share (logistic)", score(X, y, g, LR()), bb, bl)
row("Fuel as 6 separate labels instead of 2 numbers (logistic)", score(np.c_[df[["o2_pct", "psi", "fuel_flow"]].to_numpy(), onehot], y, g, LR()), bb, bl)
row("Oxygen as partial pressure (O₂ % × pressure) instead of % (logistic)",
    score(np.c_[df.o2_pct * df.psi, df[["fuel_flow", "carbon_n", "fuel_share"]].to_numpy()], y, g, LR()), bb, bl)
row("Log of pressure and fuel flow (logistic)",
    score(np.c_[df.o2_pct, np.log(df.psi), np.log(df.fuel_flow), df.carbon_n, df.fuel_share], y, g, LR()), bb, bl)
row("Strong penalty, C = 0.1 (logistic)", score(X, y, g, LR(0.1)), bb, bl)
row("'Balanced' class weights, an imbalance correction (logistic)", score(X, y, g, LR(1.0, "balanced")), bb, bl)
# mixing in the inverse flames (oxygen jet inside fuel): different physics
inv = st.usable_tests("cfig_inverse").copy()
parts = inv.fuel.map(gas_fuel_parts)
inv = inv[parts.notna() & inv.burned.notna()].copy()
parts = parts[parts.notna()]
inv["o2_pct"], inv["psi"], inv["fuel_flow"] = inv.oxidizer_o2_frac * 100, inv.pressure_kpa / 6.894757, inv.fuel_flow_mg_s
inv["carbon_n"] = [float(p[1]) for p in parts.loc[inv.index]]
inv["fuel_share"] = [p[2] for p in parts.loc[inv.index]]
inv = inv.dropna(subset=pb.features)
Xm = np.r_[X, inv[pb.features].to_numpy(float)]
ym = np.r_[y, inv.burned.astype(int).to_numpy()]
gm = np.r_[g, inv.campaign.astype(str).to_numpy()]
mask = np.r_[np.ones(len(y), bool), np.zeros(len(inv), bool)]
row(f"Adding the {len(inv)} inverse-flame tests to training, scored on normal flames only (logistic)", score(Xm, ym, gm, LR(), mask), bb, bl)

pb, df, X, y, g = frame("droplet")
bb, bl = base_scores(y)
w(f"\n### Fuel droplets (FLEX): {int(y.sum())} 'burned to the end' among {len(y)} tests\n")
table_head()
row("App features: oxygen, pressure, drop size, fuel, CO₂, helium (logistic)", score(X, y, g, LR()), bb, bl)
row("Only 3 features: oxygen, drop size, fuel (logistic)", score(df[["o2_pct", "d0_mm", "heptane"]].to_numpy(float), y, g, LR()), bb, bl)
row("Oxygen as partial pressure instead of % (logistic)",
    score(np.c_[df.o2_pct * df.psi, df[["d0_mm", "heptane", "co2_pct", "he_pct"]].to_numpy(float)], y, g, LR()), bb, bl)
row("'Balanced' class weights (logistic)", score(X, y, g, LR(1.0, "balanced")), bb, bl)
flag_ok = ~df["flags"].map(lambda f: any(x != "missing_outcome" for x in f)).astype(bool).to_numpy()
row(f"Rows with a warning flag left out ({int((~flag_ok).sum())} rows) (Gaussian process)", score(X[flag_ok], y[flag_ok], g[flag_ok], GP()), *base_scores(y[flag_ok]))
row("All rows kept, as the app does (Gaussian process)", score(X, y, g, GP()), bb, bl)

# ------------------------------------------------------------------ D. the conclusion, no model
w("\n## D. Checking the main conclusion without any model\n")
gas = st.usable_tests("cfig_normal")
gas = gas[gas.burned.notna()]
lo, hi = gas[gas.o2_frac < 0.30], gas[gas.o2_frac.between(0.35, 0.40)]
_, p = fisher_exact([[lo.burned.sum(), len(lo) - lo.burned.sum()], [hi.burned.sum(), len(hi) - hi.burned.sum()]])
w(f"- **Significant?** Gas flames that stayed lit: {int(lo.burned.sum())} of {len(lo)} below 30 % oxygen, "
  f"{int(hi.burned.sum())} of {len(hi)} at 35–40 %. Fisher exact test p = {p:.1e} (chance would give a difference this big "
  f"about {p * 1e6:.0f} times in a million).")
mins = [gas[(gas.campaign != c) & (gas.burned == 1)].o2_frac.min() for c in gas.campaign.unique()]
w(f"- **Stable?** Lowest oxygen at which a gas flame stayed lit: {gas[gas.burned == 1].o2_frac.min() * 100:.1f} %. "
  f"Leaving out any one of the {gas.campaign.nunique()} campaigns: {min(mins) * 100:.1f}–{max(mins) * 100:.1f} %.")
gap = gas[gas.o2_frac.between(0.25, 0.33)]
w(f"- **Covered?** Gas tests with an outcome between 25 % and 33 % oxygen (Moon-base air): **{len(gap)}**. "
  "So the data says 'no flame stayed lit below 30 % in these tests', not 'flames need 33 %'.")

OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
print(f"\nwritten {OUT.relative_to(ROOT)}")
