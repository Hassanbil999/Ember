"""One readable record per test: every value with its status, plain label, unit, source and trail.

This is the single place where a stored value becomes display text, so the rules live here once:
flagged values never render as numbers, gravity is a regime name, dataset settings are "assumed",
and every blank says why. The provenance panel renders this payload as-is.
"""
from __future__ import annotations

import json
from functools import lru_cache

import pandas as pd

from .core import config
from .core.config import RAW
from .core.store import get_store

STATUS_LABEL = {"measured": "Measured", "derived": "Derived", "assumed": "Assumed", "flagged": "Flagged",
                "image": "Measured from images", "blank": "No value"}

# (variable, plain label, group) in display order
FIELDS = [
    ("material", "Material", "conditions"),
    ("sample_shape", "Sample shape", "conditions"),
    ("fuel", "Fuel", "conditions"),
    ("o2_frac", "Oxygen in the atmosphere", "conditions"),
    ("n2_frac", "Nitrogen", "conditions"),
    ("co2_frac", "Carbon dioxide", "conditions"),
    ("he_frac", "Helium", "conditions"),
    ("diluent", "Main inert gas", "conditions"),
    ("pressure_kpa", "Total pressure", "conditions"),
    ("o2_pp_kpa", "Oxygen partial pressure", "conditions"),
    ("flow_cm_s", "Airflow past the sample", "conditions"),
    ("flow_direction", "Flow direction", "conditions"),
    ("d0_mm", "Droplet size at ignition", "conditions"),
    ("thickness_mm", "Sample thickness", "conditions"),
    ("diameter_mm", "Sample diameter", "conditions"),
    ("fuel_flow_mg_s", "Fuel flow into the flame", "conditions"),
    ("burner_mm", "Burner or nozzle size", "conditions"),
    ("oxidizer_o2_frac", "Oxygen in the oxidizer stream (inverse flame)", "conditions"),
    ("ambient_fuel_frac", "Fuel in the surrounding gas (inverse flame)", "conditions"),
    ("heater_ratio", "Heater setting (Rt/R0)", "conditions"),
    ("heat_duration_s", "Heating time", "conditions"),
    ("mass_loss_rate_mg_min", "Sample weight-loss rate", "conditions"),
    ("smoke_aging_s", "Smoke aging time before measurement", "conditions"),
    ("gravity_g", "Gravity", "conditions"),
    ("test_end", "How the test ended", "results"),
    ("burned", "Outcome", "results"),
    ("burn_time_s", "Burn time", "results"),
    ("burn_rate_k_mm2_s", "Burning rate (K)", "results"),
    ("extinction_d_mm", "Droplet size when the flame went out", "results"),
    ("spread_rate_mm_s", "Flame spread speed", "results"),
    ("flames_ignited", "Flames ignited that day", "results"),
    ("notes", "Test note", "metadata"),
    ("investigation_id", "Experiment", "metadata"),
    ("campaign", "Test campaign", "metadata"),
    ("mission_date", "Test date", "metadata"),
]
DILUENT = {"N2": "Nitrogen (N₂)", "CO2": "Carbon dioxide (CO₂)", "He": "Helium (He)"}
RULE_TITLE = {"impossible_value": "Impossible value", "implausible": "Unusual value", "duplicate": "Duplicate row",
              "missing_outcome": "No burn-or-extinguish outcome", "rate_without_burn": "Spread rate reported for an extinguished sample",
              "fractions_do_not_sum": "Gas fractions do not add up", "extinction_larger_than_start": "Extinction diameter larger than the start"}


def gravity_label(g) -> str | None:
    """Regime name for a gravity code. Microgravity is never shown as zero."""
    if g is None or pd.isna(g):
        return None
    g = float(g)
    if g < 0.02:
        return "Microgravity (ISS)"
    if abs(g - 1.0) < 0.05:
        return "Earth 1g"
    if abs(g - 0.165) < 0.01:
        return "Moon gravity (1/6 g)"
    if abs(g - 0.38) < 0.01:
        return "Mars gravity (0.38 g)"
    return f"Partial gravity ({g:.2g} g)"


def outcome_label(b) -> str | None:
    if b is None or pd.isna(b):
        return None
    return "Burned" if float(b) >= 0.5 else "Extinguished"


def _num(v: float, digits: int = 4) -> str:
    return f"{float(f'{v:.{digits}g}'):g}"


def display(var: str, v) -> tuple[str | None, str]:
    """(value text, unit) for a stored value; (None, '') when there is nothing to show."""
    if v is None or (not isinstance(v, str) and pd.isna(v)):
        return None, ""
    if var == "gravity_g":
        return gravity_label(v), ""
    if var == "burned":
        return outcome_label(v), ""
    if var == "diluent":
        return DILUENT.get(str(v), str(v)), ""
    if var.endswith("_frac"):
        return _num(float(v) * 100), "%"
    meta = config.variables().get(var, {})
    if meta.get("kind") == "number":
        return _num(float(v)), meta.get("unit", "")
    return str(v), ""


def _blank_reason(var: str, row: dict) -> str:
    burned = row.get("burned")
    known = burned is not None and not pd.isna(burned)
    if var == "burned" and row.get("test_end") == "Disruption":
        return "Not determined: the droplet broke apart before the flame burned out or went out"
    if var == "extinction_d_mm" and known and burned >= 0.5:
        return "Not applicable: the droplet burned to completion"
    if var in ("burn_rate_k_mm2_s", "spread_rate_mm_s") and known and burned < 0.5:
        return "Not applicable: flame extinguished"
    return "Not reported in source"


@lru_cache(maxsize=8)
def _raw_table(dataset: str) -> tuple[str, pd.DataFrame]:
    cfg = config.datasets()[dataset]
    name = cfg["files"][0]
    path = RAW / dataset / name
    if path.suffix.lower() in {".xlsx", ".xls"}:
        df = pd.read_excel(path, sheet_name=cfg.get("sheet", 0), dtype=str)
    else:
        try:
            df = pd.read_csv(path, dtype=str, keep_default_na=False, encoding="utf-8-sig")
        except UnicodeDecodeError:          # e.g. the PSI export, which is Latin-1
            df = pd.read_csv(path, dtype=str, keep_default_na=False, encoding="latin-1")
    return name, df.fillna("")


def source_rows(dataset: str, row: int, span: int = 3) -> dict:
    """The raw table around one source row (row numbers count the header as row 1)."""
    name, df = _raw_table(dataset)
    i = row - 2
    lo, hi = max(0, i - span), min(len(df), i + span + 1)
    return {"dataset": dataset, "title": config.datasets()[dataset]["title"], "file": name, "row": row,
            "columns": list(df.columns),
            "rows": [{"n": j + 2, "cells": [str(x) for x in df.iloc[j].tolist()]} for j in range(lo, hi)],
            "demo": bool(config.datasets()[dataset].get("demo"))}


def _source_name(dataset: str) -> str:
    title = config.datasets()[dataset]["title"]
    return title.split(" (")[0]


def test_record(test_id: str) -> dict | None:
    st = get_store()
    if test_id not in st.tests.index:
        return None
    row = st.tests.loc[test_id].to_dict()
    ds = row["dataset"]
    invalid: dict = row.get("invalid") or {}
    image_derived = set(row.get("image_derived") or [])
    prov = st.provenance[st.provenance.test_id == test_id.split("~")[0]]
    pv = {r.variable: r for r in prov.itertuples()}
    fields = []
    for var, label, group in FIELDS:
        p = pv.get(var)
        if p is None:
            continue                               # this dataset does not carry the variable
        if var == "notes" and (row.get(var) is None or (not isinstance(row.get(var), str) and pd.isna(row.get(var)))):
            continue                               # most tests have no note: no empty row for it
        steps = json.loads(p.steps)
        ops = {s["op"] for s in steps}
        value, unit = display(var, row.get(var))
        if var == "gravity_g" and value == "Microgravity (ISS)" and config.datasets()[ds].get("microgravity_label"):
            value = config.datasets()[ds]["microgravity_label"]     # e.g. SAFFIRE flew on Cygnus, not the ISS
        note = None
        if var in invalid:
            status, value, unit, note = "flagged", None, "", invalid[var]
        elif "constant" in ops:
            status, note = "assumed", "Assumed (dataset setting), not a measurement from this test."
        elif value is None and ops & {"derive", "not_reported"}:
            # read from text that does not state it: say why it is blank, not "derived"
            status, note = "blank", next(s["detail"] for s in steps if s["op"] in ("derive", "not_reported"))
        elif "derive" in ops:
            status = "derived"
        elif value is None:
            status, note = "blank", _blank_reason(var, row)
        else:
            status = "measured"
        if "constant" in ops:
            src = {"kind": "setting", "text": f"Dataset setting for “{_source_name(ds)}”. The source table has no column for this."}
        elif "derive" in ops or "not_computed" in ops:
            how = "oxygen fraction × total pressure" if var == "o2_pp_kpa" else steps[0]["detail"]
            src = {"kind": "calculation", "text": f"Worked out here, not read from the source: {how}."}
        else:
            src = {"kind": "table", "dataset": ds, "row": int(row["_row"]), "column": p.column,
                   "text": f"{_source_name(ds)}, row {int(row['_row'])}, column “{p.column}”"}
        fields.append({
            "var": var, "label": label, "group": group, "status": status, "status_label": STATUS_LABEL[status],
            "value": value, "unit": unit, "note": note, "source": src,
            "trail": {"variable": var, "raw": p.raw_value, "file": p.source_file, "locator": p.locator,
                      "column": p.column, "steps": steps},
        })
    for var in sorted(image_derived):
        iv = row.get(f"img_{var}")
        value, unit = display(var, iv)
        if value is not None:
            label = next((lab for v, lab, _ in FIELDS if v == var), var)
            fields.append({"var": f"img_{var}", "label": f"{label}, measured from images", "group": "results",
                           "status": "image", "status_label": STATUS_LABEL["image"], "value": value, "unit": unit,
                           "note": "Extracted from the test's image sequence by the vision pipeline.",
                           "source": {"kind": "images", "text": "Image sequence of this test", "test": test_id},
                           "trail": {"variable": f"img_{var}", "raw": None, "file": "data/artifacts/vision", "locator": test_id,
                                     "column": None, "steps": [{"op": "image_measurement", "detail": "see Image Lab"}]}})
    log = st.validation_log[st.validation_log.test_id == test_id]
    notices = [{"rule": e.rule, "title": RULE_TITLE.get(e.rule, e.rule.replace("_", " ").capitalize()),
                "excludes": e.action == "exclude", "reason": e.reason, "detail": e.detail or ""}
               for e in log.itertuples()]
    inv = row.get("investigation_id")
    return {
        "test_id": test_id, "dataset": ds, "dataset_title": _source_name(ds),
        "investigation": None if inv is None or pd.isna(inv) else str(inv),
        "excluded": bool(row["excluded"]), "demo": bool(row["demo"]), "source_row": int(row["_row"]),
        "notices": notices, "fields": fields,
        "media": json.loads(st.media[st.media.test_id == test_id].to_json(orient="records")),
    }
