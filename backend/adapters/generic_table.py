"""Adapter: any tidy CSV/XLSX whose columns are mapped in config/datasets.yaml.

Use this for a new dataset before writing a dedicated adapter. Category columns are kept
as stripped strings; numbers go through the shared unit normalizer.
"""
from __future__ import annotations

import pandas as pd

from ..core.config import RAW
from .base import AdapterResult, register, tabular_to_canonical


@register("generic_table")
def load(ds_id: str, cfg: dict) -> AdapterResult:
    name = cfg["files"][0]
    path = RAW / ds_id / name
    raw = pd.read_excel(path, sheet_name=cfg.get("sheet", 0)) if path.suffix.lower() in {".xlsx", ".xls"} \
        else pd.read_csv(path, dtype=str, keep_default_na=False)
    res = tabular_to_canonical(raw, ds_id, cfg, f"data/raw/{ds_id}/{name}")
    if "investigation_id" not in res.tests.columns:
        res.tests["investigation_id"] = (cfg.get("investigations") or [ds_id])[0]
    return res
