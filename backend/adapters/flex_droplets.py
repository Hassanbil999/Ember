"""Adapter: droplet-combustion test tables shaped like FLEX (CSV or XLSX).

Expected columns are declared in config/datasets.yaml → `columns`. Cells may carry their
own units ("14.7 psi", "21%") — the shared normalizer handles them.
"""
from __future__ import annotations

from typing import Any

import pandas as pd

from ..core.config import RAW
from .base import AdapterResult, _is_blank, register, tabular_to_canonical

DILUENTS = {"n2": "N2", "nitrogen": "N2", "co2": "CO2", "carbon dioxide": "CO2", "he": "He", "helium": "He"}


def _diluent(v: Any):
    if _is_blank(v):
        return None, None
    key = str(v).strip().lower()
    out = DILUENTS.get(key, str(v).strip())
    return out, (f"'{v}' → {out}" if out != str(v).strip() else None)


def _fuel(v: Any):
    if _is_blank(v):
        return None, None
    s = str(v).strip().lower()
    canon = {"heptane": "n-heptane", "decane": "n-decane"}.get(s, s)
    return canon, (f"'{v}' → {canon}" if canon != str(v).strip() else None)


@register("flex_droplets")
def load(ds_id: str, cfg: dict) -> AdapterResult:
    frames = []
    for name in cfg["files"]:
        path = RAW / ds_id / name
        raw = pd.read_excel(path) if path.suffix.lower() in {".xlsx", ".xls"} else pd.read_csv(path, dtype=str, keep_default_na=False)
        frames.append((name, raw))
    name, raw = frames[0]
    res = tabular_to_canonical(raw, ds_id, cfg, f"data/raw/{ds_id}/{name}",
                               category_maps={"diluent": _diluent, "fuel": _fuel})
    df = res.tests
    if "investigation_id" not in df.columns or df["investigation_id"].isna().all():
        df["investigation_id"] = cfg["investigations"][0]
    # values the report/table publishes, used to validate image-derived measurements
    for _, r in df.iterrows():
        pub = {}
        if r.get("burn_rate_k_mm2_s") is not None and pd.notna(r.get("burn_rate_k_mm2_s")):
            pub["burn_rate_k_mm2_s"] = float(r["burn_rate_k_mm2_s"])
        if r.get("d0_mm") is not None and pd.notna(r.get("d0_mm")):
            pub["d0_mm"] = float(r["d0_mm"])
        if r.get("extinction_d_mm") is not None and pd.notna(r.get("extinction_d_mm")):
            pub["extinction_d_mm"] = float(r["extinction_d_mm"])
        res.published[r["test_id"]] = pub
    return res
