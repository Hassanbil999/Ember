"""Adapters: smoke experiments for fire detection, as published on NASA PSI.

  psi_same    SAME experimental table (PSI-102): samples heated to make smoke for detector design.
  psi_same_r  SAME-R experimental table (PSI-101): five spacecraft materials heated at set heater
              levels, airflows and aging times.

Both tables record the CONDITIONS under which smoke was made, not the smoke measurements (particle
sizes are not in the PSI tables). So no outcome is set; these tests show what NASA tested for
detection, and nothing is claimed about the results.

Read as the tables say, and recorded as derived where text is interpreted:
  * SAME rows 5-8 read "Kapton: same conditions as 1-4". Each is expanded into four tests with the
    conditions of samples 1-4, and the provenance says so.
  * SAME-R rows whose test number ends in "a" (51a ...) are a second, longer-aged measurement of the
    smoke from the test with the same number, not a new heating run; the test note says so.
  * SAME-R dates have no year ("21-Jul"); the date is kept in the note and no year is invented.
  * SAME-R test 57 appears under two materials, so test ids include the material.
"""
from __future__ import annotations

import re

import pandas as pd

from ..core.config import RAW
from .base import AdapterResult, _is_blank, register, tabular_to_canonical

KEEP = lambda v: (None, None) if _is_blank(v) else (str(v), None)   # noqa: E731


def _read(ds_id: str, cfg: dict) -> pd.DataFrame:
    raw = pd.read_csv(RAW / ds_id / cfg["files"][0], dtype=str, keep_default_na=False, encoding="utf-8-sig")
    raw.columns = [c.strip() for c in raw.columns]
    return raw


def _clean(v) -> str:
    return "" if _is_blank(v) else " ".join(str(v).split())


def _derive(res: AdapterResult, how: dict[tuple[str, str], tuple[str, str]]) -> AdapterResult:
    """how[(test_id, variable)] = (source column, explanation): mark those values as derived."""
    for p in res.provenance:
        k = (p["test_id"], p["variable"])
        if k in how:
            col, why = how[k]
            p["column"] = col
            p["steps"] = [{"op": "derive", "detail": why}] + [s for s in p["steps"] if s["op"] != "map_category"]
    return res


@register("psi_same")
def load_same(ds_id: str, cfg: dict) -> AdapterResult:
    raw = _read(ds_id, cfg)
    c_mat = next(c for c in raw.columns if c.lower().startswith("sample material"))
    base = raw[raw[c_mat].str.contains(r"^\s*[A-Za-z]", regex=True) & raw["Air Flow (cm/s)"].str.strip().ne("")]
    rows, index, how = [], [], {}
    for i, r in raw.iterrows():
        mat = _clean(r[c_mat])
        m = re.match(r"^(.*?):\s*same conditions as (\d+)\s*-\s*(\d+)", mat, re.I)
        if m:                                  # "Kapton: same conditions as 1-4" -> four tests
            name, lo, hi = m.group(1).strip(), int(m.group(2)), int(m.group(3))
            for j, (_, b) in enumerate(base[base["Sample #"].astype(int).between(lo, hi)].iterrows(), 1):
                tid = f"SAME-{_clean(r['Sample #'])}.{j}"
                rows.append({"Test id": tid, "Material": name, "Flow": b["Air Flow (cm/s)"], "Loss": b["Weight loss rate (mg/min)"],
                             "Aging": b["Aging Duration (minutes)"], "Note": f"Conditions of sample {_clean(b['Sample #'])}, as the table states"})
                index.append(i)
                why = f"the row says '{mat}': conditions copied from sample {_clean(b['Sample #'])}"
                for v, col in (("flow_cm_s", "Air Flow (cm/s)"), ("mass_loss_rate_mg_min", "Weight loss rate (mg/min)"),
                               ("smoke_aging_s", "Aging Duration (minutes)")):
                    how[(tid, v)] = (col, why)
                how[(tid, "material")] = (c_mat, f"read from '{mat}'")
        elif mat:
            rows.append({"Test id": f"SAME-{_clean(r['Sample #'])}", "Material": mat, "Flow": r["Air Flow (cm/s)"],
                         "Loss": r["Weight loss rate (mg/min)"], "Aging": r["Aging Duration (minutes)"], "Note": None})
            index.append(i)
    frame = pd.DataFrame(rows, index=index).astype(object)
    frame = frame.where(frame.notna(), "")
    frame["Investigation"] = cfg["investigations"][0]
    res = tabular_to_canonical(frame, ds_id, cfg, f"data/raw/{ds_id}/{cfg['files'][0]}",
                               category_maps={"material": KEEP, "notes": KEEP})
    for r in rows:
        how[(r["Test id"], "investigation_id")] = (None, f"every row of this file belongs to {cfg['investigations'][0]}")
    return _derive(res, how)


@register("psi_same_r")
def load_same_r(ds_id: str, cfg: dict) -> AdapterResult:
    raw = _read(ds_id, cfg)
    rows, index, how = [], [], {}
    for i, r in raw.iterrows():
        mat, num = _clean(r["Sample Type"]), _clean(r["SAME Test #"])
        if not mat or not num:
            continue
        tid = f"SAMER-{mat[:3].upper()}-{num}"
        desc, date = _clean(r["Description"]), _clean(r["Date"])
        second = num[-1:].isalpha()
        note = (f"Second measurement of the smoke from test {num[:-1]}, after longer aging ({date}; the table gives no year)"
                if second else f"{desc} ({date}; the table gives no year)")
        rows.append({"Test id": tid, "Material": mat, "Flow": r["Inlet velocity (cm/s)"], "Heater": r["Rt/R0"],
                     "Heat time": r["Duration (sec)"], "Aging": r["Net aging time (sec)"], "Note": note})
        index.append(i)
        how[(tid, "notes")] = ("Description", (f"test number '{num}' ends in a letter and the description says '{desc}'"
                                               if second else "the table's description and date, unchanged"))
        how[(tid, "investigation_id")] = (None, f"every row of this file belongs to {cfg['investigations'][0]}")
    frame = pd.DataFrame(rows, index=index).astype(object)
    frame = frame.where(frame.notna(), "")
    frame["Investigation"] = cfg["investigations"][0]
    res = tabular_to_canonical(frame, ds_id, cfg, f"data/raw/{ds_id}/{cfg['files'][0]}",
                               category_maps={"material": KEEP, "notes": KEEP})
    return _derive(res, how)
