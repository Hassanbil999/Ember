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
FORMULA = {"ch4": "methane", "c2h4": "ethylene", "c2h6": "ethane", "c3h8": "propane", "c3h6": "propylene",
           "c12h26": "n-dodecane", "h2": "hydrogen"}
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


# ------------------------------------------------------------------ SLICE, ACME CLD Flame, ACME s-Flame (daily summaries)
def _yyddd(code: str) -> Optional[str]:
    m = re.match(r"^\s*(\d{2})(\d{3})\s*$", code or "")
    if not m or not 1 <= int(m.group(2)) <= 366:
        return None
    return (date(2000 + int(m.group(1)), 1, 1) + timedelta(days=int(m.group(2)) - 1)).isoformat()


def _fuel_as_written(text: str) -> Optional[str]:
    """A single 'pct formula' is named ('45% CH4' -> 'methane (45%)'); a mixture stays as the table writes it."""
    t = _clean(text)
    m = re.search(r"\swith\s+([A-Za-z0-9]+)\s*$", t)
    if m and m.group(1).lower() in FORMULA:            # "44.4% H2 with CH4" is a fuel mixture, not a diluted fuel
        return t
    part = t.split(" with")[0].split(" (")[0].strip(" ,")
    if re.fullmatch(r"\d+(?:\.\d+)?\s*%\s*[A-Za-z0-9]+", part) and part.split("%")[1].strip().lower() in FORMULA:
        return gas_name(part)
    return part or None


@register("psi_slice")
def load_slice(ds_id: str, cfg: dict) -> AdapterResult:
    raw = _read(ds_id, cfg)
    rows, index = [], []
    for i, r in raw.iterrows():
        cell, fuel_cell = _clean(r["Test Date"]), _clean(r["Fuel Type"])
        m = re.match(r"^(\d{4}-[A-Za-z]{3}-\d{1,2})\s*(.*)$", cell)
        if not m:
            continue
        d = pd.to_datetime(m.group(1), format="%Y-%b-%d", errors="coerce")
        when = d.strftime("%Y-%m-%d") if pd.notna(d) else None
        rows.append({"Test id": f"SLICE-{when or i}", "Fuel": _fuel_as_written(fuel_cell), "Date": when,
                     "Note": "Daily summary row. As written: " + "; ".join(x for x in (m.group(2), fuel_cell) if x),
                     "_src": {"Test Date": cell, "Fuel Type": fuel_cell},
                     "_why": {"fuel": ("Fuel Type", f"read from '{fuel_cell}'"),
                              "mission_date": ("Test Date", f"'{m.group(1)}' read as a date"),
                              "notes": ("Fuel Type", "the table's own text, unchanged")}})
        index.append(i)
    return _derive(_canonical(rows, index, ds_id, cfg), rows, cfg)


@register("psi_cld")
def load_cld(ds_id: str, cfg: dict) -> AdapterResult:
    """The Fuel Bottle column counts up row by row (CH4, CH5 ... CH14; C2H4 ... C2H11), the pattern a dragged
    spreadsheet cell leaves, so it is not used as the fuel: the fuel family comes from the Test Type column."""
    raw = _read(ds_id, cfg)
    family = {"methane": "methane", "ethylene": "ethylene"}
    rows, index = [], []
    for i, r in raw.iterrows():
        day = _clean(r["Test Day"])
        if not day:
            continue
        kind, bottle = _clean(r["Test Type"]), _clean(r["Fuel Bottle"])
        fam = next((v for k, v in family.items() if kind.lower().startswith(k)), None)
        rows.append({"Test id": f"CLD-{day}", "Fuel": fam, "Flames": _clean(r["Flames ignited"]), "Date": _yyddd(day),
                     "Note": (f"Daily summary row ({kind}). Fuel bottle as written: '{bottle}'; fuel concentration range "
                              f"{_clean(r['Fuel conc. Range'])}; fuel / N2 flow settings {_clean(r['Fuel MFC'])} / {_clean(r['N2 MFC'])}. "
                              "The Fuel Bottle column counts up row by row (CH4, CH5, CH6 ...), a spreadsheet auto-fill pattern, "
                              "so it is not used as the fuel."),
                     "_src": {"Test Type": kind, "Test Day": day},
                     "_why": {"fuel": ("Test Type", f"fuel family from the Test Type '{kind}'" if fam else
                                       f"the Test Type '{kind}' names no fuel, and the Fuel Bottle column is not reliable"),
                              "mission_date": ("Test Day", f"'{day}' read as year and day of year (YYDDD), as the table explains"),
                              "notes": ("Fuel Bottle", "the table's own values, unchanged, with a warning")}})
        index.append(i)
    return _derive(_canonical(rows, index, ds_id, cfg), rows, cfg)


@register("psi_sflame")
def load_sflame(ds_id: str, cfg: dict) -> AdapterResult:
    raw = _read(ds_id, cfg)
    c_day = next(c for c in raw.columns if c.startswith("Test Day"))
    c_atm = next(c for c in raw.columns if c.startswith("Atmosphere"))
    c_fl = next(c for c in raw.columns if c.startswith("Flames Ignited"))
    rows, index = [], []
    for i, r in raw.iterrows():
        day, atm, bottle = _clean(r[c_day]), _clean(r[c_atm]), _clean(r["Fuel Bottle"])
        if not day:
            continue
        mo = _clean(r["Month"]).lower()[:3]
        when = (date(int(_clean(r["Year"])), MONTH[mo], int(_clean(r["Date"]))).isoformat()
                if mo in MONTH and _clean(r["Date"]).isdigit() else _yyddd(day))
        m = re.search(r"with\s+([A-Za-z0-9]+)\s*$", atm)
        dil_txt = m.group(1) if m else ""
        dil = {"N2": "N2", "He": "He"}.get(dil_txt)
        levels = re.findall(r"(\d+(?:\.\d+)?)\s*%", atm)
        for k, lvl in enumerate(levels, 1):
            rows.append({"Test id": f"SFLAME-{day}-{k}", "Fuel": _fuel_as_written(bottle), "O2": f"{lvl} %", "Diluent": dil,
                         "Flames": _clean(r[c_fl]), "Date": when,
                         "Note": (f"Daily summary row. Atmosphere as written: '{atm}'; fuel bottle as written: '{bottle}'. "
                                  "The table says the chamber was about 1 atm, with pressure rising during testing; no pressure value is given."
                                  + ("" if dil or not dil_txt else f" '{dil_txt}' is not a gas (the column counts up N2, N3, N4 ..., "
                                                                     "a spreadsheet auto-fill pattern), so no diluent is recorded.")),
                         "_src": {c_atm: atm, "Fuel Bottle": bottle},
                         "_why": {"o2_frac": (c_atm, f"approximate level {k} of '{atm}' (the table writes ~)"),
                                  "diluent": (c_atm, f"'with {dil_txt}' in '{atm}'" if dil else
                                              f"'with {dil_txt}' in '{atm}' is not a gas; no diluent recorded"),
                                  "fuel": ("Fuel Bottle", f"read from '{bottle}'"),
                                  "mission_date": ("Year", "Year, Month and Date columns"),
                                  "notes": (c_atm, "the table's own text, unchanged")}})
            index.append(i)
    return _derive(_canonical(rows, index, ds_id, cfg), rows, cfg)
