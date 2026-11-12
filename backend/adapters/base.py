"""Shared adapter machinery: map raw columns → canonical variables with per-value provenance.

An adapter only has to (1) read its raw file into a DataFrame and (2) declare small
category maps. `tabular_to_canonical` does unit parsing, conversion, derivation and
provenance recording the same way for every dataset.
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

import pandas as pd

from ..core import config
from ..core.units import header_unit, is_flagged, normalize

REGISTRY: dict[str, Callable[[str, dict], "AdapterResult"]] = {}


def register(name: str):
    def deco(fn):
        REGISTRY[name] = fn
        return fn
    return deco


@dataclass
class AdapterResult:
    tests: pd.DataFrame                          # canonical wide table (one row per test)
    provenance: list[dict] = field(default_factory=list)
    stages: list[dict] = field(default_factory=list)   # for the Refinery pipeline view
    published: dict[str, dict[str, float]] = field(default_factory=dict)  # test_id -> {var: value}
    raw_preview: Optional[pd.DataFrame] = None


def _is_blank(v: Any) -> bool:
    return v is None or (isinstance(v, float) and math.isnan(v)) or (isinstance(v, str) and not v.strip())


def tabular_to_canonical(raw: pd.DataFrame, ds_id: str, cfg: dict, source_file: str,
                         category_maps: dict[str, Callable[[Any], tuple[Any, Optional[str]]]] | None = None,
                         header_row_offset: int = 2) -> AdapterResult:
    variables = config.variables()
    colmap: dict[str, str] = cfg["columns"]
    unit_over = cfg.get("units", {})
    category_maps = category_maps or {}
    outcome_map = {k.lower(): v for k, v in cfg.get("outcome_map", {}).items()}
    rows, prov = [], []
    unit_conversions = 0

    for i, r in raw.iterrows():
        src_row = int(i) + header_row_offset   # 1-based line incl. header (CSV) / Excel row
        out: dict[str, Any] = {"dataset": ds_id, "_row": src_row, "demo": bool(cfg.get("demo"))}
        invalid: dict[str, str] = {}     # variable -> why its source value was refused
        for col, var in colmap.items():
            if col not in raw.columns:
                continue
            v = r[col]
            steps: list[dict] = []
            meta = variables.get(var, {})
            if var == "burned":
                if _is_blank(v):
                    val = None
                else:
                    key = str(v).strip().lower()
                    val = outcome_map.get(key)
                    steps.append({"op": "map_category", "detail": f"'{v}' → burned={val}"})
            elif var in category_maps:
                val, note = category_maps[var](v)
                if note:
                    steps.append({"op": "map_category", "detail": note})
            elif meta.get("kind") == "number":
                val, steps = normalize(var, v, unit_over.get(col) or header_unit(col))
                unit_conversions += sum(1 for s in steps if s["op"] == "convert")
                if is_flagged(steps):
                    invalid[var] = is_flagged(steps)
            elif _is_blank(v):
                val = None
            else:
                val = str(v).strip()
            out[var] = val
            if var not in ("test_id",):
                prov.append({"dataset": ds_id, "test_id": str(r[[c for c, t in colmap.items() if t == 'test_id'][0]]),
                             "variable": var, "source_file": source_file, "locator": f"row {src_row}",
                             "column": col, "raw_value": None if _is_blank(v) else str(v), "steps": steps})
        for var, val in cfg.get("constants", {}).items():
            if out.get(var) is None:
                out[var] = val
                prov.append({"dataset": ds_id, "test_id": out["test_id"], "variable": var, "source_file": "config/datasets.yaml",
                             "locator": f"{ds_id}.constants", "column": None, "raw_value": str(val),
                             "steps": [{"op": "constant", "detail": f"dataset constant {var}={val}"}]})
        # derived variables: computed only from inputs that passed validation
        o2pp_inputs = ("o2_frac", "pressure_kpa")
        blocked = [v for v in o2pp_inputs if v in invalid]
        if blocked:
            out["o2_pp_kpa"] = None
            names = " and ".join(variables[v]["label"].lower() for v in blocked)
            invalid["o2_pp_kpa"] = f"Not computed: input flagged ({names})."
            prov.append({"dataset": ds_id, "test_id": out["test_id"], "variable": "o2_pp_kpa", "source_file": source_file,
                         "locator": f"row {src_row}", "column": None, "raw_value": None,
                         "steps": [{"op": "not_computed", "detail": invalid["o2_pp_kpa"]}]})
        elif all(out.get(v) is not None for v in o2pp_inputs):
            out["o2_pp_kpa"] = out["o2_frac"] * out["pressure_kpa"]
            prov.append({"dataset": ds_id, "test_id": out["test_id"], "variable": "o2_pp_kpa", "source_file": source_file,
                         "locator": f"row {src_row}", "column": None, "raw_value": None,
                         "steps": [{"op": "derive", "detail": f"o2_frac × pressure_kpa = {out['o2_frac']:.4g} × "
                                                              f"{out['pressure_kpa']:.4g} = {out['o2_pp_kpa']:.4g} kPa"}]})
        out["invalid"] = invalid
        rows.append(out)

    df = pd.DataFrame(rows)
    df["test_id"] = df["test_id"].astype(str)
    stages = [
        {"id": "raw", "label": "Raw file", "rows": len(raw), "detail": f"{source_file} · {raw.shape[1]} columns"},
        {"id": "parsed", "label": "Checked, then unit-normalized", "rows": len(df),
         "detail": f"{unit_conversions} unit conversions · {len(colmap)} columns mapped"},
        {"id": "derived", "label": "Derived variables", "rows": len(df),
         "detail": "o2_pp_kpa = o2_frac × pressure_kpa (skipped when an input is flagged)"},
    ]
    return AdapterResult(tests=df, provenance=prov, stages=stages, raw_preview=raw.head(50))


def slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")[:40]
