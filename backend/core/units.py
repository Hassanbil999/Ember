"""Unit parsing and normalization into canonical units.

`normalize(var, raw, header_unit)` returns (value, steps) where steps describe every
transformation so provenance can show exactly what happened.
"""
from __future__ import annotations

import math
import re
from typing import Any, Optional

# factor to canonical unit
PRESSURE = {"kpa": 1.0, "pa": 0.001, "mpa": 1000.0, "atm": 101.325, "psi": 6.894757, "psia": 6.894757,
            "bar": 100.0, "mbar": 0.1, "torr": 0.133322, "mmhg": 0.133322}
LENGTH = {"mm": 1.0, "m": 1000.0, "cm": 10.0, "um": 0.001, "µm": 0.001, "μm": 0.001, "in": 25.4}
SPEED = {"cm/s": 1.0, "mm/s": 0.1, "m/s": 100.0, "ft/min": 0.508}
TIME = {"s": 1.0, "ms": 0.001, "min": 60.0}
RATE_AREA = {"mm^2/s": 1.0, "mm2/s": 1.0, "mm²/s": 1.0, "cm^2/s": 100.0, "m^2/s": 1e6}
SPREAD = {"mm/s": 1.0, "cm/s": 10.0, "m/s": 1000.0}

CANON_TABLE = {
    "pressure_kpa": ("kPa", PRESSURE),
    "o2_pp_kpa": ("kPa", PRESSURE),
    "d0_mm": ("mm", LENGTH),
    "thickness_mm": ("mm", LENGTH),
    "extinction_d_mm": ("mm", LENGTH),
    "flow_cm_s": ("cm/s", SPEED),
    "burn_rate_k_mm2_s": ("mm²/s", RATE_AREA),
    "spread_rate_mm_s": ("mm/s", SPREAD),
}

# Physical limits in canonical units: (lower bound, lower bound allowed?, upper bound or None, plain reason).
# They are checked against the RAW value in the RAW unit (the bound is rescaled, the value is not),
# so an impossible reading is flagged before any conversion can launder it into a normal-looking number.
PHYSICAL = {
    "pressure_kpa": (0.0, False, None, "Total pressure must be greater than zero: nothing can burn in a vacuum."),
    "o2_frac": (0.0, True, 1.0, "An oxygen fraction must lie between 0 and 100 %."),
    "d0_mm": (0.0, False, None, "A droplet diameter must be greater than zero."),
    "thickness_mm": (0.0, False, None, "A sample thickness must be greater than zero."),
    "extinction_d_mm": (0.0, True, None, "A diameter cannot be negative."),
    "flow_cm_s": (0.0, True, None, "A flow speed cannot be negative."),
    "burn_rate_k_mm2_s": (0.0, True, None, "A burning rate cannot be negative."),
    "spread_rate_mm_s": (0.0, True, None, "A flame spread rate cannot be negative."),
    "gravity_g": (0.0, True, None, "A gravity level cannot be negative."),
}


def raw_problem(var: str, value: float, factor: float = 1.0, unit: str = "") -> Optional[str]:
    """Reason if `value` (still in its source unit; `factor` = canonical units per source unit) is impossible."""
    rule = PHYSICAL.get(var)
    if rule is None:
        return None
    lo, lo_ok, hi, reason = rule
    lo_raw, hi_raw = lo / factor, (None if hi is None else hi / factor)
    bad = value < lo_raw or (value == lo_raw and not lo_ok) or (hi_raw is not None and value > hi_raw)
    return f"{reason} The source says {_f(value)}{' ' + unit if unit else ''}." if bad else None


def is_flagged(steps: list[dict]) -> Optional[str]:
    """The reason carried by a `flagged` step, if normalization refused the value."""
    return next((s["detail"] for s in steps if s["op"] == "flagged"), None)


_NUM_UNIT = re.compile(r"^\s*([-+]?\d*\.?\d+(?:[eE][-+]?\d+)?)\s*([^\d\s].*)?$")


def _f(x: float) -> str:
    return f"{x:.6g}"


def parse_number_unit(raw: Any) -> tuple[Optional[float], Optional[str]]:
    if raw is None:
        return None, None
    if isinstance(raw, (int, float)):
        if isinstance(raw, float) and math.isnan(raw):
            return None, None
        return float(raw), None
    s = str(raw).strip().replace(",", "")
    if not s or s.lower() in {"nan", "na", "n/a", "-", "—", "none"}:
        return None, None
    m = _NUM_UNIT.match(s)
    if not m:
        return None, None
    unit = (m.group(2) or "").strip() or None
    return float(m.group(1)), unit


def normalize(var: str, raw: Any, header_unit: Optional[str] = None) -> tuple[Optional[float], list[dict]]:
    """Normalize a numeric raw cell for canonical variable `var`.

    Validation comes first: an impossible raw value returns (None, [..., {"op": "flagged"}]) and is
    never converted. Callers use `is_flagged(steps)` to tell "flagged" from "blank"."""
    steps: list[dict] = []

    def refuse(reason: str):
        steps.append({"op": "flagged", "detail": reason})
        return None, steps

    value, unit = parse_number_unit(raw)
    if value is None:
        return None, steps
    unit = unit or header_unit
    if isinstance(raw, str) and unit and unit != header_unit:
        steps.append({"op": "parse_unit", "detail": f"read '{raw}' as {_f(value)} {unit}"})

    if var == "o2_frac":
        u = (unit or "").lower()
        pct = u in {"%", "pct", "percent", "vol%", "mol%"} or (value > 1.0 and not u)
        bad = raw_problem(var, value, 0.01 if pct else 1.0, "%" if pct else "")
        if bad:
            return refuse(bad)
        if u in {"%", "pct", "percent", "vol%", "mol%"}:
            steps.append({"op": "convert", "detail": f"{_f(value)} % → {_f(value / 100)} mole fraction"})
            return value / 100.0, steps
        if value > 1.0 and not u:
            steps.append({"op": "convert", "detail": f"{_f(value)} > 1 with no unit → interpreted as percent → {_f(value / 100)}"})
            return value / 100.0, steps
        return value, steps

    if var == "gravity_g":
        u = (unit or "").lower()
        bad = raw_problem(var, value, 9.80665 ** -1 if u in {"m/s2", "m/s^2", "m/s²"} else 1.0, unit or "")
        if bad:
            return refuse(bad)
        if u in {"m/s2", "m/s^2", "m/s²"}:
            steps.append({"op": "convert", "detail": f"{_f(value)} m/s² → {_f(value / 9.80665)} g₀"})
            return value / 9.80665, steps
        return value, steps

    if var in CANON_TABLE:
        canon, table = CANON_TABLE[var]
        if unit:
            key = unit.lower().replace(" ", "").replace("²", "^2")
            key2 = unit.lower().replace(" ", "")
            factor = table.get(key, table.get(key2))
            if factor is None:
                return refuse(f"Unit '{unit}' is not recognised, so the value cannot be checked or converted.")
            bad = raw_problem(var, value, factor, unit)
            if bad:
                return refuse(bad)
            if factor != 1.0:
                out = value * factor
                steps.append({"op": "convert", "detail": f"{_f(value)} {unit} → {_f(out)} {canon}"})
                return out, steps
            return value, steps
        bad = raw_problem(var, value, 1.0, canon)
        if bad:
            return refuse(bad)
        return value, steps

    return value, steps


def header_unit(header: str) -> Optional[str]:
    """Extract a unit from headers like 'Thickness [mm]' or 'D0 (mm)'."""
    m = re.search(r"[\[(]([^\])]+)[\])]\s*$", header)
    return m.group(1).strip() if m else None


def fmt(value: Optional[float], var: str, variables: dict) -> str:
    if value is None:
        return "no data"
    meta = variables.get(var, {})
    scale = meta.get("display_scale", 1)
    unit = meta.get("display_unit", meta.get("unit", ""))
    return f"{value * scale:.3g} {unit}".strip()
