"""Adapter: ACME gas-flame tables as published on NASA PSI (CFI-G normal flames, PSI-159; Flame Design, PSI-10).

One row per test in the Combustion Integrated Rack: a spherical porous burner on the ISS that issues
fuel into a closed chamber of known oxygen fraction and pressure. Nothing is corrected here: the
shared normalizer checks, converts and records every value.

Helper columns, recorded as derived in the provenance (never shown as source values):
  * Test id      — prefix + the file's own test code, spaces removed ("21088 B1" -> "CFIG-21088B1")
  * Campaign     — "Day N" from the file's Day column (groups cross-validation)
  * Date         — from the YYDDD prefix of the test code (year + day of year, the convention PSI
                   states for ACME tables); left blank if the code does not start with five digits
  * Outcome      — only for tables that record how the flame ended (cfg `outcome`): the
                   "self-extinguished / flow terminated" column, mapped by `outcome_map`
  * Test end     — plain words built from hot ignition, cool flame and that same column
"""
from __future__ import annotations

import re
from datetime import date, timedelta
from typing import Any

import pandas as pd

from ..core.config import RAW
from .base import AdapterResult, _is_blank, register, tabular_to_canonical

FUEL = {"c2h4": "ethylene", "c3h8": "propane", "ch4": "methane", "c2h6": "ethane", "c4h10": "butane"}


def _fuel(v: Any):
    if _is_blank(v):
        return None, None
    s = str(v).strip()
    canon = FUEL.get(s.lower(), s.lower())
    return canon, (f"'{s}' → {canon}" if canon != s else None)


def _yyddd(code: str) -> str:
    m = re.match(r"^\s*(\d{2})(\d{3})", code or "")
    if not m:
        return ""
    yy, ddd = int(m.group(1)), int(m.group(2))
    if not 1 <= ddd <= 366:
        return ""
    return (date(2000 + yy, 1, 1) + timedelta(days=ddd - 1)).isoformat()


def _test_end(r: pd.Series, cfg: dict) -> str:
    oc = cfg.get("outcome") or {}
    hot = str(r.get(oc.get("ignition_column", ""), "")).strip().lower()
    cool = str(r.get(oc.get("cool_column", ""), "")).strip().lower()
    end = str(r.get(oc.get("column", ""), "")).strip().upper()
    if end == "FT":
        return "Still burning when the fuel flow was stopped"
    if end == "SE":
        return "Self-extinguished"
    if cool.startswith("yes"):
        return "Cool flame only (no hot flame)"
    if hot in ("no", "flash"):
        return "No hot ignition"
    return ""


@register("psi_gas_flames")
def load(ds_id: str, cfg: dict) -> AdapterResult:
    name = cfg["files"][0]
    raw = pd.read_csv(RAW / ds_id / name, dtype=str, keep_default_na=False, encoding="utf-8-sig")
    raw.columns = [c.strip() for c in raw.columns]
    raw = raw[raw["Test"].str.strip() != ""]                   # trailing empty rows in some exports
    code = raw["Test"].str.replace(r"\s+", "", regex=True)
    raw["Test id"] = cfg["id_prefix"] + code
    raw["Campaign"] = "Day " + raw["Day"].str.strip()
    raw["Date"] = code.map(_yyddd)
    raw["Investigation"] = cfg["investigations"][0]
    if cfg.get("outcome"):
        raw["Outcome"] = raw[cfg["outcome"]["column"]].str.strip()
        raw["Test end"] = raw.apply(_test_end, axis=1, cfg=cfg)

    res = tabular_to_canonical(raw, ds_id, cfg, f"data/raw/{ds_id}/{name}",
                               category_maps={"fuel": _fuel, "test_end": lambda v: (None if _is_blank(v) else str(v), None)})
    derived = {"campaign": "test day from the file's Day column (groups tests for cross-validation)",
               "investigation_id": f"every row of this file belongs to {cfg['investigations'][0]}",
               "mission_date": "year and day of year read from the YYDDD prefix of the test code"}
    if cfg.get("outcome"):
        col = cfg["outcome"]["column"]
        derived["test_end"] = (f"from the file's '{cfg['outcome']['ignition_column']}', '{cfg['outcome'].get('cool_column', '')}' "
                               f"and '{col}' columns (SE = self-extinguished, FT = flow terminated while burning)")
    for p in res.provenance:
        if p["variable"] == "burned" and cfg.get("outcome"):
            p["column"] = cfg["outcome"]["column"]              # read from the file's own column
        if p["variable"] in derived:
            p["column"], p["raw_value"] = None, None
            p["steps"] = [{"op": "derive", "detail": derived[p["variable"]]}]
    return res
