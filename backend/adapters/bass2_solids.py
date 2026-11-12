"""Adapter: solid-material flammability tables shaped like BASS-II (XLSX or CSV)."""
from __future__ import annotations

from typing import Any

import pandas as pd

from ..core.config import RAW
from .base import AdapterResult, _is_blank, register, tabular_to_canonical

GRAVITY = {"µg": 0.0, "μg": 0.0, "ug": 0.0, "microgravity": 0.0, "0g": 0.0, "1g": 1.0, "normal": 1.0, "earth": 1.0}


def _gravity(v: Any):
    if _is_blank(v):
        return None, None
    s = str(v).strip().lower()
    if s in GRAVITY:
        return GRAVITY[s], f"'{v}' → gravity_g={GRAVITY[s]}"
    try:
        return float(s.rstrip("g")), None
    except ValueError:
        return None, f"'{v}' not understood as a gravity level"


def _material(v: Any):
    return (None, None) if _is_blank(v) else (str(v).strip(), None)


@register("bass2_solids")
def load(ds_id: str, cfg: dict) -> AdapterResult:
    name = cfg["files"][0]
    path = RAW / ds_id / name
    if path.suffix.lower() in {".xlsx", ".xls"}:
        raw = pd.read_excel(path, sheet_name=cfg.get("sheet", 0))
    else:
        raw = pd.read_csv(path)
    res = tabular_to_canonical(raw, ds_id, cfg, f"data/raw/{ds_id}/{name}" + (f" › {cfg['sheet']}" if cfg.get("sheet") else ""),
                               category_maps={"gravity_g": _gravity, "material": _material})
    res.tests["investigation_id"] = cfg["investigations"][0]
    for _, r in res.tests.iterrows():
        if pd.notna(r.get("spread_rate_mm_s")):
            res.published[r["test_id"]] = {"spread_rate_mm_s": float(r["spread_rate_mm_s"])}
    return res
