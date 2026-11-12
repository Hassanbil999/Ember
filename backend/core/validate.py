"""Configurable validation: flag, never silently fix. Every decision is logged with a reason."""
from __future__ import annotations

import numpy as np
import pandas as pd

from . import config


def _eval_when(df: pd.DataFrame, expr: str) -> pd.Series:
    # missing columns evaluate as NaN → comparisons False
    cols = {c: df[c] if c in df.columns else pd.Series(np.nan, index=df.index) for c in
            ["pressure_kpa", "o2_frac", "n2_frac", "co2_frac", "he_frac", "burned", "burn_rate_k_mm2_s", "spread_rate_mm_s",
             "d0_mm", "extinction_d_mm", "flow_cm_s"]}
    for c in cols:
        cols[c] = pd.to_numeric(cols[c], errors="coerce")
    local = pd.DataFrame(cols)
    try:
        return local.eval(expr).fillna(False).astype(bool)
    except Exception:
        return pd.Series(False, index=df.index)


def validate(df: pd.DataFrame, dataset: str) -> tuple[pd.DataFrame, list[dict]]:
    """Return df with `flags` (list[str]) and `excluded` (bool) columns, plus a log of events."""
    variables = config.variables()
    df = df.copy()
    df["flags"] = [[] for _ in range(len(df))]
    df["excluded"] = False
    log: list[dict] = []

    def mark(mask: pd.Series, rule: dict, detail_fn=None):
        for idx in df.index[mask]:
            if rule["id"] in df.at[idx, "flags"]:
                continue
            df.at[idx, "flags"] = df.at[idx, "flags"] + [rule["id"]]
            if rule["action"] == "exclude":
                df.at[idx, "excluded"] = True
            log.append({
                "dataset": dataset, "test_id": df.at[idx, "test_id"], "rule": rule["id"],
                "action": rule["action"], "reason": rule["reason"],
                "detail": detail_fn(idx) if detail_fn else "",
                "source_row": int(df.at[idx, "_row"]) if "_row" in df.columns else None,
            })

    for rule in config.validation_rules():
        if rule.get("invalid"):
            if "invalid" in df.columns:
                mark(df["invalid"].map(bool), rule,
                     lambda i: " ".join(f"{k}: {v}" for k, v in df.at[i, "invalid"].items()))
        elif "when" in rule:
            mark(_eval_when(df, rule["when"]), rule)
        elif rule.get("plausible"):
            for var, meta in variables.items():
                rng = meta.get("plausible_range")
                if not rng or var not in df.columns:
                    continue
                col = pd.to_numeric(df[var], errors="coerce")
                bad = (col < rng[0]) | (col > rng[1])
                mark(bad.fillna(False), rule,
                     lambda i, v=var, r=rng: f"{v}={df.at[i, v]:.4g} outside plausible {r}")
        elif "duplicate_on" in rule:
            keys = [k for k in rule["duplicate_on"] if k in df.columns]
            if keys:
                mark(df.duplicated(subset=keys, keep="first"), rule)
        elif "missing" in rule:
            var = rule["missing"]
            if var in df.columns:
                mark(df[var].isna(), rule)
    return df, log
