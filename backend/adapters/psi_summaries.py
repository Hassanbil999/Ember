"""Adapters: the remaining NASA PSI experimental tables, read as published.

  psi_cfi     CFI (PSI-39): Cool Flames Investigation droplet tests, one row per test, conditions only.
  psi_spice   SPICE (PSI-107): smoke-point gas flames; several fuel/air settings per flame.
  psi_bre     ACME BRE (PSI-20): Burning Rate Emulator, one summary row per test day.
  psi_efield  ACME E-FIELD Flames (PSI-22): one summary row per test day.

None of these tables records whether a flame kept burning, so no `burned` outcome is set. What is read
from text is recorded as derived, with the rule; exact duplicate rows keep the same test id so the
shared duplicate rule excludes and logs them (never silently dropped); impossible source values such as
"3400%" oxygen are passed through unchanged so the shared checks flag them (never corrected).
"""
from __future__ import annotations

import re
from datetime import date, timedelta
from typing import Optional

import pandas as pd

from ..core.config import RAW
from .base import AdapterResult, _is_blank, register, tabular_to_canonical

KEEP = lambda v: (None, None) if _is_blank(v) else (str(v), None)   # noqa: E731
FORMULA = {"ch4": "methane", "c2h4": "ethylene", "c3h8": "propane", "c3h6": "propylene", "c12h26": "n-dodecane"}
MONTH = {m: i for i, m in enumerate(["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], 1)}


def _read(ds_id: str, cfg: dict) -> pd.DataFrame:
    raw = pd.read_csv(RAW / ds_id / cfg["files"][0], dtype=str, keep_default_na=False, encoding="utf-8-sig")
    raw.columns = [c.strip() for c in raw.columns]
    return raw


def _clean(v) -> str:
    return "" if _is_blank(v) else " ".join(str(v).split())


def gas_name(text: str) -> Optional[str]:
    """'100% C2H4' -> 'ethylene'; '40% CH4' -> 'methane (40%)'; '75 % Propylene' -> 'propylene (75%)';
    '[.75]/[.25] C12H26/iso-dodecane' -> 'n-dodecane / iso-dodecane (75/25)'."""
    t = _clean(text)
    if not t:
        return None
    m = re.match(r"^\[\.?(\d+)\]\s*/\s*\[\.?(\d+)\]\s*(\S+)\s*/\s*(\S+)$", t)
    if m:
        a, b = (FORMULA.get(x.lower(), x.lower()) for x in (m.group(3), m.group(4)))
        return f"{a} / {b} ({m.group(1)}/{m.group(2)})"
    m = re.match(r"^(\d+(?:\.\d+)?)\s*%\s*(.+)$", t)
    pct, name = (m.group(1), m.group(2)) if m else (None, t)
    name = FORMULA.get(name.strip().lower(), name.strip().lower())
    return name if pct in (None, "100") else f"{name} ({pct}%)"


def _canonical(rows: list[dict], index: list, ds_id: str, cfg: dict) -> AdapterResult:
    frame = pd.DataFrame([{k: v for k, v in r.items() if not k.startswith("_")} for r in rows], index=index).astype(object)
    frame = frame.where(frame.notna(), "")
    frame["Investigation"] = cfg["investigations"][0]
    return tabular_to_canonical(frame, ds_id, cfg, f"data/raw/{ds_id}/{cfg['files'][0]}",
                                category_maps={"fuel": KEEP, "notes": KEEP, "test_end": KEEP, "mission_date": KEEP})


def _derive(res: AdapterResult, rows: list[dict], cfg: dict) -> AdapterResult:
    """Each row may carry _why = {variable: (source column, explanation)}: those values are marked derived."""
    by_id: dict[str, dict] = {}
    for r in rows:
        by_id.setdefault(r["Test id"], r)
    for p in res.provenance:
        r = by_id.get(p["test_id"])
        if p["variable"] == "investigation_id":
            p["column"], p["raw_value"] = None, None
            p["steps"] = [{"op": "derive", "detail": f"every row of this file belongs to {cfg['investigations'][0]}"}]
        elif r and p["variable"] in r.get("_why", {}):
            col, why = r["_why"][p["variable"]]
            p["column"], p["raw_value"] = col, r.get("_src", {}).get(col, p["raw_value"])
            p["steps"] = [{"op": "derive", "detail": why}] + [s for s in p["steps"] if s["op"] not in ("map_category",)]
    return res


# ------------------------------------------------------------------ CFI (droplets)
@register("psi_cfi")
def load_cfi(ds_id: str, cfg: dict) -> AdapterResult:
    raw = _read(ds_id, cfg)
    rows, index = [], []
    for i, r in raw.iterrows():
        num = _clean(r["Flex Number"])
        if not num:
            continue
        d = pd.to_datetime(_clean(r["Test Date"]), errors="coerce", format="%d-%b-%y")
        fiber = _clean(r["Fiber"])
        rows.append({"Test id": f"CFI-{num}", "Fuel": gas_name(r["Fuel"]), "Pressure": _clean(r["Pressure"]),
                     "O2": r["Oxygen"], "N2": r["Nitrogen"], "He": r["Helium"],
                     "Date": d.strftime("%Y-%m-%d") if pd.notna(d) else None,
                     "Note": f"Fiber-supported droplet: {fiber}" if fiber else None,
                     "_src": {"Fuel": _clean(r["Fuel"]), "Test Date": _clean(r["Test Date"]), "Fiber": fiber},
                     "_why": {"fuel": ("Fuel", f"'{_clean(r['Fuel'])}' read as {gas_name(r['Fuel'])}"),
                              "mission_date": ("Test Date", f"'{_clean(r['Test Date'])}' read as a day-month-year date"),
                              "notes": ("Fiber", "the table's Fiber column")}})
        index.append(i)
    return _derive(_canonical(rows, index, ds_id, cfg), rows, cfg)


# ------------------------------------------------------------------ SPICE (smoke point, gas jets)
def _secs(t: str) -> Optional[int]:
    m = re.match(r"^(\d{1,2}):(\d{2}):(\d{2})$", _clean(t))
    return int(m.group(1)) * 3600 + int(m.group(2)) * 60 + int(m.group(3)) if m else None


@register("psi_spice")
def load_spice(ds_id: str, cfg: dict) -> AdapterResult:
    raw = _read(ds_id, cfg)
    c_off = next(c for c in raw.columns if "flame off" in c.lower())
    rows, index, setting = [], [], {}
    for i, r in raw.iterrows():
        day, ign, off = _clean(r["GMT date"]), _clean(r["GMT ignition"]), _clean(r[c_off])
        if not day:
            continue
        a, b = _secs(ign), _secs(off)
        dur = None if a is None or b is None else (b - a) % 86400
        flame = f"{day}-{ign.replace(':', '')}"
        key = (flame, _clean(r["Fuel Rate (sccm)"]), _clean(r["Air Rate (cm/s)"]))
        setting.setdefault(key, len([k for k in setting if k[0] == flame]) + 1)
        # identical rows get the same id, so the duplicate rule excludes and logs the copies
        rows.append({"Test id": f"SPICE-{flame}-{setting[key]}", "Fuel": gas_name(r["Fuel"]), "Nozzle": r["Nozzle (mm)"],
                     "Fuel flow": r["Fuel Rate (mg/s)"], "Air": r["Air Rate (cm/s)"], "Burn": str(dur) if dur is not None else "",
                     "Note": f"Setting {setting[key]} of the flame lit on GMT day {day} at {ign} (the table gives no year)",
                     "_src": {"GMT  Flame Off": f"{ign} → {off}", "Fuel": _clean(r["Fuel"])},
                     "_why": {"burn_time_s": ("GMT  Flame Off", f"flame-off time minus ignition time ({ign} → {off}); the whole flame, not this setting"),
                              "fuel": ("Fuel", f"'{_clean(r['Fuel'])}' read as {gas_name(r['Fuel'])}")}})
        index.append(i)
    return _derive(_canonical(rows, index, ds_id, cfg), rows, cfg)


# ------------------------------------------------------------------ ACME BRE (daily summary)
@register("psi_bre")
def load_bre(ds_id: str, cfg: dict) -> AdapterResult:
    raw = _read(ds_id, cfg)
    rows, index = [], []
    for i, r in raw.iterrows():
        y, mo, d = _clean(r["Year"]), _clean(r["Month"]).lower()[:3], _clean(r["Date"])
        if not y:
            continue
        when = date(int(y), MONTH[mo], int(d)).isoformat() if mo in MONTH and d.isdigit() else None
        n = _clean(r["Flames Ignited"])
        o2_cell = _clean(r["Oxygen Conc (percent)"])
        for k, lvl in enumerate([x.strip() for x in o2_cell.split(";") if x.strip()], 1):
            end = ("No flame ignited that day" if n == "0" else "At least one flame ignited at this oxygen level that day")
            rows.append({"Test id": f"BRE-{when or y}-{k}", "Fuel": gas_name(r["Fuel Bottle"]), "Burner": r["Burner Size (mm)"],
                         "O2": lvl if "%" in lvl else f"{lvl} %", "Flames": n, "End": end, "Date": when,
                         "Note": "Daily summary row; chamber pressure was varied but is not given in this table",
                         "_src": {"Oxygen Conc (percent)": o2_cell, "Flames Ignited": n},
                         "_why": {"o2_frac": ("Oxygen Conc (percent)", f"level {k} of the list '{o2_cell}' (percent by volume)"),
                                  "test_end": ("Flames Ignited", "the table lists the oxygen levels of flames that ignited that day"
                                               if n != "0" else "the table reports 0 flames ignited that day"),
                                  "mission_date": ("Year", f"Year, Month and Date columns: {y} {r['Month']} {d}"),
                                  "fuel": ("Fuel Bottle", f"'{_clean(r['Fuel Bottle'])}' read as {gas_name(r['Fuel Bottle'])}")}})
            index.append(i)
    return _derive(_canonical(rows, index, ds_id, cfg), rows, cfg)


# ------------------------------------------------------------------ ACME E-FIELD (daily summary)
@register("psi_efield")
def load_efield(ds_id: str, cfg: dict) -> AdapterResult:
    raw = _read(ds_id, cfg)
    rows, index, last = [], [], None
    for i, r in raw.iterrows():
        day = _clean(r["Test Day"])
        conc = _clean(r["Fuel Conc"])
        if not day:                                   # continuation row: one more fuel concentration that day
            if last is not None and conc:
                last["_concs"].append(conc)
            continue
        when = date(int(_clean(r["Year"])), int(_clean(r["Month"])), int(_clean(r["Date"]))).isoformat()
        last = {"Test id": f"EFIELD-{day}", "Fuel": gas_name(r["Fuel Bottle"]), "Flames": _clean(r["Flames Ignited"]), "Date": when,
                "_kind": _clean(r["Test Type"]), "_polarity": _clean(r["Mesh Polarity"]), "_concs": [conc] if conc else [],
                "_src": {"Fuel Bottle": _clean(r["Fuel Bottle"])},
                "_why": {"fuel": ("Fuel Bottle", f"'{_clean(r['Fuel Bottle'])}' read as {gas_name(r['Fuel Bottle'])}"),
                         "mission_date": ("Year", "Year, Month and Date columns")}}
        rows.append(last)
        index.append(i)
    for r in rows:
        r["Note"] = (f"{r['_kind']}; mesh polarity {r['_polarity']}; fuel concentrations used: {', '.join(r['_concs'])} "
                     "(daily summary row)")
    return _derive(_canonical(rows, index, ds_id, cfg), rows, cfg)
