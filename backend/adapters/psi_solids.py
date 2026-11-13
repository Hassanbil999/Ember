"""Adapters: solid-material fire tests as published on NASA PSI.

  psi_bass2    BASS-II experimental table (PSI-25): one row per test in the Microgravity Science Glovebox.
  psi_bass     BASS experimental table (PSI-26): the run list (date, sample, material) only.
  psi_saffire  SAFFIRE-1/2/3 experimental tables (PSI-98/99/100): large samples burned in a Cygnus
               cargo vehicle after it left the ISS. SAFFIRE-2 also reports a 1g ground test of each
               sample; that becomes a second test row with gravity 1g.

These tables are lab notebooks rather than tidy tables, so the adapter reads free text. Every value
read from text is recorded as DERIVED in the provenance, with the original cell as its raw value and
the rule that produced it. What the text does not say is left blank, never guessed:

  * BASS-II has no burned / went-out column. Almost every test was lit and then taken to a limit on
    purpose (airflow lowered until the flame went out, or raised until it blew off), so `burned` is
    not set. "How the test ended" is read from the notes in the Fan display / Air display columns.
  * BASS-II airflow is written as a sequence of display readings without a stated unit, so no single
    airflow is assigned.
  * A sample whose material is not written is named only when every row of the same file that does
    name a sample of that shape names the same material (e.g. all named BASS-II rods are PMMA). The
    provenance says so. Otherwise it stays "Not named in the table".
  * SAFFIRE outcomes: "Complete" or a burn length equal to the sample length = burned the whole sample
    (burned = 1); "~ 0" = did not spread (burned = 0); anything in between has no yes/no outcome and is
    described in words.
"""
from __future__ import annotations

import re
from typing import Any, Optional

import pandas as pd

from ..core import config
from ..core.config import RAW
from .base import AdapterResult, _is_blank, register, tabular_to_canonical

UNNAMED = "Not named in the table"


# ------------------------------------------------------------------ reading sample descriptions
def _clean(s: Any) -> str:
    return "" if _is_blank(s) else " ".join(str(s).split())


def material_of(text: str) -> Optional[str]:
    t = text.lower()
    if "soot" in t and "clean" in t:
        return None
    if "pmma" in t:
        return "PMMA"
    if "sibal" in t or "cotton" in t:
        return "Cotton-fiberglass fabric (SIBAL)"
    if "nomex" in t:
        return "Nomex blend fabric" if "blend" in t else "Nomex III fabric"
    if "silicone" in t:
        return "Silicone"
    if "ultem" in t:
        return "Ultem (polyetherimide)"
    if "japan" in t:
        return "Japan wax"
    if "paraffin" in t or "parrafin" in t:
        return "Paraffin wax"
    if "wax" in t or "candle" in t:
        return "Wax (type not named)"
    return None


def shape_of(text: str, thickness_mm: Optional[float] = None) -> Optional[str]:
    t = text.lower()
    for key, shape in (("film", "film"), ("slab", "slab"), ("rod", "rod"), ("spher", "sphere"), ("candle", "candle"),
                       ("sheet", "sheet"), ("sibal", "fabric"), ("nomex", "fabric"), ("fabric", "fabric"), ("cotton", "fabric")):
        if key in t:
            return shape
    if thickness_mm is not None:                 # "1 mm thick PMMA 2 cm wide": a flat sample, named by its thickness
        return "film" if thickness_mm < 0.5 else "slab"
    return None


_INCH = re.compile(r'(\d+/\d+|\d*\.\d+|\d+)\s*(?:"|in\b|(?=\s*(?:clear|black|blac)\b))')
_THICK = re.compile(r"(\d*\.?\d+)\s*(micron|mm)\b")
_CM = re.compile(r"(\d*\.?\d+)\s*cm\b")


def thickness_text(text: str) -> Optional[str]:
    """'100 micron PMMA film' -> '100 um'; '2 cm 0.2 mm PMMA film' -> '0.2 mm'. Widths in cm are ignored."""
    m = _THICK.search(text.lower())
    if not m:
        return None
    return f"{m.group(1)} {'um' if m.group(2) == 'micron' else 'mm'}"


def diameter_text(text: str, shape: Optional[str]) -> Optional[str]:
    """Rods: '1/4\" clear rod' -> '0.25 in'. Spheres: '2 cm sphere' -> '2 cm'."""
    t = text.lower()
    if shape == "rod":
        m = _INCH.search(t)
        if m:
            v = m.group(1)
            if "/" in v:
                a, b = v.split("/")
                v = f"{int(a) / int(b):g}"
            return f"{v} in"
    if shape == "sphere":
        m = _CM.search(t)
        if m:
            return f"{m.group(1)} cm"
    return None


def flow_direction_of(text: str) -> Optional[str]:
    t = text.lower()
    if "oppos" in t or "oppsed" in t:
        return "opposed"
    if "concurrent" in t:
        return "concurrent"
    return None


def _num(v: Any) -> Optional[float]:
    m = re.search(r"\d*\.?\d+", _clean(v))
    return float(m.group(0)) if m else None


def _mm(text: Optional[str]) -> Optional[float]:
    if not text:
        return None
    v, u = text.split()
    return float(v) * {"um": 0.001, "mm": 1.0, "cm": 10.0, "in": 25.4}[u]


def fill_unnamed_materials(rows: list[dict], file_label: str) -> None:
    """Name an unnamed sample only if every named sample of the same shape in this file is one material."""
    named: dict[str, set] = {}
    for r in rows:
        if r.get("Material") and r["Material"] != UNNAMED and r.get("Shape"):
            named.setdefault(r["Shape"], set()).add(r["Material"])
    for r in rows:
        if r.get("Material") == UNNAMED and r.get("Shape") and len(named.get(r["Shape"], ())) == 1:
            mat = next(iter(named[r["Shape"]]))
            r["Material"] = mat
            r["_why"]["material"] = (f"the row does not name the material; every {r['Shape']} sample that is named in "
                                     f"{file_label} is {mat}, so this one is read as {mat}")


# ------------------------------------------------------------------ provenance
def _finish(res: AdapterResult, rows: list[dict], derived_from: dict[str, str]) -> AdapterResult:
    """Point derived variables at the raw cell they were read from, and say how."""
    by_id = {r["Test id"]: r for r in rows}
    values = res.tests.set_index("test_id")
    for p in res.provenance:
        r = by_id.get(p["test_id"])
        var = p["variable"]
        if r is None or var not in derived_from:
            continue
        src = derived_from[var]
        p["column"] = src
        p["raw_value"] = r["_src"].get(src) or None
        v = values.at[p["test_id"], var] if var in values.columns else None
        blank = v is None or (not isinstance(v, str) and pd.isna(v))
        label = config.variables().get(var, {}).get("label", var).lower()
        why = r["_why"].get(var) or (f"Not stated: '{src}' gives no {label} for this test" if blank
                                     else f"read from the text of '{src}'")
        p["steps"] = [{"op": "derive", "detail": why}] + [s for s in p["steps"] if s["op"] != "map_category"]
    return res


def _canonical(rows: list[dict], index: list[int], ds_id: str, cfg: dict, cats: tuple[str, ...]) -> AdapterResult:
    frame = pd.DataFrame([{k: v for k, v in r.items() if not k.startswith("_")} for r in rows], index=index)
    frame = frame.astype(object).where(frame.notna(), "")
    keep = lambda v: (None, None) if _is_blank(v) else (str(v), None)
    return tabular_to_canonical(frame, ds_id, cfg, f"data/raw/{ds_id}/{cfg['files'][0]}",
                                category_maps={c: keep for c in cats})


def _iso_date(v: str) -> tuple[Optional[str], Optional[str]]:
    if not v:
        return None, None
    d = pd.to_datetime(v, errors="coerce", format="mixed")
    if pd.isna(d):
        return None, f"The source says '{v}', which is not a readable date; left blank"
    if not 1990 <= d.year <= 2030:                 # e.g. "5/15/2103" in the BASS table: flagged, never corrected
        return None, f"The source says '{v}' (year {d.year}), which cannot be right for this test; left blank, not corrected"
    return d.strftime("%Y-%m-%d"), f"'{v}' → {d.strftime('%Y-%m-%d')}"


def _read(ds_id: str, cfg: dict) -> pd.DataFrame:
    raw = pd.read_csv(RAW / ds_id / cfg["files"][0], dtype=str, keep_default_na=False, encoding="utf-8-sig")
    raw.columns = [c.strip() for c in raw.columns]
    return raw


# ------------------------------------------------------------------ BASS-II
def bass2_test_end(notes: str) -> Optional[str]:
    n = notes.lower()
    if "no ign" in n:
        return "No ignition"
    if "would not stay lit" in n:
        return "Flame would not stay lit"
    if "blowoff" in n or "blow off" in n:
        return "Flame blew off when the airflow was raised"
    if re.search(r"(?<![a-z])ext\b|extinguish|\bout\b", n):
        return "Flame went out when the airflow was lowered"
    return None


@register("psi_bass2")
def load_bass2(ds_id: str, cfg: dict) -> AdapterResult:
    raw = _read(ds_id, cfg)
    rows, index = [], []
    for i, r in raw.iterrows():
        desc = _clean(r["Fuel Sample Material"])
        th = thickness_text(desc)
        shape = shape_of(desc, _mm(th))
        notes = f"Fan display: {_clean(r['Fan display']) or '–'}; Air display: {_clean(r['Air display']) or '–'}"
        end = bass2_test_end(notes)
        rows.append({
            "Test id": f"BASS2-{_clean(r['Test #'])}", "Campaign": _clean(r["PI"]), "Investigation": cfg["investigations"][0],
            "Material": material_of(desc) or UNNAMED, "Shape": shape, "Thickness": th if shape in ("film", "slab") else None,
            "Diameter": diameter_text(desc, shape), "Flow direction": flow_direction_of(desc),
            "O2": _clean(r["Calibrated  initial O2 % by vol"]), "Date": _iso_date(_clean(r["Date"]))[0], "Test end": end,
            "_src": {"Fuel Sample Material": desc, "Fan display / Air display": notes, "Date": _clean(r["Date"])},
            "_why": {"test_end": f"read from the test notes: {end.lower()}" if end else None,
                     "mission_date": _iso_date(_clean(r["Date"]))[1]},
        })
        index.append(i)
    fill_unnamed_materials(rows, "the BASS-II table")
    res = _canonical(rows, index, ds_id, cfg, ("material", "sample_shape", "flow_direction", "test_end", "campaign", "mission_date"))
    res = _finish(res, rows, {v: "Fuel Sample Material" for v in ("material", "sample_shape", "thickness_mm", "diameter_mm", "flow_direction")}
                  | {"test_end": "Fan display / Air display", "mission_date": "Date"})
    for p in res.provenance:
        if p["variable"] == "investigation_id":
            p["column"], p["raw_value"] = None, None
            p["steps"] = [{"op": "derive", "detail": "every row of this file belongs to BASS-II"}]
    return res


# ------------------------------------------------------------------ BASS (run list)
@register("psi_bass")
def load_bass(ds_id: str, cfg: dict) -> AdapterResult:
    raw = _read(ds_id, cfg)
    rows, index = [], []
    for i, r in raw.iterrows():
        desc = _clean(r["Fuel Sample Material"])
        mat = material_of(desc)
        shape = shape_of(desc)
        soot = "soot" in desc.lower()
        rows.append({
            "Test id": f"BASS-{_clean(r['As Run Test #']) or 'x'}-{_clean(r['Test #']) or 'x'}",
            "Investigation": cfg["investigations"][0], "Material": None if soot else (mat or UNNAMED), "Shape": shape,
            "Diameter": diameter_text(desc, shape), "Flow direction": flow_direction_of(desc),
            "Date": _iso_date(_clean(r["Date"]))[0], "Test end": "Soot cleaning run (no sample burned)" if soot else None,
            "_src": {"Fuel Sample Material": desc, "Date": _clean(r["Date"])},
            "_why": {"mission_date": _iso_date(_clean(r["Date"]))[1]},
        })
        index.append(i)
    fill_unnamed_materials(rows, "the BASS table")
    res = _canonical(rows, index, ds_id, cfg, ("material", "sample_shape", "flow_direction", "test_end", "mission_date"))
    res = _finish(res, rows, {v: "Fuel Sample Material" for v in ("material", "sample_shape", "diameter_mm", "flow_direction", "test_end")}
                  | {"mission_date": "Date"})
    for p in res.provenance:
        if p["variable"] == "investigation_id":
            p["column"], p["raw_value"] = None, None
            p["steps"] = [{"op": "derive", "detail": "every row of this file belongs to BASS"}]
    return res


# ------------------------------------------------------------------ SAFFIRE
def _col(raw: pd.DataFrame, *must: str, avoid: str = "\0") -> Optional[str]:
    for c in raw.columns:
        cl = c.lower()
        if all(m in cl for m in must) and avoid not in cl:
            return c
    return None


def saffire_outcome(burn_length: str, sample_length_cm: Optional[float], notes: dict[str, str] | None = None,
                    composite: bool = False) -> tuple[Optional[str], Optional[str]]:
    """burned as "1" / "0" / None, and the result in words (with the table's own footnote when one is cited)."""
    s = _clean(burn_length)
    sl = s.lower()
    if not s or sl.startswith("n/a"):
        return None, None
    cited = [notes[n] for n in re.findall(r"note\s*(\d+)", sl) if notes and n in notes]
    tail = (" — table note: " + " ".join(cited)) if cited else ""
    if composite:                                   # two materials in one sample: no single outcome
        return None, f"Two-part sample, burn length '{s}'{tail}"
    if sl.startswith("complete"):
        return "1", "Burned the whole sample"
    if re.match(r"^~\s*0\b", sl):
        return "0", "Did not spread"
    v = _num(s)
    if v is not None and sample_length_cm and abs(v - sample_length_cm) < 0.5 and "cm" in sl and not cited:
        return "1", "Burned the whole sample"
    return None, f"Burned part of the sample: {s}{tail}"


def _o2_text(v: str) -> tuple[Optional[str], Optional[str]]:
    """'~ 21.5' -> '21.5 %'; '22.1 to 22.0' or '21.5 - 21.7' -> midpoint."""
    nums = [float(x) for x in re.findall(r"\d*\.?\d+", v)]
    if not nums:
        return None, None
    if len(nums) >= 2:
        mid = (nums[0] + nums[1]) / 2
        return f"{mid:.4g} %", f"midpoint of the range '{v}'"
    return f"{nums[0]:g} %", (f"'{v}' is approximate (~)" if "~" in v else None)


@register("psi_saffire")
def load_saffire(ds_id: str, cfg: dict) -> AdapterResult:
    raw = _read(ds_id, cfg)
    tag = cfg["id_prefix"]
    c_id = raw.columns[0]
    c_th = _col(raw, "thickness")
    c_len = _col(raw, "length", avoid="burn")
    c_flow = _col(raw, "air flow")
    c_o2 = _col(raw, "o2")
    c_bt = _col(raw, "burn time")
    c_dir = _col(raw, "direction")
    c_ug_len = next((c for c in raw.columns if "burn length" in c.lower() and not c.lower().startswith("1-g")), None)
    c_ug_rate = next((c for c in raw.columns if "spread" in c.lower() and not c.lower().startswith("1-g")), None)
    c_1g_len, c_1g_rate = _col(raw, "1-g", "burn length"), _col(raw, "1-g", "spread")
    th_unit = "cm" if c_th and "(cm)" in c_th.lower() else ""

    notes: dict[str, str] = {}                               # the table's own footnotes: "Note 3 This is the ..."
    for v in raw[c_id]:
        m = re.match(r"^\s*note\s*(\d+)\s+(.*)$", _clean(v), re.I)
        if m:
            notes[m.group(1)] = m.group(2).rstrip(".") + "."
    rows, index, last_mat = [], [], None
    for i, r in raw.iterrows():
        sid = _clean(r[c_id])
        thick_raw = _clean(r[c_th]) if c_th else ""
        if not re.match(r"^(S\d|\d+-\d+)", sid):             # flow-visualisation rows and footnotes
            continue
        desc = _clean(r["Material"])
        why: dict[str, Optional[str]] = {}
        mat = material_of(desc)
        if "pmma" in desc.lower() and "nomex" in desc.lower():
            mat = "PMMA and Nomex (two-part sample)"
        if not desc and last_mat:
            mat = last_mat
            why["material"] = f"the Material cell is blank; the row above names {last_mat} (spreadsheet convention)"
        last_mat = mat or last_mat
        thick = thick_raw if re.search(r"[a-z]", thick_raw, re.I) else (f"{thick_raw} {th_unit}".strip() if thick_raw else "")
        if thick and not re.fullmatch(r"\d*\.?\d+\s*(mm|cm)", thick):
            why["thickness_mm"] = f"'{thick_raw}' is not a single thickness, so none is recorded"
            thick = ""
        composite = mat is not None and "two-part" in mat
        sample_len = _num(r[c_len]) if c_len else None
        o2, o2_why = _o2_text(_clean(r[c_o2])) if c_o2 else (None, None)
        if o2_why:
            why["o2_frac"] = o2_why
        base = {"Investigation": cfg["investigations"][0], "Campaign": cfg["investigations"][0],
                "Material": mat or UNNAMED,
                "Shape": None if composite else (shape_of(desc) or ("fabric" if mat and "fabric" in mat.lower() else None)),
                "Thickness": thick or None, "Flow direction": (_clean(r[c_dir]).lower() or None) if c_dir else None}
        src = {"Material": desc, c_o2 or "": _clean(r[c_o2]) if c_o2 else ""}
        ug_end, ug_text = saffire_outcome(r[c_ug_len], sample_len, notes, composite) if c_ug_len else (None, None)
        flow = _clean(r[c_flow]) if c_flow else ""
        rows.append({**base, "Test id": f"{tag}-{sid}" + ("-UG" if c_1g_len else ""), "Gravity": "0",
                     "Airflow": (flow if re.search(r"[a-z]", flow, re.I) else f"{flow} cm/s") if flow else None,
                     "O2": o2, "Burn time": _clean(r[c_bt]) if c_bt else None, "Burned": ug_end, "Test end": ug_text,
                     "Spread rate": _clean(r[c_ug_rate]) if c_ug_rate else None,
                     "_src": {**src, "burn length": _clean(r[c_ug_len]) if c_ug_len else ""},
                     "_why": {**why, "gravity_g": "flight test in microgravity (Cygnus vehicle)",
                              "burned": f"from the microgravity burn length '{_clean(r[c_ug_len])}'" if c_ug_len else None}})
        index.append(i)
        if c_1g_len:                                          # SAFFIRE-2: the same sample tested on the ground
            g_end, g_text = saffire_outcome(r[c_1g_len], sample_len, notes, composite)
            rate = _clean(r[c_1g_rate])
            if rate.lower().startswith("acceler"):
                g_text = (g_text or "") + " (spread was accelerating)"
            rows.append({**base, "Test id": f"{tag}-{sid}-1G", "Gravity": "1", "Airflow": None, "O2": None,
                         "Burn time": None, "Burned": g_end, "Test end": g_text, "Spread rate": rate,
                         "_src": {**src, "burn length": _clean(r[c_1g_len])},
                         "_why": {**why, "gravity_g": "1g ground test of the same sample, reported in the same row",
                                  "o2_frac": None, "burned": f"from the 1g burn length '{_clean(r[c_1g_len])}'"}})
            index.append(i)
    res = _canonical(rows, index, ds_id, cfg, ("material", "sample_shape", "flow_direction", "test_end", "campaign"))
    derived = {"material": "Material", "sample_shape": "Material", "burned": "burn length", "test_end": "burn length"}
    if c_o2:
        derived["o2_frac"] = c_o2
    res = _finish(res, rows, derived)
    for p in res.provenance:
        if p["variable"] in ("investigation_id", "campaign", "gravity_g"):
            r = next(x for x in rows if x["Test id"] == p["test_id"])
            p["column"], p["raw_value"] = None, None
            p["steps"] = [{"op": "derive", "detail": r["_why"].get("gravity_g") if p["variable"] == "gravity_g"
                           else f"every row of this file belongs to {cfg['investigations'][0]}"}]
        if p["variable"] == "o2_frac":
            r = next(x for x in rows if x["Test id"] == p["test_id"])
            if r["Gravity"] == "1":
                p["steps"] = [{"op": "not_reported", "detail": "the table gives no oxygen level for the 1g ground test"}]
    return res
