"""Adapter: the FLEX experimental table as published on NASA PSI (PSI-69, CSV export).

The export is Latin-1, uses an en dash for empty cells, drops subscripts in its headers
("O initial ambient composition" is O₂) and gives the atmosphere as four mole fractions.
Nothing is corrected here: the shared normalizer checks, converts and records every value.
Three helper columns are added and marked as derived in the provenance: a unique test id,
a campaign (calendar quarter, used to group cross-validation) and the dominant inert gas.
"""
from __future__ import annotations

from typing import Any

import pandas as pd

from ..core.config import RAW
from .base import AdapterResult, _is_blank, register, tabular_to_canonical

FUEL = {"heptane": "n-heptane", "methanol": "methanol"}
INERT = [("N initial ambient composition; mole fraction", "N2"), ("CO initial ambient composition; mole fraction", "CO2"),
         ("He initial ambient composition; mole fraction", "He")]


def _fuel(v: Any):
    if _is_blank(v):
        return None, None
    s = str(v).strip()
    canon = FUEL.get(s.lower(), s.lower())
    return canon, (f"'{s}' → {canon}" if canon != s else None)


def _date(v: Any):
    if _is_blank(v):
        return None, None
    d = pd.to_datetime(str(v).strip(), errors="coerce", format="mixed")
    if pd.isna(d):
        return None, f"'{v}' is not a readable date"
    return d.strftime("%Y-%m-%d"), f"'{v}' → {d.strftime('%Y-%m-%d')}"


def _end(v: Any):
    return (None, None) if _is_blank(v) else (str(v).strip().capitalize(), None)


@register("flex_psi")
def load(ds_id: str, cfg: dict) -> AdapterResult:
    name = cfg["files"][0]
    raw = pd.read_csv(RAW / ds_id / name, dtype=str, keep_default_na=False, encoding="latin-1")
    raw = raw.replace({"\x96": "", "–": ""})                       # the export's "no value" mark
    num = raw["FLEX Test #"].astype(int)
    raw["Test"] = "FLEX-" + num.map("{:03d}".format)
    d = pd.to_datetime(raw["Test Date"], errors="coerce", format="mixed")
    raw["Campaign"] = (d.dt.year.astype("Int64").astype(str) + "-Q" + d.dt.quarter.astype("Int64").astype(str)).where(d.notna(), "")
    inert = pd.DataFrame({k: pd.to_numeric(raw[c], errors="coerce") for c, k in INERT})
    raw["Diluent"] = inert.idxmax(axis=1).where(inert.notna().any(axis=1), "")
    raw["Investigation"] = cfg["investigations"][0]
    raw["Outcome"] = raw["Test end"]
    res = tabular_to_canonical(raw, ds_id, cfg, f"data/raw/{ds_id}/{name}",
                               category_maps={"fuel": _fuel, "mission_date": _date, "test_end": _end})
    derived = {"campaign": "calendar quarter of the test date (groups tests for cross-validation)",
               "diluent": "the inert gas with the largest mole fraction",
               "investigation_id": "every row of this file belongs to FLEX"}
    for p in res.provenance:
        if p["variable"] == "burned":                        # read from the file's own "Test end" column
            p["column"] = "Test end"
        if p["variable"] in derived:
            p["column"], p["raw_value"] = None, None
            p["steps"] = [{"op": "derive", "detail": derived[p["variable"]]}]
    for _, r in res.tests.iterrows():
        res.published[r["test_id"]] = {v: float(r[v]) for v in ("burn_rate_k_mm2_s", "d0_mm", "extinction_d_mm")
                                       if r.get(v) is not None and pd.notna(r.get(v))}
    return res
